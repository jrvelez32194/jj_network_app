import os
import time
import json
import threading
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

# ============================================================
# 🧩 Logger Setup
# ============================================================
logger = logging.getLogger("mikrotik_poll")
logger.setLevel(logging.INFO)

# ============================================================
# 🌐 Router Mapping (Configurable)
# ============================================================
DEFAULT_MAP = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or DEFAULT_MAP
    logger.info(f"✅ Loaded router map: {ROUTER_MAP}")
except json.JSONDecodeError:
    ROUTER_MAP = DEFAULT_MAP
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON format, using defaults.")

# ============================================================
# 🗃️ DB Session Helper
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# 🧠 Global State Tracking
# ============================================================
last_state = {}         # Last observed router state (UP/DOWN/SPIKING)
notified_state = {}     # Last state that was notified
spiking_active = {}     # Track SPIKING events (for recovery)

# ============================================================
# ⏱️ Timing Settings
# ============================================================
DELAY = 180                   # Debounce before notifying (in seconds)
RECOVERY_STABLE_SECONDS = 120 # 2 minutes stability before recovery message
FLAP_WINDOW = 120             # Time window for flap detection
FLAP_THRESHOLD = 3            # Minimum changes within window to trigger spiking

# ============================================================
# ⚡ Default Message Templates (fallback only)
# ============================================================
SPIKING_MESSAGES = {
    ("ISP1-PING", "G1"): "⚠️ Primary ISP is experiencing high latency. Switched to secondary temporarily.",
    ("ISP2-PING", "G1"): "⚠️ Secondary ISP latency detected. Primary remains active.",
    ("ISP1-PING", "G2"): "⚠️ ISP connection high ping detected. Please standby.",
}

SPIKING_RECOVERY_MESSAGES = {
    ("ISP1-PING", "G1"): "✅ Primary ISP stable again. Back to normal performance.",
    ("ISP2-PING", "G1"): "✅ Secondary ISP stable again. Traffic normal.",
    ("ISP1-PING", "G2"): "✅ ISP connection stable again. Thank you for your patience.",
}

# ============================================================
# 🔍 Template Finder (Priority-based)
# ============================================================
def find_template(db: Session, connection_name: Optional[str], group_name: Optional[str], state: str):
    s = (state or "").upper()
    candidates: List[str] = []

    if connection_name and group_name:
        candidates.append(f"{connection_name.upper()}-{group_name.upper()}-{s}")
    candidates.append(f"{group_name.upper()}-{s}" if group_name else None)
    candidates.append(f"{connection_name.upper()}-{s}" if connection_name else None)
    candidates.append(s)

    for title in filter(None, candidates):
        tpl = db.query(models.Template).filter(models.Template.title.ilike(title)).first()
        if tpl:
            return tpl
    return None

# ============================================================
# 💬 Notification Sender
# ============================================================
def notify_clients(db: Session, connection_name: str = None, group_name: str = None, state: str = None):
    """Send templated message to clients using DB templates with auto-creation fallback."""
    state_key = (state or "").upper()
    template = find_template(db, connection_name, group_name, state_key)

    conn_type = (connection_name or "").lower()

    # 🚫 Skip non-customer links for all main states
    if not (
        "vendo" in conn_type or "private" in conn_type or "isp" in conn_type):
      if state_key in ("UP", "DOWN", "SPIKING", "RECOVERY"):
        logger.info(
          f"🛑 Skipping {state_key} notification for non-mt link: {connection_name}")
        return

    # Auto-create if not found
    if not template:
        content = None
        if state_key == "SPIKING":
            content = SPIKING_MESSAGES.get((connection_name, group_name))
        elif state_key == "UP" and last_state.get(f"{connection_name}_{group_name}") == "SPIKING":
            content = SPIKING_RECOVERY_MESSAGES.get((connection_name, group_name))

        if not content:
            if state_key == "DOWN":
                if "vendo" in conn_type:
                    content = "Your VENDO is currently down. Please check the connection."
                elif "private" in conn_type:
                    content = "Your PRIVATE connection is currently down. Please check connections."
                else:
                    logger.info(f"🛑 Skipping DOWN notification for non-customer link: {connection_name}")
                    return
            elif state_key == "UP":
                if "vendo" in conn_type:
                    content = "Your VENDO is now up and running."
                elif "private" in conn_type:
                    content = "Your PRIVATE connection is now up and running."
                else:
                    logger.info(f"🛑 Skipping UP notification for non-customer link: {connection_name}")
                    return

        preferred_title = f"{connection_name.upper()}-{group_name.upper()}-{state_key}"
        template = models.Template(
            title=preferred_title,
            content=content or f"Notification: {preferred_title}"
        )
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"🧩 Auto-created template '{preferred_title}' for {connection_name}/{group_name}/{state_key}")

    # Determine recipients
    conn_lower = (connection_name or "").lower()
    is_local = "vendo" in conn_lower or "private" in conn_lower

    query = db.query(models.Client)
    if is_local:
        query = query.filter(
            models.Client.connection_name == connection_name,
            models.Client.group_name == group_name,
        )
    else:
        query = query.filter(models.Client.group_name == group_name)

    clients = query.all()

    for client in clients:
        if getattr(client, "status", None) == BillingStatus.CUTOFF:
            logger.info(f"⏩ Skipping {client.name} ({connection_name}) – CUTOFF")
            continue
        try:
            resp = send_message(client.messenger_id, template.content)
            db.add(models.MessageLog(
                client_id=client.id,
                template_id=template.id,
                status=resp.get("message_id", "failed"),
            ))
            db.commit()
            logger.info(f"📩 Notified {client.name} ({connection_name}/{group_name}) with '{template.title}'")
        except Exception as e:
            logger.error(f"❌ Failed sending to {client.name}: {e}")

# ============================================================
# ⏳ Debounced Notification
# ============================================================
def schedule_notify(state_key, connection_name, group_name, new_state):
    def task():
        logger.info(f"[{state_key}] Waiting {DELAY}s before confirming {new_state}")
        time.sleep(DELAY)
        if last_state.get(state_key) == new_state:
            prev = notified_state.get(state_key)
            if prev != new_state:
                db = SessionLocal()
                try:
                    notify_clients(db, connection_name, group_name, new_state)
                    notified_state[state_key] = new_state
                finally:
                    db.close()
            else:
                logger.info(f"[{state_key}] {new_state} already notified, skipping")
        else:
            logger.info(f"[{state_key}] State changed before {DELAY}s expired, cancelling")

    threading.Thread(target=task, daemon=True).start()

# ============================================================
# 🌐 WebSocket Broadcast Helper
# ============================================================
def broadcast_state_change(ws_manager, client, connection_name, new_state):
    if not ws_manager:
        return
    payload = {
        "event": "state_update",
        "id": int(getattr(client, "id", 0)),
        "messenger_id": getattr(client, "messenger_id", None),
        "client": getattr(client, "name", "Unknown"),
        "connection_name": connection_name,
        "state": new_state,
        "timestamp": time.time(),
    }
    try:
        ws_manager.safe_broadcast(payload)
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")

# ============================================================
# 🧩 Core State Processor
# ============================================================
def process_rule(db, client, connection_name, last_state_value, group_name, ws_manager=None):
    key = f"{connection_name}_{group_name}"

    # SPIKING DETECTED
    if last_state_value == "SPIKING":
        logger.info(f"⚠️ {key} detected SPIKING")
        broadcast_state_change(ws_manager, client or models.Client(id=0, name="Unknown"), connection_name, "SPIKING")

        if notified_state.get(key) == "SPIKING":
            logger.info(f"⏩ SPIKING already notified for {key}, skipping")
            last_state[key] = "SPIKING"
            return

        notify_clients(db, connection_name, group_name, "SPIKING")
        notified_state[key] = "SPIKING"
        spiking_active[key] = time.time()
        last_state[key] = "SPIKING"
        return

    # RECOVERY FROM SPIKING
    if last_state.get(key) == "SPIKING" and last_state_value == "UP":
        logger.info(f"🧩 {key} recovering from SPIKING – scheduling recovery in {RECOVERY_STABLE_SECONDS}s")

        def recovery_task():
            time.sleep(RECOVERY_STABLE_SECONDS)
            db2 = SessionLocal()
            try:
                if last_state.get(key) == "UP" and spiking_active.get(key):
                    notify_clients(db2, connection_name, group_name, "UP")
                    logger.info(f"✅ Sent recovery message for {key}")
                    spiking_active.pop(key, None)
                    notified_state[key] = "UP"
            except Exception as e:
                logger.error(f"❌ Recovery task failed for {key}: {e}")
            finally:
                db2.close()

        threading.Thread(target=recovery_task, daemon=True).start()

    # NORMAL UP/DOWN HANDLING
    if client and client.state != last_state_value:
        logger.info(f"🔄 {client.name} ({connection_name}/{group_name}) {client.state} → {last_state_value}")
        broadcast_state_change(ws_manager, client, connection_name, last_state_value)
        schedule_notify(key, connection_name, group_name, last_state_value)
        client.state = last_state_value
        db.add(client)
    else:
        broadcast_state_change(ws_manager, models.Client(id=0, name="Unknown"), connection_name, last_state_value)

    last_state[key] = last_state_value

# ============================================================
# 🔁 Polling Loop with Smart Flap Detection
# ============================================================
def poll_netwatch(host, username, password, interval=30, ws_manager=None, group_name=None):
    mikrotik = MikroTikClient(host, username, password)
    change_history = {}

    while True:
        if not mikrotik.ensure_connection():
            logger.warning(f"❌ Cannot connect to {host}, retrying in {interval}s...")
            time.sleep(interval)
            continue

        rules = mikrotik.get_netwatch() or []
        db = next(get_db())

        try:
            for rule in rules:
                connection_name = rule.get("comment") or rule.get("host")
                raw_status = (rule.get("status") or "unknown").upper()
                state_val = raw_status
                key = f"{connection_name}_{group_name}"
                now = time.time()

                # Maintain rolling history
                history = [(t, s) for (t, s) in change_history.get(key, []) if now - t < FLAP_WINDOW]
                if not history or history[-1][1] != state_val:
                    history.append((now, state_val))
                change_history[key] = history

                # Detect flapping/spiking
                if len(history) >= FLAP_THRESHOLD and len({s for _, s in history}) > 1:
                    state_val = "SPIKING"
                    change_history[key] = []
                    logger.info(f"🚨 Detected SPIKING for {connection_name} ({group_name}) history={history}")

                # Process rule
                client = db.query(models.Client).filter(models.Client.connection_name == connection_name).first()
                effective_group = getattr(client, "group_name", None) or group_name
                process_rule(db, client, connection_name, state_val, effective_group, ws_manager)
                db.commit()
        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error polling {host}: {e}")
        finally:
            db.close()

        time.sleep(interval)

# ============================================================
# 🚀 Polling Starter
# ============================================================
def start_polling(username, password, interval=30, ws_manager=None):
    for group_name, host in ROUTER_MAP.items():
        threading.Thread(
            target=poll_netwatch,
            args=(host, username, password, interval, ws_manager, group_name),
            daemon=True,
        ).start()
        logger.info(f"✅ Started Netwatch polling for '{group_name}' ({host})")

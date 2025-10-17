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
last_state = {}
notified_state = {}
spiking_active = {}

# ============================================================
# ⏱️ Timing Settings
# ============================================================
DELAY = 180
RECOVERY_STABLE_SECONDS = 120
FLAP_WINDOW = 120
FLAP_THRESHOLD = 3
SPIKING_DEBOUNCE_SECONDS = 10  # 🆕 Prevents duplicate SPIKING notifications

# ============================================================
# ⚡ SPIKING ALERT MESSAGES
# ============================================================
SPIKING_MESSAGES = {
    ("ISP1-PING", "G1"): "⚠️ Primary ISP is experiencing high latency. Switched to secondary temporarily.",
    ("ISP2-PING", "G1"): "⚠️ Secondary ISP latency detected. Primary remains active.",
    ("ISP1-PING", "G2"): "⚠️ PLDT high ping detected. Please standby.",
    ("ISP1-CONNECTION", "G1"): "⚠️ Primary internet is unstable, timeout detected. Switched to secondary temporarily.",
    ("ISP2-CONNECTION", "G1"): "⚠️ Secondary ISP is unstable. No worries, Primary remains active.",
    ("ISP1-CONNECTION", "G2"): "⚠️ PLDT is unstable. Please standby waiting to be fixed.",
}

# ============================================================
# ✅ SPIKING RECOVERY MESSAGES
# ============================================================
SPIKING_RECOVERY_MESSAGES = {
    ("ISP1-PING", "G1"): "✅ Primary ISP stable again. Back to normal performance.",
    ("ISP2-PING", "G1"): "✅ Secondary ISP stable again. Traffic normal.",
    ("ISP1-PING", "G2"): "✅ PLDT stable again. Thank you for your patience.",
    ("ISP1-CONNECTION", "G1"): "✅ Primary internet is stable again. Back to normal performance.",
    ("ISP2-CONNECTION", "G1"): "✅ Secondary ISP is stable again. Primary remains active.",
    ("ISP1-CONNECTION", "G2"): "✅ PLDT connection is stable again. Thank you for your patience.",
}

# ============================================================
# 🔍 Template Finder
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
# 💬 Notification Sender (simplified)
# ============================================================
def notify_clients(db: Session, connection_name: str = None, group_name: str = None, state: str = None):
    state_key = (state or "").upper()
    conn_type = (connection_name or "").lower()

    # ------------------------------------------------------------
    # 🏷️ Dynamic ISP Label Resolver
    # ------------------------------------------------------------
    def get_label(conn_name: str, grp: str) -> Optional[str]:
        name, grp = (conn_name or "").upper(), (grp or "").upper()
        if grp == "G1":
            if name.startswith("ISP1-"): return "Primary Internet"
            if name.startswith("ISP2-"): return "Secondary Internet"
        elif grp == "G2" and name.startswith("ISP1-"):
            return "PLDT"
        return None

    isp_label = get_label(connection_name, group_name)

    # ------------------------------------------------------------
    # 🧠 Template Fetch or Auto-create
    # ------------------------------------------------------------
    template = find_template(db, connection_name, group_name, state_key)
    if not template:
        content = build_auto_template_content(conn_type, connection_name, isp_label, state_key, group_name)
        if not content:
            logger.info(f"⏩ Skipping auto-template for {connection_name}/{state_key}")
            return

        title = f"{(connection_name or '').upper()}-{(group_name or '').upper()}-{state_key}"
        template = models.Template(title=title, content=content)
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"🧩 Auto-created template '{title}'")

    # ------------------------------------------------------------
    # 👥 Recipients (Clients + Admins)
    # ------------------------------------------------------------
    query = db.query(models.Client)
    base_filter = [models.Client.group_name == group_name]
    if connection_name and (connection_name.upper() != "ADMIN") and any(k in conn_type for k in ("vendo", "private")):
        base_filter.append(models.Client.connection_name == connection_name)

    recipients = query.filter(*base_filter).all()
    admins = query.filter(models.Client.connection_name.ilike("ADMIN"), models.Client.group_name == group_name).all()
    recipients = list({c.id: c for c in recipients + admins}.values())

    # ------------------------------------------------------------
    # 💬 Send Notifications
    # ------------------------------------------------------------
    for client in recipients:
        if getattr(client, "status", None) == BillingStatus.CUTOFF:
            logger.info(f"⏩ Skipping {client.name} – CUTOFF")
            continue

        final_msg = personalize_message(template.content, conn_type, connection_name, group_name, isp_label, client)
        if not final_msg:
            logger.warning(f"⚠️ Empty message for {client.name}")
            continue

        try:
            resp = send_message(client.messenger_id, final_msg)
            db.add(models.MessageLog(
                client_id=client.id,
                template_id=template.id,
                status=resp.get("message_id", "failed"),
            ))
            db.commit()
            logger.info(f"📩 Notified {client.name} ({connection_name}/{group_name})")
        except Exception as e:
            logger.error(f"❌ Failed sending to {client.name}: {e}")

# ============================================================
# 🧩 Helper: Build Auto Template Content
# ============================================================
def build_auto_template_content(conn_type, name, label, state_key, group_name):
    name_up = name or ""
    label = label or f"ISP '{name_up}'"

    if state_key == "SPIKING":
        if "private" in conn_type:
            return f"⚠️ '{name_up}' is experiencing instability (spiking). Please check cables or plug."
        if "vendo" in conn_type:
            return f"⚠️ VENDO link '{name_up}' is unstable. Please check indicator light."
        if "isp" in conn_type:
            return f"⚠️ {label} is unstable or experiencing latency."

    elif state_key == "DOWN":
        if "vendo" in conn_type:
            return f"⚠️ VENDO '{name_up}' is currently down. Please check cables and indicator lights."
        if "private" in conn_type:
            return f"⚠️ '{name_up}' is currently down. Kindly inspect cables and plugs."
        if "isp" in conn_type:
            return f"⚠️ {label} is currently down. Please monitor the provider."

    elif state_key == "UP":
        if "vendo" in conn_type:
            return f"✅ VENDO '{name_up}' is now up and running smoothly."
        if "private" in conn_type:
            return f"✅ '{name_up}' is now up and stable."
        if "isp" in conn_type:
            return f"✅ {label} is back online. Service restored."

    elif state_key == "UP" and last_state.get(f"{name_up}_{group_name}") == "SPIKING":
        return f"✅ {label} is now stable again."

    return None

# ============================================================
# 🧩 Helper: Personalize message per client
# ============================================================
def personalize_message(content, conn_type, name, group, isp_label, client):
    if not content:
        return None

    msg = content

    # Replace ISP markers
    if group == "G1":
        msg = msg.replace("'ISP1-CONNECTION'", "Primary Internet") \
                 .replace("'ISP2-CONNECTION'", "Secondary Internet") \
                 .replace("'ISP1-PING'", "Primary Internet") \
                 .replace("'ISP2-PING'", "Secondary Internet")
    elif group == "G2":
        msg = msg.replace("'ISP1-CONNECTION'", "PLDT") \
                 .replace("'ISP1-PING'", "PLDT")

    # Remove “Your connection” for ISP-type
    if "isp" in conn_type:
        msg = msg.replace("Your connection ", "").strip()

    # Adjust for admins
    if (client.connection_name or "").upper() == "ADMIN":
        msg = msg.replace("Your connection ", "").replace("Your vendo link ", "").strip()
    elif not "isp" in conn_type and name and name in msg and "Your connection" not in msg:
        # Add "Your connection" prefix
        idx = msg.find(name)
        if idx != -1:
            quote_idx = msg.rfind("'", 0, idx)
            insert_pos = quote_idx if quote_idx != -1 else idx
            msg = msg[:insert_pos] + "Your connection " + msg[insert_pos:]

    return msg.strip()


# ============================================================
# ⏳ Debounced Notification
# ============================================================
def schedule_notify(state_key, connection_name, group_name, new_state):
    if new_state == "SPIKING":
        logger.info(f"[{state_key}] Skipping delayed schedule for SPIKING")
        return

    def task():
        logger.info(f"[{state_key}] Waiting {DELAY}s before confirming {new_state}")
        time.sleep(DELAY)
        if last_state.get(state_key) == new_state:
            if notified_state.get(state_key) != new_state:
                with SessionLocal() as db:
                    notify_clients(db, connection_name, group_name, new_state)
                    notified_state[state_key] = new_state
            else:
                logger.info(f"[{state_key}] {new_state} already notified, skipping")
        else:
            logger.info(f"[{state_key}] State changed before {DELAY}s expired, cancelling")

    threading.Thread(target=task, daemon=True).start()

# ============================================================
# 🧩 Core State Processor (Spam-Protected & Fixed)
# ============================================================
def process_rule(db, client, connection_name, last_state_value, group_name, ws_manager=None):
    key = f"{connection_name}_{group_name}"

    # 🧩 Ignore if state hasn't changed (prevents rebroadcast spam)
    if last_state.get(key) == last_state_value:
        return

    # 🆕 SPIKING handling with debounce + safe placeholder broadcast
    if last_state_value == "SPIKING":
        last_time = spiking_active.get(key, 0)
        if time.time() - last_time < SPIKING_DEBOUNCE_SECONDS:
            logger.info(f"⏩ Ignoring duplicate SPIKING within {SPIKING_DEBOUNCE_SECONDS}s for {key}")
            return

        logger.info(f"⚠️ {key} detected SPIKING")

        placeholder = client or type(
            "Placeholder", (), {"id": 0, "messenger_id": None, "name": "Unknown"}
        )()

        broadcast_state_change(ws_manager, placeholder, connection_name, "SPIKING")

        if notified_state.get(key) != "SPIKING":
            notify_clients(db, connection_name, group_name, "SPIKING")
            notified_state[key] = "SPIKING"
            spiking_active[key] = time.time()
        last_state[key] = "SPIKING"
        return

    # 🧩 SPIKING → UP recovery handling
    if last_state.get(key) == "SPIKING" and last_state_value == "UP":
        def recovery_task():
            time.sleep(RECOVERY_STABLE_SECONDS)
            with SessionLocal() as db2:
                if last_state.get(key) == "UP" and spiking_active.get(key):
                    notify_clients(db2, connection_name, group_name, "UP")
                    logger.info(f"✅ Sent recovery message for {key}")
                    spiking_active.pop(key, None)
                    notified_state[key] = "UP"

        threading.Thread(target=recovery_task, daemon=True).start()

    # 🔄 Normal state change handling
    if client and client.state != last_state_value:
        logger.info(f"🔄 {client.name} ({connection_name}/{group_name}) {client.state} → {last_state_value}")
        broadcast_state_change(ws_manager, client, connection_name, last_state_value)
        if last_state_value not in ["SPIKING"]:
            schedule_notify(key, connection_name, group_name, last_state_value)
        client.state = last_state_value
        db.add(client)
    else:
        # ⚡ Broadcast only if previous state differs
        prev_state = last_state.get(key)
        if prev_state != last_state_value:
            placeholder = client or type(
                "Placeholder", (), {"id": 0, "messenger_id": None, "name": "Unknown"}
            )()
            broadcast_state_change(ws_manager, placeholder, connection_name, last_state_value)

    last_state[key] = last_state_value

# ============================================================
# 📡 WebSocket Broadcaster (Safe Fallback)
# ============================================================
def broadcast_state_change(ws_manager, client, connection_name, state_value):
    """Safely broadcast state changes to all connected WebSocket clients."""
    try:
        if not ws_manager:
            logger.debug(f"🕸️ No ws_manager available — skipping broadcast for {connection_name}")
            return

        payload = {
            "client_id": getattr(client, "id", 0),
            "client_name": getattr(client, "name", "Unknown"),
            "connection_name": connection_name,
            "state": state_value,
            "timestamp": time.time(),
        }

        # Send to all active WebSocket clients
        ws_manager.broadcast(payload)
        logger.info(f"📢 Broadcasted {state_value} for {connection_name}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to broadcast state for {connection_name}: {e}")


# ============================================================
# 🔁 Polling Loop
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

        # 🆕 Deduplicate rules by comment
        seen = set()
        unique_rules = []
        for rule in rules:
            comment = rule.get("comment") or rule.get("host")
            if comment not in seen:
                seen.add(comment)
                unique_rules.append(rule)
        rules = unique_rules

        with SessionLocal() as db:
            try:
                for rule in rules:
                    connection_name = rule.get("comment") or rule.get("host")
                    state_val = (rule.get("status") or "UNKNOWN").upper()
                    key = f"{connection_name}_{group_name}"
                    now = time.time()

                    history = [(t, s) for (t, s) in change_history.get(key, []) if now - t < FLAP_WINDOW]
                    if not history or history[-1][1] != state_val:
                        history.append((now, state_val))
                    change_history[key] = history

                    if len(history) >= FLAP_THRESHOLD and len({s for _, s in history}) > 1:
                        state_val = "SPIKING"
                        change_history[key] = []
                        logger.info(f"🚨 Detected SPIKING for {connection_name} ({group_name}) history={history}")

                    client = db.query(models.Client).filter(models.Client.connection_name == connection_name).first()
                    effective_group = getattr(client, "group_name", group_name)
                    process_rule(db, client, connection_name, state_val, effective_group, ws_manager)

                db.commit()
            except Exception as e:
                db.rollback()
                logger.error(f"❌ Error polling {host}: {e}")

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

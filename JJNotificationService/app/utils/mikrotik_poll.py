# app/utils/mikrotik_poll.py
import time
import threading
import logging
import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("mikrotik_poll")
logger.setLevel(logging.INFO)

# ============================================================
# 🔧 Router mapping (configurable via environment variable)
# ============================================================
default_map = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or default_map
    logger.info(f"✅ Loaded router map: {ROUTER_MAP}")
except json.JSONDecodeError:
    ROUTER_MAP = default_map
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON format, using defaults.")

# ============================================================
# DB and debounce
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


last_state = {}       # Last observed state (UP/DOWN)
notified_state = {}   # Last state actually notified
timers = {}
DELAY = 180  # seconds before sending notification


# ============================================================
# Notification helpers
# ============================================================
def notify_clients(db: Session, template_name: str, connection_name: str = None,
                   group_name: str = None):
    """Send messages to clients filtered by connection/group using a template.
       If the template does not exist, create it automatically with default content.
    """
    template = db.query(models.Template).filter(
        models.Template.title == template_name).first()
    if not template:
        logger.warning(f"Template '{template_name}' not found, creating it automatically")

        connection_type = (connection_name or "").lower()
        content = f"Notification: {template_name}"

        if template_name.endswith("DOWN"):
            if "private" in connection_type:
                content = "Your PRIVATE connection is currently down. Kindly check if the cables are properly connected and if all indicator lights are on."
            elif "vendo" in connection_type:
                content = "Your VENDO is currently down. Kindly check if the cables are properly connected and if all indicator lights are on."
            else:
                content = "Your connection is currently down. Kindly check the cables and indicator lights."
        elif template_name.endswith("UP"):
            if "private" in connection_type:
                content = "Your PRIVATE connection is up and running."
            elif "vendo" in connection_type:
                content = "Your VENDO is up and running."
            else:
                content = "Your connection is up and running."

        template = models.Template(title=template_name, content=content)
        db.add(template)
        db.commit()
        db.refresh(template)

    query = db.query(models.Client)
    if connection_name:
        query = query.filter(models.Client.connection_name == connection_name)
    if group_name:
        query = query.filter(models.Client.group_name == group_name)

    clients = query.all()
    for client in clients:
        if getattr(client, "status", None) == BillingStatus.CUTOFF:
          logger.info(
            f"⏩ Skipping {client.name} ({connection_name}) – status is CUTOFF")
          continue  # Skip clients who are cut off

        resp = send_message(client.messenger_id, template.content)
        log = models.MessageLog(
            client_id=client.id,
            template_id=template.id,
            status=resp.get("message_id", "failed"),
        )
        db.add(log)
        db.commit()
        logger.info(f"📩 Notified {client.name} ({connection_name}) with '{template_name}'")


def schedule_notify(state_key: str, template_name: str, connection_name: str, group_name: str, new_state: str):
    """Run notify after a delay in background thread to avoid flapping."""
    def task():
        logger.info(f"[{state_key}] Waiting {DELAY}s before confirming {new_state}")
        time.sleep(DELAY)
        if last_state.get(state_key) == new_state:
            prev_notified = notified_state.get(state_key)
            if prev_notified != new_state:
                logger.info(f"[{state_key}] Stable {new_state} → sending {template_name}")
                db = SessionLocal()
                try:
                    notify_clients(db, template_name, connection_name, group_name)
                    notified_state[state_key] = new_state
                finally:
                    db.close()
            else:
                logger.info(f"[{state_key}] {new_state} already notified, skipping")
        else:
            logger.info(f"[{state_key}] State changed before {DELAY}s expired, cancelling")

    if timers.get(state_key) and timers[state_key].is_alive():
        logger.info(f"[{state_key}] Cancelling old timer")
    t = threading.Thread(target=task, daemon=True)
    timers[state_key] = t
    t.start()


# ============================================================
# WebSocket helper
# ============================================================
def broadcast_state_change(ws_manager, client: models.Client,
                           connection_name: str, new_state: str):
    """Broadcast state changes to frontend via WebSocket manager."""
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
# Core processing
# ============================================================
def process_rule(db: Session, client: models.Client, connection_name: str,
                 last_state_value: str, group_name: str, ws_manager=None):
    """Handles state change detection, DB update, notifications, and broadcasting."""
    key = f"{connection_name}_{group_name}"

    if client:
        if client.state != last_state_value:
            logger.info(f"🔄 {client.name} ({connection_name}) {client.state} → {last_state_value}")

            broadcast_state_change(ws_manager, client, connection_name, last_state_value)

            template_name = f"{connection_name}-{last_state_value}"
            schedule_notify(key, template_name, connection_name, group_name, last_state_value)

            client.state = last_state_value
            db.add(client)
    else:
        broadcast_state_change(
            ws_manager,
            models.Client(id=0, messenger_id=None, name="Unknown"),
            connection_name,
            last_state_value,
        )

    last_state[key] = last_state_value


# ============================================================
# Polling logic
# ============================================================
def poll_netwatch(host: str, username: str, password: str, interval: int = 30,
                  ws_manager=None, group_name: str = None):
    """Polls MikroTik Netwatch rules every `interval` seconds and updates DB."""
    mikrotik = MikroTikClient(host, username, password)

    while True:
        if not mikrotik.ensure_connection():
            logger.warning(f"❌ Cannot connect to {host}, retrying in {interval}s...")
            time.sleep(interval)
            continue

        rules = mikrotik.get_netwatch()
        if not rules:
            logger.warning(f"⚠️ No Netwatch rules found for {host}")
            time.sleep(interval)
            continue

        db: Session = next(get_db())
        try:
            for rule in rules:
                connection_name = rule.get("comment") or rule.get("host")
                last_state_value = (rule.get("status") or "unknown").upper()

                client = db.query(models.Client).filter(
                    models.Client.connection_name == connection_name
                ).first()

                effective_group = getattr(client, "group_name", None) or group_name or "default"

                process_rule(
                    db,
                    client,
                    connection_name,
                    last_state_value,
                    effective_group,
                    ws_manager,
                )
                db.commit()

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error updating client states for {host}: {e}")
        finally:
            db.close()

        time.sleep(interval)


# ============================================================
# Start polling threads per router group
# ============================================================
def start_polling(username: str, password: str, interval: int = 30, ws_manager=None):
    """Start Netwatch polling for each MikroTik router by group."""
    for group_name, host in ROUTER_MAP.items():
        thread = threading.Thread(
            target=poll_netwatch,
            args=(host, username, password, interval, ws_manager, group_name),
            daemon=True,
        )
        thread.start()
        logger.info(f"✅ Started Netwatch polling for group '{group_name}' at {host}")

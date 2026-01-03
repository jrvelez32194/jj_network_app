import os
import json
import asyncio
import logging
import time
from typing import Dict, Optional, List
from sqlalchemy.orm import Session

from fastapi import FastAPI

from app.database import SessionLocal
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("mikrotik_poll_async")
logger.setLevel(logging.INFO)

app = FastAPI()

# ============================================================
# Configuration
# ============================================================
class Config:
    POLL_INTERVAL = 30
    NOTIFY_DELAY = 90
    COOLDOWN = 120
    SPIKE_WINDOW = 180
    SPIKE_THRESHOLD = 3
    SPIKE_ESCALATE_SECONDS = 10 * 60
    HOLD_LEVELS = [(3, 3*60), (5, 5*60), (8, 8*60)]
    EARLY_SPIKE_WINDOW = 3 * 60
    EARLY_SPIKE_THRESHOLD = 3
    STABLE_CLEAR_WINDOW = 3 * 60

# ============================================================
# Router map
# ============================================================
default_map = {"G1": "192.168.4.1", "G2": "10.147.18.20"}
ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or default_map

def load_router_map() -> Dict[str, str]:
    try:
        return ROUTER_MAP
    except Exception:
        return default_map

# ============================================================
# Async state and debounce
# ============================================================
class PollState:
    def __init__(self):
        self.last_state: Dict[str, str] = {}
        self.notified_state: Dict[str, str] = {}
        self.pending_tasks: Dict[str, asyncio.Task] = {}
        self.flip_history: Dict[str, Dict] = {}
        self.cooldown_state: Dict[str, float] = {}
        self.group_router_status: Dict[str, str] = {}
        self.lock = asyncio.Lock()

STATE = PollState()

# ============================================================
# Helper functions for parsing template keys
# ============================================================
def parse_template(name: str) -> dict:
    parts = name.upper().replace("_", "-").split("-")
    return {
        "event": "UP" if "UP" in parts else "DOWN",
        "metric": (
            "PING" if "PING" in parts else
            "CONNECTION" if "CONNECTION" in parts else
            "PRIVATE" if "PRIVATE" in parts else
            "VENDO" if "VENDO" in parts else None
        ),
        "is_spike": "SPIKE" in parts,
        "group": next((p for p in parts if p.startswith("G")), None),
    }

def compose_message(template: str, client_conn_name: str, client_is_admin: bool) -> str:
    ctx = parse_template(template)
    status = "UP" if ctx["event"] == "UP" else "DOWN"
    return f"📡 {client_conn_name}\n⚠ Status: {status}"

# ============================================================
# WebSocket broadcast
# ============================================================
async def broadcast_state_change(ws_manager, client: models.Client,
                                 connection_name: str, new_state: str):
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
        await ws_manager.safe_broadcast(payload)
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")

# ============================================================
# Notify clients
# ============================================================
def notify_clients(db: Session, template: str,
                   connection_name: str = None, group: str = None):
    clients = db.query(models.Client).filter(
        models.Client.connection_name.ilike(f"%{connection_name}%")
    ).all()

    for client in clients:
        msg = compose_message(template, client.connection_name or "Unknown", False)
        try:
            resp = send_message(client.messenger_id, msg)
            status = resp.get("message_id", "failed")
        except Exception:
            status = "failed"
        db.add(models.MessageLog(client_id=client.id, template_id=0, status=status))
    db.commit()

# ============================================================
# Async notify with debounce & spike handling
# ============================================================
async def schedule_notify(state_key: str, template: str,
                          connection_name: str, group: str, new_state: str):
    await asyncio.sleep(Config.NOTIFY_DELAY)

    async with STATE.lock:
        if STATE.last_state.get(state_key) != new_state:
            STATE.pending_tasks.pop(state_key, None)
            return

    db = SessionLocal()
    try:
        notify_clients(db, template, connection_name, group)
        STATE.notified_state[state_key] = new_state
    finally:
        db.close()

    async with STATE.lock:
        STATE.pending_tasks.pop(state_key, None)

async def process_rule(db: Session, connection: str, state: str,
                       template: str, group: str):
    key = f"{group}:{connection}"
    async with STATE.lock:
        last = STATE.last_state.get(key)
        if last == state:
            return
        STATE.last_state[key] = state
        if key in STATE.pending_tasks:
            STATE.pending_tasks[key].cancel()
        task = asyncio.create_task(schedule_notify(key, template, connection, group, state))
        STATE.pending_tasks[key] = task

# ============================================================
# Polling loop
# ============================================================
async def poll_group(host: str, group: str, username: str, password: str):
    mikrotik = MikroTikClient(host, username, password)
    STATE.group_router_status.setdefault(group, None)

    while True:
        try:
            connected = await asyncio.to_thread(mikrotik.ensure_connection)
            if not connected:
                prev = STATE.group_router_status.get(group)
                if prev != "DOWN":
                    logger.warning(f"🚨 Mikrotik {host} unreachable, marking group DOWN")
                    db = SessionLocal()
                    try:
                        affected = db.query(models.Client).filter(
                            models.Client.group_name == group
                        ).all()
                        for c in affected:
                            c.state = "DOWN"
                            db.add(c)
                        db.commit()
                    finally:
                        db.close()
                    STATE.group_router_status[group] = "DOWN"
                await asyncio.sleep(Config.POLL_INTERVAL)
                continue

            # Router is reachable
            STATE.group_router_status[group] = "UP"
            rules = await asyncio.to_thread(mikrotik.get_netwatch)
            db = SessionLocal()
            try:
                for rule in rules or []:
                    connection = (rule.get("comment") or rule.get("host") or "UNKNOWN").replace("_", "-")
                    state_val = (rule.get("status") or "UNKNOWN").upper()
                    template = rule.get("up-script") or rule.get("down-script") or ""
                    await process_rule(db, connection, state_val, template, group)
                db.commit()
            finally:
                db.close()

        except Exception as e:
            logger.error(f"Polling error for {group}: {e}")

        await asyncio.sleep(Config.POLL_INTERVAL)

# ============================================================
# Startup
# ============================================================
@app.on_event("startup")
async def start_polling(username: str, password: str, interval: int = 30,
                        ws_manager=None, router_map=None):
    routers = router_map or load_router_map()
    for group, host in routers.items():
        asyncio.create_task(poll_group(host, group, username, password))
    logger.info("✅ MikroTik async pollers started")

import time
import threading
import logging
import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal, get_db
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("netwatch poll")
logger.setLevel(logging.INFO)

# Track per-group router status to avoid repeated group messages
# Values: "UP" | "DOWN" | None (unknown)
group_router_status: dict[str, str] = {}


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


def net_watch_poll(    host: str,
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    group_name: str = None):

    from sqlalchemy import or_

    mikrotik = MikroTikClient(host, username, password)

    # initialize group status if not present
    if group_name and group_name not in group_router_status:
      group_router_status[group_name] = None

    connected = False

    db: Session = next(get_db())
    try:
      connected = mikrotik.ensure_connection()
    except Exception as e:
      logger.error(f"Error while checking connection to {host}: {e}")
      connected = False


    # Proceed with normal Netwatch rules
    rules = mikrotik.get_netwatch()
    if not rules:
      logger.warning(f"⚠️ No Netwatch rules found for {host}")
      db.close()
      time.sleep(interval)
      continue



# ============================================================
# Start polling threads per router group
# ============================================================
def start_polling(username: str, password: str, interval: int = 30,
    ws_manager=None, router_map=None):
    routers = router_map or ROUTER_MAP

    initialize_state_cache()

    for group_name, host in routers.items():
        # initialize group_router_status
        group_router_status.setdefault(group_name, None)

        thread = threading.Thread(
            target=poll_netwatch,
            args=(host, username, password, interval, ws_manager, group_name),
            daemon=True,
        )
        thread.start()
        logger.info(
            f"✅ Started Netwatch polling for group '{group_name}' at {host}")

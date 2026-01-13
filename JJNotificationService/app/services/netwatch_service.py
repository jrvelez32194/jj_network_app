import time
import logging
import os
import json
import traceback
from typing import Dict, Optional

from sqlalchemy.orm import Session
from app.database import get_db
from app.models import  ConnectionState
from app.services.client_service import (
    update_client_status,
    update_client_under_route_state,
    get_clients,
)
from app.services.netwatch_notification import send_notification
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("netwatch_sync")
logger.setLevel(logging.INFO)

# ============================================================
# Router mapping
# ============================================================
DEFAULT_ROUTER_MAP = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

group_router_status: Dict[str, ConnectionState] = {}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or DEFAULT_ROUTER_MAP
    logger.info("✅ Loaded router map: %s", ROUTER_MAP)
except json.JSONDecodeError:
    ROUTER_MAP = DEFAULT_ROUTER_MAP
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON, using defaults")


# ============================================================
# Synchronous polling loop
# ============================================================
def netwatch_sync_loop(
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    router_map: Optional[Dict[str, str]] = None,
):
    routers = router_map or ROUTER_MAP

    # Initialize MikroTik clients
    mikrotik_clients: Dict[str, MikroTikClient] = {}
    for group, host in routers.items():
        try:
            mikrotik_clients[group] = MikroTikClient(host, username, password)
            logger.info("[%s] MikroTik initialized (%s)", group, host)
        except Exception as e:
            logger.error("[%s] MikroTik init failed: %s", group, e)

    logger.info("🚀 Netwatch sync loop started")

    while True:
        for group_name, mt_client in mikrotik_clients.items():
            db: Session | None = None
            try:
                db = next(get_db())  # Use sync session

                logger.debug("[%s] Poll cycle start", group_name)

                # ====================================================
                # Router DOWN
                # ====================================================
                if not mt_client.ensure_connection():
                    prev_state = group_router_status.get(group_name)
                    if prev_state != ConnectionState.DOWN:
                        logger.warning(
                            "[%s] Router unreachable (%s) → marking clients DOWN",
                            group_name,
                            mt_client.host,
                        )

                        update_client_under_route_state(
                            db=db,
                            group=group_name,
                            state=ConnectionState.DOWN,
                            ws_manager=ws_manager,
                        )

                        clients = get_clients(db, group_name)
                        send_notification(
                            db=db,
                            clients=clients,
                            is_router_down=True,
                            router_group=group_name,
                        )

                        group_router_status[group_name] = ConnectionState.DOWN
                    else:
                        logger.debug("[%s] Router still DOWN", group_name)
                    continue

                # ====================================================
                # Router RECOVERED
                # ====================================================
                if group_router_status.get(group_name) == ConnectionState.DOWN:
                    logger.info("[%s] Router recovered (%s)", group_name, mt_client.host)

                    update_client_under_route_state(
                        db=db,
                        group=group_name,
                        state=ConnectionState.UP,
                        ws_manager=ws_manager,
                    )

                    clients = get_clients(db, group_name)
                    send_notification(
                        db=db,
                        clients=clients,
                        is_router_down=False,
                        router_group=group_name,
                    )

                    group_router_status[group_name] = ConnectionState.UP

                # ====================================================
                # Netwatch rule processing
                # ====================================================
                rules = mt_client.get_netwatch() or []
                rule_states: Dict[str, ConnectionState] = {}

                for rule in rules:
                    name = rule.get("comment") or rule.get("host")
                    if not name:
                        continue
                    name = name.replace("_", "-")
                    raw = (rule.get("status") or "unknown").lower()
                    state = {"up": ConnectionState.UP, "down": ConnectionState.DOWN}.get(
                        raw, ConnectionState.UNKNOWN
                    )
                    rule_states[name] = state

                changed_clients = update_client_status(
                    db=db,
                    group=group_name,
                    rule_states=rule_states,
                    ws_manager=ws_manager,
                )

                send_notification(
                    db=db,
                    clients=changed_clients,
                    is_router_down=False,
                    router_group=group_name,
                )

            except Exception as e:
                logger.error(
                    "[%s] Netwatch error: %s\n%s",
                    group_name,
                    e,
                    traceback.format_exc(),
                )

            finally:
                if db:
                    db.close()

        time.sleep(interval)


# ============================================================
# Start helper
# ============================================================
def start_polling(
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    router_map: Optional[Dict[str, str]] = None,
):
    import threading
    threading.Thread(
        target=netwatch_sync_loop,
        args=(username, password, interval, ws_manager, router_map),
        daemon=True,
        name="netwatch-sync-worker",
    ).start()

    routers = router_map or ROUTER_MAP
    logger.info(
        "✅ Netwatch polling started for %d routers: %s",
        len(routers),
        list(routers.keys()),
    )

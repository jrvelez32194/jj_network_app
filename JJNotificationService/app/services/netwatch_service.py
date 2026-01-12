import asyncio
import logging
import os
import json
import traceback
from typing import Dict

from sqlalchemy.orm import Session

from app.database import SessionLocal
from app.models import ConnectionState
from app.services.client_service import (
    update_client_status,
    update_client_under_route_state,
)
from app.services.netwatch_notification import send_notification
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("netwatch_async")
logger.setLevel(logging.INFO)

# ============================================================
# 🔧 Router mapping (configurable via environment variable)
# ============================================================
DEFAULT_ROUTER_MAP = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

group_router_status: Dict[str, ConnectionState] = {}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or DEFAULT_ROUTER_MAP
    logger.info(f"✅ Loaded router map: {ROUTER_MAP}")
except json.JSONDecodeError:
    ROUTER_MAP = DEFAULT_ROUTER_MAP
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON format, using defaults.")


# ============================================================
# 🔄 Async Netwatch polling loop
# ============================================================
async def netwatch_async_loop(
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    router_map: dict[str, str] | None = None,
):
    routers = router_map or ROUTER_MAP

    # Create MikroTik clients once
    mikrotik_clients: dict[str, MikroTikClient] = {
        group: MikroTikClient(host, username, password)
        for group, host in routers.items()
    }

    logger.info("🚀 Netwatch async loop started")

    while True:
        for group_name, mt_client in mikrotik_clients.items():
            db: Session | None = None

            try:
                db = SessionLocal()

                # ------------------------------------------------
                # Router unreachable
                # ------------------------------------------------
                if not mt_client.ensure_connection():
                    prev_state = group_router_status.get(group_name)

                    if prev_state != ConnectionState.DOWN:
                        logger.warning(
                            f"🚨 Mikrotik for group {group_name} ({mt_client.host}) unreachable. "
                            f"Marking PRIVATE/VENDO as DOWN and notifying group."
                        )

                        clients = update_client_under_route_state(
                            db=db,
                            group=group_name,
                            state=ConnectionState.DOWN,
                            ws_manager=ws_manager,
                        )

                        send_notification(
                            db,
                            clients,
                            is_router_down=True,
                            router_group=group_name,
                        )

                        group_router_status[group_name] = ConnectionState.DOWN
                    else:
                        logger.debug(
                            f"[{group_name}] Router already DOWN, skipping duplicate handling."
                        )

                    continue  # move to next router

                # ------------------------------------------------
                # Router recovered
                # ------------------------------------------------
                prev_state = group_router_status.get(group_name)
                if prev_state == ConnectionState.DOWN:
                    logger.info(
                        f"🔺 Mikrotik for group {group_name} ({mt_client.host}) recovered."
                    )
                    group_router_status[group_name] = ConnectionState.UP

                # ------------------------------------------------
                # Normal Netwatch processing
                # ------------------------------------------------
                rules = mt_client.get_netwatch() or []

                rule_states: dict[str, str] = {}

                for rule in rules:
                    connection_name = rule.get("comment") or rule.get("host")
                    if not connection_name:
                        continue

                    connection_name = connection_name.replace("_", "-")
                    raw_status = (rule.get("status") or "unknown").lower()

                    if raw_status == "up":
                        state = ConnectionState.UP
                    elif raw_status == "down":
                        state = ConnectionState.DOWN
                    else:
                        state = ConnectionState.UNKNOWN

                    rule_states[connection_name] = state

                clients = update_client_status(
                    db=db,
                    group=group_name,
                    rule_states=rule_states,
                    ws_manager=ws_manager,
                )

                send_notification(
                    db,
                    clients,
                    is_router_down=False,
                    router_group=group_name,
                )

            except Exception as e:
                logger.error(
                    f"[{group_name}] Netwatch error: {e}\n{traceback.format_exc()}"
                )

            finally:
                if db:
                    db.close()

        await asyncio.sleep(interval)


# ============================================================
# 🔹 Start polling helper
# ============================================================
def start_polling(
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    router_map=None,
):
    asyncio.create_task(
        netwatch_async_loop(
            username=username,
            password=password,
            interval=interval,
            ws_manager=ws_manager,
            router_map=router_map,
        )
    )

    routers = router_map or ROUTER_MAP
    logger.info(f"✅ Netwatch async polling started for {len(routers)} routers")

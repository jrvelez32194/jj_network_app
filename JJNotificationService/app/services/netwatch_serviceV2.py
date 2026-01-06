import asyncio
import logging
import os
import json
import time
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("netwatch_async")
logger.setLevel(logging.INFO)

# Track per-router overall state (optional)
group_router_status: dict[str, str | None] = {}

# Track per-rule state
# Key: "{group}_{rule_comment}"
rule_router_status: dict[str, str | None] = {}

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
# 🔄 Single-thread async loop for all routers
# ============================================================
async def netwatch_async_loop(
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    router_map: dict[str, str] | None = None,
):
    """
    Polls all routers for Netwatch rules in a single async loop.
    Pushes state changes via WebSocket if ws_manager is provided.
    """
    routers = router_map or ROUTER_MAP

    # Create MikroTik clients once
    clients: dict[str, MikroTikClient] = {
        group: MikroTikClient(host, username, password)
        for group, host in routers.items()
    }

    # Initialize per-router and per-rule state
    for group_name in routers:
        group_router_status.setdefault(group_name, None)
        try:
            client = clients[group_name]
            rules = client.get_netwatch() or []
            for rule in rules:
                rule_comment = rule.get("comment")
                if rule_comment:
                    key = f"{group_name}_{rule_comment}"
                    rule_router_status.setdefault(key, None)
        except Exception as e:
            logger.warning(f"[{group_name}] Failed to initialize rule states: {e}")

    logger.info("🚀 Netwatch async loop started (per-rule tracking)")

    while True:
        for group_name, client in clients.items():
            try:
                # Ensure connection to router
                if not client.ensure_connection():
                    raise Exception("Unable to connect to router")

                rules = client.get_netwatch() or []

                for rule in rules:
                    rule_comment = rule.get("comment")
                    if not rule_comment:
                        continue

                    key = f"{group_name}_{rule_comment}"
                    status = rule.get("status")
                    router_state = "DOWN" if status == "down" else "UP"

                    previous_state = rule_router_status.get(key)

                    # Only act on state change
                    if router_state != previous_state:
                        rule_router_status[key] = router_state

                        logger.info(
                            f"[{group_name}] {rule_comment}: {previous_state} → {router_state}"
                        )

            except Exception as e:
                logger.error(f"[{group_name}] Netwatch error: {e}")

        # Sleep asynchronously between polls
        await asyncio.sleep(interval)


# ============================================================
# 🔹 Start polling helper (replaces old thread-based start_polling)
# ============================================================
def start_polling(username: str, password: str, interval: int = 30, ws_manager=None, router_map=None):
    asyncio.create_task(
        netwatch_async_loop(
            username=username,
            password=password,
            interval=interval,
            ws_manager=ws_manager,
            router_map=router_map
        )
    )
    routers = router_map or ROUTER_MAP
    logger.info(f"✅ Netwatch async polling started for {len(routers)} routers")

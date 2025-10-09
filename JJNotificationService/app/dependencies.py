import os
import json
from app.utils.mikrotik_config import MikroTikClient


def get_mikrotik_clients():
    """
    ✅ Return a list of MikroTikClient instances for all routers defined in ROUTER_MAP_JSON.
    Example .env:
      ROUTER_MAP_JSON={"G1":"192.168.4.1","G2":"10.147.18.20"}
    """
    routers = []

    router_map_str = os.getenv("ROUTER_MAP_JSON", "{}")
    try:
        router_map = json.loads(router_map_str)
    except json.JSONDecodeError:
        router_map = {}

    username = os.getenv("MIKROTIK_USER", "admin")
    password = os.getenv("MIKROTIK_PASS", "")

    for group, host in router_map.items():
        routers.append(
            {
                "group": group,
                "client": MikroTikClient(
                    host=host,
                    username=username,
                    password=password,
                ),
            }
        )

    return routers


def get_mikrotik(group: str | None = None, host: str | None = None):
    """
    ✅ Return a specific MikroTikClient by group name or host.
    - If group is provided, match group key (e.g., "G1").
    - If host is provided, match host IP (e.g., "192.168.4.1").
    - Otherwise, return the first router.
    """
    routers = get_mikrotik_clients()
    if not routers:
        raise ValueError("⚠️ No MikroTik routers configured in environment.")

    # Match by group name
    if group:
        for r in routers:
            if r["group"].upper() == group.upper():
                return r["client"]
        raise ValueError(f"⚠️ No MikroTik found for group '{group}'")

    # Match by host/IP
    if host:
        for r in routers:
            if r["client"].host == host:
                return r["client"]
        raise ValueError(f"⚠️ No MikroTik found with host '{host}'")

    # Default: first router
    return routers[0]["client"]

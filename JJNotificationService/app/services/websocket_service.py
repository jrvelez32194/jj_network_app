# ============================================================
# WebSocket helper
# ============================================================
import time
import logging

from app import models

logger = logging.getLogger("websocket")
logger.setLevel(logging.INFO)

def broadcast_state_change(ws_manager, client: models.Client,
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
        ws_manager.safe_broadcast(payload)
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")
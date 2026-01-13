import logging
from typing import Dict, List, Optional

from sqlalchemy import any_
from sqlalchemy.orm import Session

from app.models import Client, ClientStateHistory, ConnectionState
from app.services.websocket_service import broadcast_state_change

logger = logging.getLogger("client_service_sync")

# ============================================================
# Queries (sync)
# ============================================================
def get_clients(db: Session, group_name: str) -> List[Client]:
    return db.query(Client).filter(Client.group_name == group_name).all()

def get_clients_by_state(db: Session, group_name: str, state: ConnectionState) -> List[Client]:
    return (
        db.query(Client)
        .filter(
            Client.group_name == group_name,
            Client.connection_name.isnot(None),
            Client.connection_name != "",
            Client.state == state,
        )
        .all()
    )

# ============================================================
# Update clients based on Netwatch rules
# ============================================================
def update_client_status(
    db: Session,
    group: str,
    rule_states: Dict[str, ConnectionState],
    ws_manager=None,
) -> List[Client]:
    if not group:
        raise ValueError("group is required")

    clients = get_clients(db, group)
    if not clients:
        logger.info("[%s] No clients found", group)
        return []

    normalized_rules = {k.lower(): v for k, v in rule_states.items() if k}
    changed_clients: List[Client] = []

    for client in clients:
        if not client.connection_name:
            continue

        prev_state = client.state
        client_key = client.connection_name.lower()
        new_state = normalized_rules.get(client_key, ConnectionState.UNKNOWN)

        if prev_state == new_state:
            continue

        # Update client
        client.state = new_state
        db.add(client)

        # Persist history
        db.add(ClientStateHistory(client_id=client.id, prev_state=prev_state, new_state=new_state, reason="netwatch"))

        logger.info("[%s] %s (%s): %s → %s", group, client.name, client.connection_name, prev_state, new_state)
        changed_clients.append(client)

        # WebSocket broadcast (sync)
        if ws_manager:
            broadcast_state_change(ws_manager, client, client.connection_name, new_state)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[%s] Failed to commit netwatch updates", group)
        raise

    logger.debug("[%s] Clients updated: %d", group, len(changed_clients))
    return changed_clients


# ============================================================
# Bulk update for router DOWN/UP
# ============================================================
def update_client_under_route_state(
    db: Session,
    group: str,
    state: ConnectionState,
    ws_manager=None,
) -> List[Client]:
    if not group:
        raise ValueError("group is required")

    clients = get_clients(db, group)
    if not clients:
        logger.info("[%s] No clients found for bulk update", group)
        return []

    changed_clients: List[Client] = []
    reason = "router_down" if state == ConnectionState.DOWN else "router_up"

    for client in clients:
        if client.state == state:
            continue

        prev_state = client.state
        client.state = state
        db.add(client)

        db.add(ClientStateHistory(client_id=client.id, prev_state=prev_state, new_state=state, reason=reason))

        logger.info("[%s] %s (%s) bulk: %s → %s", group, client.name, client.connection_name, prev_state, state)
        changed_clients.append(client)

        # WebSocket broadcast (sync)
        if ws_manager:
            broadcast_state_change(ws_manager, client, client.connection_name, state)

    try:
        db.commit()
    except Exception:
        db.rollback()
        logger.exception("[%s] Failed to commit bulk updates", group)
        raise

    logger.debug("[%s] Bulk clients updated: %d", group, len(changed_clients))
    return changed_clients

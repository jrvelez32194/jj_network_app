from sqlalchemy.orm import Session
from app.models import Client
from app.services.websocket_service import broadcast_state_change

UNKNOWN_STATE = "UNKNOWN"


def get_clients(db: Session, group_name: str) -> list[Client]:
    return db.query(Client).filter(Client.group_name == group_name).all()


def get_clients_by_state(
    db: Session,
    group_name: str,
    state: str,
) -> list[Client]:
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


def update_client_status(
    db: Session,
    group: str,
    rule_states: dict[str, str],
    ws_manager=None,
) -> list[Client]:

    if not group:
        raise ValueError("group is required")

    clients = get_clients(db, group)
    if not clients:
        return []

    normalized_rules = {
        key.lower(): value
        for key, value in rule_states.items()
        if key
    }

    changed_clients: list[Client] = []

    for client in clients:
        if not client.connection_name:
            continue

        prev_state = client.state
        client_key = client.connection_name.lower()

        new_state = normalized_rules.get(
            client_key,
            UNKNOWN_STATE,
        )

        if prev_state == new_state:
            continue

        client.state = new_state
        db.add(client)
        changed_clients.append(client)

        if ws_manager:
            broadcast_state_change(
                ws_manager,
                client,
                client.connection_name,
                new_state,
            )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return changed_clients


def update_client_under_route_state(
    db: Session,
    group: str,
    state: str,
    ws_manager=None,
) -> list[Client]:

    if not group:
        raise ValueError("group is required")

    clients = get_clients(db, group)
    if not clients:
        return []

    changed_clients: list[Client] = []

    for client in clients:
        if client.state == state:
            continue

        client.state = state
        db.add(client)
        changed_clients.append(client)

        if ws_manager:
            broadcast_state_change(
                ws_manager,
                client,
                client.connection_name,
                state,
            )

    try:
        db.commit()
    except Exception:
        db.rollback()
        raise

    return changed_clients

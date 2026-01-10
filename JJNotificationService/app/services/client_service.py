from sqlalchemy.orm import Session
from app.models import Client
from app.services.websocket_service import broadcast_state_change


def update_client_status(
    db: Session,
    group: str,
    rule_states: dict[str, str],
    ws_manager=None,
) -> list[Client]:

    if not group:
        raise ValueError("group is required")

    clients = (
        db.query(Client)
        .filter(Client.group_name == group)
        .all()
    )

    if not clients:
        return []

    # Normalize rule keys once
    normalized_rules = {
        key.lower(): value
        for key, value in rule_states.items()
        if key
    }

    changed_clients: list[Client] = []

    for client in clients:
        prev_state = client.state
        client_key = client.connection_name.lower()

        # Determine new state
        if client_key in normalized_rules:
            new_state = normalized_rules[client_key]
        else:
            new_state = "UNKNOWN"

        # Apply only if changed
        if prev_state != new_state:
            client.state = new_state
            db.add(client)

            changed_clients.append(client)

            broadcast_state_change(
                ws_manager,
                client,
                client.connection_name,
                new_state,
            )

    db.commit()
    return changed_clients

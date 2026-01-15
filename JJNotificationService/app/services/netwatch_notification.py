import logging
import threading
import time
from queue import Queue, Empty
from typing import List, Optional

from sqlalchemy.orm import Session

from app.database import get_db
from app.models import Client, ClientStateHistory
from app.schemas import ConnectionState, BillingStatus
from app.services.template_service import get_template
from app.utils.messengerV2 import send_message

logger = logging.getLogger("notification_service")

# ============================================================
# Constants
# ============================================================
ISP_KEYWORD = "ISP"
VENDO_KEYWORD = "VENDO"
PRIVATE_KEYWORD = "PRIVATE"

OBSERVATION_WINDOW = 60
RATE_LIMIT_PER_GROUP = 5
WORKER_SLEEP = 0.1
ADMIN_DEDUPE_WINDOW = 60
UP_THROTTLE_WINDOW = 30

PLACEHOLDER_REPLACEMENTS = {
    PRIVATE_KEYWORD: "Your",
    VENDO_KEYWORD: "Vendo",
}

# ============================================================
# Thread-safe runtime state
# ============================================================
group_queues: dict[str, Queue] = {}
group_last_tick: dict[str, float] = {}
group_sent_count: dict[str, int] = {}

queue_lock = threading.Lock()
rate_lock = threading.Lock()

admin_dedupe_cache: dict[tuple, float] = {}
up_throttle_cache: dict[int, float] = {}

# ============================================================
# Queue worker
# ============================================================
def start_queue_worker() -> None:
    threading.Thread(
        target=_queue_worker_loop,
        daemon=True,
        name="notification-queue-worker",
    ).start()


def _queue_worker_loop() -> None:
    while True:
        try:
            now = time.time()
            with queue_lock:
                groups_snapshot = list(group_queues.items())

            for group, queue in groups_snapshot:
                _reset_rate_limit_if_needed(group, now)
                _process_group_queue(group, queue)

        except Exception:
            logger.exception("Notification worker crashed, retrying in 1s")
            time.sleep(1)

        time.sleep(WORKER_SLEEP)


def _reset_rate_limit_if_needed(group: str, now: float) -> None:
    with rate_lock:
        last_tick = group_last_tick.get(group, 0)
        if now - last_tick >= 1:
            group_last_tick[group] = now
            group_sent_count[group] = 0


def _process_group_queue(group: str, queue: Queue) -> None:
    while True:
        with rate_lock:
            if group_sent_count.get(group, 0) >= RATE_LIMIT_PER_GROUP:
                return

        try:
            client, content = queue.get_nowait()
        except Empty:
            return

        try:
            db = next(get_db())
            send_message(db, client.messenger_id, f"From {client.connection_name}", content)
            logger.info("[%s] Sent → %s (%s)", group, client.name, client.connection_name)
        except Exception:
            logger.exception("[%s] Failed to send message to %s", group, client.name)

        with rate_lock:
            group_sent_count[group] = group_sent_count.get(group, 0) + 1

# ============================================================
# Public entry
# ============================================================
def send_notification(db: Session, clients: List[Client], is_router_down: bool, router_group: str) -> None:
    if is_router_down:
        _notify_router_down(db, router_group)
        return

    for client in clients:
        if not client.connection_name:
            continue

        state = evaluate_notification_state(db, client)
        if not state:
            continue

        if _is_up_throttled(client, state):
            continue

        prefix = extract_prefix(client.connection_name)
        template_key = resolve_template_key(client, prefix, state)

        template = get_template(db, client.group_name, template_key, state)
        if not template:
            logger.warning("[%s] Missing template %s (%s)", client.group_name, template_key, state)
            continue

        dispatch_notification(db, client, prefix, template.content, client.group_name, state)


def _notify_router_down(db: Session, group: str) -> None:
    template = get_template(db, group, ISP_KEYWORD, ConnectionState.DOWN)
    if not template:
        logger.warning("[%s] Missing ISP DOWN template", group)
        return

    logger.info("[%s] Router DOWN → ISP broadcast", group)
    notify_all_under_group(db, template.content, group)


def _is_up_throttled(client: Client, state: ConnectionState) -> bool:
    if state != ConnectionState.UP:
        return False

    last_up = up_throttle_cache.get(client.id, 0)
    if time.time() - last_up < UP_THROTTLE_WINDOW:
        logger.debug("[%s] UP throttled for %s", client.group_name, client.connection_name)
        return True

    up_throttle_cache[client.id] = time.time()
    return False

# ============================================================
# Notification decision logic
# ============================================================
def evaluate_notification_state(db: Session, client: Client) -> Optional[ConnectionState]:
    history = (
        db.query(ClientStateHistory)
        .filter(ClientStateHistory.client_id == client.id)
        .order_by(ClientStateHistory.created_at.desc())
        .limit(2)
        .all()
    )

    if len(history) < 2:
        return client.state if client.state != ConnectionState.UP else None

    prev = history[1]
    elapsed = time.time() - prev.created_at.timestamp()

    if prev.new_state != client.state and client.state != ConnectionState.UP and elapsed <= OBSERVATION_WINDOW:
        return ConnectionState.SPIKE if prev.new_state != ConnectionState.SPIKE else None

    if client.state == ConnectionState.DOWN:
        return ConnectionState.DOWN if prev.new_state != ConnectionState.DOWN else None

    if client.state == ConnectionState.UP and prev.new_state in {ConnectionState.DOWN, ConnectionState.SPIKE, ConnectionState.UNKNOWN}:
        return ConnectionState.UP

    return None

# ============================================================
# Template resolution
# ============================================================
def resolve_template_key(client: Client, prefix: str, state: ConnectionState) -> str:
    if state == ConnectionState.SPIKE and prefix == PRIVATE_KEYWORD and client.status in {BillingStatus.CUTOFF, BillingStatus.LIMITED}:
        return f"{PRIVATE_KEYWORD}-UNPAID-SPIKE"
    return prefix


def extract_prefix(connection_name: str) -> str:
    if not connection_name:
        return ""
    # ISP messages should preserve full connection_name for broadcast
    if connection_name.startswith(ISP_KEYWORD):
        return connection_name
    return connection_name.split("-", 1)[0]

# ============================================================
# Dispatching
# ============================================================
def dispatch_notification(db: Session, client: Client, prefix: str, content: str, group: str, state: ConnectionState) -> None:
    # ------------------------------
    # ISP → broadcast to all clients under the group
    # ------------------------------
    if prefix.startswith(ISP_KEYWORD):
        notify_all_under_group(db, content, group)
        return  # Stop here; do NOT call admin dedupe

    # ------------------------------
    # Non-ISP → apply placeholders for PRIVATE/VENDO
    # ------------------------------
    client_content = _apply_placeholder(prefix, content, client.connection_name)
    enqueue_message(client, client_content, group)

    # ------------------------------
    # Admin notifications (deduped)
    # ------------------------------
    notify_admin_deduped(db, content, group, client.connection_name, prefix, state)


def _apply_placeholder(prefix: str, content: str, connection_name: str) -> str:
    if prefix.startswith(ISP_KEYWORD):
        return content  # skip ISP
    placeholder = PLACEHOLDER_REPLACEMENTS.get(prefix)
    if not placeholder:
        return content
    replacement = f"Your {connection_name}" if prefix == PRIVATE_KEYWORD else connection_name
    return content.replace(placeholder, replacement)

# ============================================================
# Queue helpers
# ============================================================
def enqueue_message(client: Client, content: str, group: str) -> None:
    with queue_lock:
        queue = group_queues.setdefault(group, Queue())
        queue.put((client, content))

# ============================================================
# Admin notifications (deduped)
# ============================================================
def notify_admin_deduped(db: Session, content: str, group: str, connection_name: str, prefix: str, state: ConnectionState) -> None:
    if prefix.startswith(ISP_KEYWORD):
        return  # never notify admin for ISP

    key = (group, prefix, connection_name, state)
    now = time.time()
    if now - admin_dedupe_cache.get(key, 0) < ADMIN_DEDUPE_WINDOW:
        return
    admin_dedupe_cache[key] = now

    content = content.replace(PLACEHOLDER_REPLACEMENTS.get(prefix, ""), connection_name)

    admins = db.query(Client).filter(Client.group_name == group, Client.connection_name == "ADMIN").all()
    for admin in admins:
        enqueue_message(admin, content, group)

# ============================================================
# ISP broadcast
# ============================================================
def notify_all_under_group(db: Session, content: str, group: str) -> None:
    clients = db.query(Client).filter(Client.group_name == group).all()
    for client in clients:
        # Skip offline clients or cut-off accounts
        if client.state == ConnectionState.DOWN or client.status == BillingStatus.CUTOFF:
            continue
        enqueue_message(client, content, group)

# ============================================================
# Boot
# ============================================================
start_queue_worker()

import logging
import threading
import time
from collections import defaultdict
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

OBSERVATION_WINDOW = 60       # seconds for spike detection
RATE_LIMIT_PER_GROUP = 5      # max messages per second per group
WORKER_SLEEP = 0.1
ADMIN_DEDUPE_WINDOW = 60      # seconds
UP_THROTTLE_WINDOW = 30       # seconds

PLACEHOLDER_REPLACEMENTS = {
    PRIVATE_KEYWORD: "Your",
    VENDO_KEYWORD: "Vendo",
}

# ============================================================
# Thread-safe runtime state
# ============================================================
group_queues: dict[str, Queue] = defaultdict(Queue)
group_last_tick: dict[str, float] = defaultdict(lambda: 0.0)
group_sent_count: dict[str, int] = defaultdict(int)
lock = threading.Lock()  # protects sent_count & last_tick

admin_dedupe_cache: dict[tuple, float] = {}
up_throttle_cache: dict[int, float] = {}

# ============================================================
# Queue worker
# ============================================================
def start_queue_worker():
    """Start a background thread for sending messages."""
    threading.Thread(
        target=_queue_worker_loop,
        daemon=True,
        name="notification-queue-worker"
    ).start()


def _queue_worker_loop():
    while True:
        try:
            now = time.time()
            for group, queue in group_queues.items():
                # Reset per-second counter
                with lock:
                    if now - group_last_tick[group] >= 1:
                        group_last_tick[group] = now
                        group_sent_count[group] = 0

                while True:
                    with lock:
                        if group_sent_count[group] >= RATE_LIMIT_PER_GROUP:
                            break  # reached rate limit

                    try:
                        client, content = queue.get_nowait()
                    except Empty:
                        break  # no more messages

                    try:
                        db = next(get_db())
                        send_message(db, client.messenger_id, f"From {client.connection_name}" , content)
                        logger.info("[%s] Sent → %s (%s)", group, client.name, client.connection_name)
                    except Exception:
                        logger.exception("[%s] Failed to send message to %s", group, client.name)

                    with lock:
                        group_sent_count[group] += 1

        except Exception:
            logger.exception("Notification worker crashed, retrying in 1s")
            time.sleep(1)

        time.sleep(WORKER_SLEEP)


# ============================================================
# Public entry
# ============================================================
def send_notification(db: Session, clients: List[Client], is_router_down: bool, router_group: str):
    """Main notification entry point."""

    if is_router_down:
        template = get_template(db, router_group, ISP_KEYWORD, ConnectionState.DOWN)
        if not template:
            logger.warning("[%s] Missing ISP DOWN template", router_group)
            return
        logger.info("[%s] Router DOWN → ISP broadcast", router_group)
        notify_all_under_group(db, template.content, router_group)
        return

    for client in clients:
        if not client.connection_name:
            continue

        notify_state = evaluate_notification_state(db, client)
        if not notify_state:
            continue

        # UP throttling
        if notify_state == ConnectionState.UP:
            last_up = up_throttle_cache.get(client.id, 0)
            if time.time() - last_up < UP_THROTTLE_WINDOW:
                logger.debug("[%s] UP throttled for %s", client.group_name, client.connection_name)
                continue
            up_throttle_cache[client.id] = time.time()

        prefix = extract_prefix(client.connection_name)
        template_key = resolve_template_key(client, prefix, notify_state)
        template = get_template(db, client.group_name, template_key, notify_state)
        if not template:
            logger.warning("[%s] Missing template %s (%s)", client.group_name, template_key, notify_state)
            continue

        dispatch_notification(db, client, prefix, template.content, client.group_name, notify_state)


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

    # SPIKE detection
    if prev.new_state != client.state and client.state != ConnectionState.UP and elapsed <= OBSERVATION_WINDOW:
        return ConnectionState.SPIKE if prev.new_state != ConnectionState.SPIKE else None

    # DOWN
    if client.state == ConnectionState.DOWN:
        return ConnectionState.DOWN if prev.new_state != ConnectionState.DOWN else None

    # UP (including UNKNOWN → UP)
    if client.state == ConnectionState.UP and prev.new_state in {ConnectionState.DOWN, ConnectionState.SPIKE, ConnectionState.UNKNOWN}:
        return ConnectionState.UP

    return None


# ============================================================
# Template resolution
# ============================================================
def resolve_template_key(client: Client, prefix: str, state: ConnectionState) -> str:
    if state == ConnectionState.SPIKE:
        if prefix == PRIVATE_KEYWORD and client.status in {BillingStatus.CUTOFF, BillingStatus.LIMITED}:
            return f"{PRIVATE_KEYWORD}-UNPAID-SPIKE"
        return prefix
    return prefix


def extract_prefix(connection_name: str) -> str:
    if not connection_name:
        return ""
    prefix = connection_name.split("-", 1)[0]
    return connection_name if prefix == ISP_KEYWORD else prefix


# ============================================================
# Dispatching
# ============================================================
def dispatch_notification(db: Session, client: Client, prefix: str, content: str, group: str, state: ConnectionState):
    if prefix == ISP_KEYWORD:
        notify_all_under_group(db, content, group)
        return

    client_content = content

    if prefix in {PRIVATE_KEYWORD, VENDO_KEYWORD}:
        placeholder = PLACEHOLDER_REPLACEMENTS.get(prefix)
        if placeholder:
            replacement = (
                f"Your {client.connection_name}"
                if prefix == PRIVATE_KEYWORD
                else client.connection_name
            )
            client_content = content.replace(placeholder, replacement)

    enqueue_message(client, client_content, group)
    notify_admin_deduped(db, content, group, client.connection_name, prefix, state)

# ============================================================
# Queue helpers
# ============================================================
def enqueue_message(client: Client, content: str, group: str):
    group_queues[group].put((client, content))


# ============================================================
# Admin notifications (deduped)
# ============================================================
def notify_admin_deduped(db: Session, content: str, group: str, connection_name: str, prefix: str, state: ConnectionState):
    key = (group, prefix, connection_name, state)
    now = time.time()

    if key in admin_dedupe_cache and now - admin_dedupe_cache[key] < ADMIN_DEDUPE_WINDOW:
        return
    admin_dedupe_cache[key] = now

    replacement = PLACEHOLDER_REPLACEMENTS.get(prefix)
    if replacement:
        content = content.replace(replacement, connection_name)

    admins = db.query(Client).filter(Client.group_name == group, Client.connection_name == "ADMIN").all()
    for admin in admins:
        enqueue_message(admin, content, group)


# ============================================================
# ISP broadcast
# ============================================================
def notify_all_under_group(db: Session, content: str, group: str):
    clients = db.query(Client).filter(Client.group_name == group).all()
    for client in clients:
        if client.state == ConnectionState.DOWN or client.status == BillingStatus.CUTOFF:
            continue
        enqueue_message(client, content, group)


# ============================================================
# Boot
# ============================================================
start_queue_worker()

from sqlalchemy.orm import Session
import logging
import time
import threading
from collections import defaultdict, deque

from app.models import Client
from app.schemas import ConnectionState, BillingStatus
from app.services.template_service import get_template
from app.utils.messenger import send_message

logger = logging.getLogger("Notification Service")

# ---------------- Constants ----------------
ISP_KEYWORD = "ISP"
VENDO_KEYWORD = "VENDO"
PRIVATE_KEYWORD = "PRIVATE"

SPIKE_STABLE_SECONDS = 180  # 3 minutes debounce
RATE_LIMIT_PER_GROUP = 5    # messages per second per group
WORKER_SLEEP = 0.1          # sleep time between processing queue items

# ---------------- In-memory state ----------------
client_spike_cache: dict[int, dict] = {}
# client_id -> {"last_state": ConnectionState, "last_change": float, "is_spike": bool}

# Queue per group for rate-limited sending
group_queues: dict[str, deque] = defaultdict(deque)
group_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
group_last_sent = defaultdict(lambda: 0)
group_message_count = defaultdict(lambda: 0)

# ---------------- Background Worker ----------------
def start_queue_worker():
    thread = threading.Thread(target=_queue_worker_loop, daemon=True)
    thread.start()

def _queue_worker_loop():
    while True:
        now = time.time()
        for group, queue in group_queues.items():
            with group_locks[group]:
                # reset counter every 1 second
                if now - group_last_sent[group] > 1:
                    group_last_sent[group] = now
                    group_message_count[group] = 0

                # process messages up to RATE_LIMIT_PER_GROUP
                while queue and group_message_count[group] < RATE_LIMIT_PER_GROUP:
                    client, content = queue.popleft()
                    try:
                        send_message(client.messenger_id, content)
                        group_message_count[group] += 1
                    except Exception as e:
                        logger.error(f"[{group}] Failed to send message to {client.id}: {e}")

        time.sleep(WORKER_SLEEP)

# ---------------- Notification Entry Point ----------------
def send_notification(db: Session, clients: list[Client]) -> None:
    for client in clients:
        # UNKNOWN never notifies
        if client.state == ConnectionState.UNKNOWN:
            continue

        # SPIKE stabilization check
        if not is_client_stable(client):
            logger.debug(f"[{client.group_name}] Client {client.id} in SPIKE, observing only")
            continue

        prefix = extract_prefix(client.connection_name)
        group_name = client.group_name

        template_key = resolve_template_key(client, prefix)
        template = get_template(db, group_name, template_key, client.state)
        if not template:
            logger.debug(f"[{group_name}] No template for '{template_key}'")
            continue

        content = template.content
        dispatch_notification(db, client, prefix, content, group_name)

# ---------------- SPIKE / Stabilization Logic ----------------
def is_client_stable(client: Client) -> bool:
    now = time.time()
    entry = client_spike_cache.get(client.id)

    if not entry:
        client_spike_cache[client.id] = {
            "last_state": client.state,
            "last_change": now,
            "is_spike": False,
        }
        return True

    if entry["last_state"] != client.state:
        entry["last_state"] = client.state
        entry["last_change"] = now
        entry["is_spike"] = True
        return False

    if entry["is_spike"]:
        if now - entry["last_change"] >= SPIKE_STABLE_SECONDS:
            entry["is_spike"] = False
            return True
        return False

    return True

# ---------------- Template Resolution ----------------
def resolve_template_key(client: Client, prefix: str) -> str:
    if client.state == ConnectionState.SPIKE:
        if prefix == PRIVATE_KEYWORD and client.status in {BillingStatus.CUTOFF, BillingStatus.LIMITED}:
            return f"{PRIVATE_KEYWORD}-UNPAID-SPIKE"
        return f"{prefix}-SPIKE"
    return prefix

def extract_prefix(connection_name: str) -> str:
    prefix = connection_name.split("-", 1)[0]
    if prefix == ISP_KEYWORD:
      return connection_name
    return connection_name.split("-", 1)[0]

# ---------------- Dispatching ----------------
def dispatch_notification(db: Session, client: Client, prefix: str, content: str, group: str):
    if prefix == ISP_KEYWORD:
        notify_all_under_group(db, content, group)
    elif prefix == PRIVATE_KEYWORD or prefix == VENDO_KEYWORD:
        enqueue_message(client, content, group)
        notify_admin(db, content, group, client.connection_name, prefix)
    else:
        logger.debug(f"[{group}] Unknown connection prefix '{prefix}'")

# ---------------- Queue Helper ----------------
def enqueue_message(client: Client, content: str, group: str):
    with group_locks[group]:
        group_queues[group].append((client, content))

# ---------------- Admin Notifications ----------------
def notify_admin(db: Session, content: str, group: str, connection_name: str, prefix: str):
    admins = (
        db.query(Client)
        .filter(Client.connection_name == "ADMIN", Client.group_name == group)
        .all()
    )
    if prefix == PRIVATE_KEYWORD:
        content = content.replace("Your", connection_name)
    elif prefix == VENDO_KEYWORD:
        content = content.replace("Vendo", connection_name)
    for admin in admins:
        enqueue_message(admin, content, group)

# ---------------- ISP Broadcast ----------------
def notify_all_under_group(db: Session, content: str, group: str):
    clients = db.query(Client).filter(Client.group_name == group).all()
    for client in clients:
        if client.state == ConnectionState.DOWN or client.status == BillingStatus.CUTOFF:
            continue
        enqueue_message(client, content, group)

# ---------------- Start worker ----------------
start_queue_worker()

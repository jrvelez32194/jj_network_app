from sqlalchemy.orm import Session
import logging
import time
import threading
from collections import defaultdict, deque

from app.models import Client
from app.schemas import ConnectionState, BillingStatus
from app.services.template_service import get_template
from app.utils.messenger import send_message

logger = logging.getLogger("notification_service")

# ============================================================
# Constants
# ============================================================
ISP_KEYWORD = "ISP"
VENDO_KEYWORD = "VENDO"
PRIVATE_KEYWORD = "PRIVATE"

OBSERVATION_WINDOW = 60     # detect flapping
STABILITY_WINDOW = 30       # must hold before notify
CACHE_TTL = 3600            # cleanup window

RATE_LIMIT_PER_GROUP = 5
WORKER_SLEEP = 0.1

# ============================================================
# Admin Deduplication Cache
# ============================================================
# (group, prefix, connection_name, state) -> last_sent_ts
admin_dedupe_cache: dict[tuple, float] = {}

ADMIN_DEDUPE_WINDOW = 60  # seconds


# ============================================================
# In-memory State
# ============================================================
# client_id -> state machine
client_state_cache: dict[int, dict] = {}

group_queues: dict[str, deque] = defaultdict(deque)
group_locks: dict[str, threading.Lock] = defaultdict(threading.Lock)
group_last_tick = defaultdict(float)
group_sent_count = defaultdict(int)


# ============================================================
# Queue Worker
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

            for group, queue in list(group_queues.items()):
                with group_locks[group]:
                    if now - group_last_tick[group] >= 1:
                        group_last_tick[group] = now
                        group_sent_count[group] = 0

                    while queue and group_sent_count[group] < RATE_LIMIT_PER_GROUP:
                        client, content = queue.popleft()
                        try:
                            send_message(client.messenger_id, content)
                            group_sent_count[group] += 1
                        except Exception:
                            logger.exception(
                                "[%s] Failed sending to client %s",
                                group,
                                client.id,
                            )

        except Exception:
            logger.exception("Notification queue worker crashed")
            time.sleep(1)

        time.sleep(WORKER_SLEEP)


# ============================================================
# Public Entry Point
# ============================================================
def send_notification(
    db: Session,
    clients: list[Client],
    is_router_down: bool,
    router_group: str,
) -> None:

    # ---------------- ISP Router DOWN ----------------
    if is_router_down:
        template = get_template(
            db,
            router_group,
            ISP_KEYWORD,
            ConnectionState.DOWN,
        )
        if not template:
            return

        dispatch_notification(
            db=db,
            client=None,
            prefix=ISP_KEYWORD,
            content=template.content,
            group=router_group,
        )
        return

    # ---------------- Per-client ----------------
    for client in clients:
        if not client.connection_name:
            continue

        if client.state == ConnectionState.UNKNOWN:
            continue

        if not is_client_stable(client):
            logger.debug(
                "[%s] Client %s flapping (state=%s)",
                client.group_name,
                client.id,
                client.state,
            )
            continue

        prefix = extract_prefix(client.connection_name)
        group = client.group_name

        template_key = resolve_template_key(client, prefix)
        template = get_template(db, group, template_key, client.state)

        if not template:
            continue

        dispatch_notification(
            db=db,
            client=client,
            prefix=prefix,
            content=template.content,
            group=group,
        )


# ============================================================
# Hybrid Stability Logic (BEST PRACTICE)
# ============================================================
def is_client_stable(client: Client) -> bool:
    """
    Hybrid Model:
    - UP recovery → immediate
    - DOWN/SPIKE → must stabilize
    - Flapping → suppressed
    """
    now = time.time()
    entry = client_state_cache.get(client.id)

    if not entry:
        client_state_cache[client.id] = {
            "observed_state": client.state,
            "stable_since": now,
            "last_change": now,
            "notified_state": None,
        }
        return True

    # State changed
    if entry["observed_state"] != client.state:
        entry["observed_state"] = client.state
        entry["stable_since"] = now
        entry["last_change"] = now

        # Immediate UP recovery
        if client.state == ConnectionState.UP:
            entry["notified_state"] = ConnectionState.UP
            return True

        return False

    # Same state → check stability
    stable_duration = now - entry["stable_since"]

    if stable_duration >= STABILITY_WINDOW:
        if entry["notified_state"] == client.state:
            return False

        entry["notified_state"] = client.state
        return True

    # Cleanup
    if now - entry["last_change"] > CACHE_TTL:
        client_state_cache.pop(client.id, None)

    return False


# ============================================================
# Template Resolution
# ============================================================
def resolve_template_key(client: Client, prefix: str) -> str:
    if client.state == ConnectionState.SPIKE:
        if (
            prefix == PRIVATE_KEYWORD
            and client.status in {BillingStatus.CUTOFF, BillingStatus.LIMITED}
        ):
            return f"{PRIVATE_KEYWORD}-UNPAID-SPIKE"
        return f"{prefix}-SPIKE"

    return prefix


def extract_prefix(connection_name: str) -> str:
    prefix = connection_name.split("-", 1)[0]
    return connection_name if prefix == ISP_KEYWORD else prefix


# ============================================================
# Dispatching
# ============================================================
def dispatch_notification(
    db: Session,
    client: Client | None,
    prefix: str,
    content: str,
    group: str,
) -> None:

    if prefix == ISP_KEYWORD:
        notify_all_under_group(db, content, group)
        return

    if prefix in {PRIVATE_KEYWORD, VENDO_KEYWORD} and client:
        enqueue_message(client, content, group)
        notify_admin_deduped(db, content, group, client.connection_name, prefix, client.state)
        return

    logger.debug("[%s] Unknown prefix '%s'", group, prefix)


# ============================================================
# Queue Helpers
# ============================================================
def enqueue_message(client: Client, content: str, group: str) -> None:
    with group_locks[group]:
        group_queues[group].append((client, content))


# ============================================================
# Admin Notifications
# ============================================================
def notify_admin(
    db: Session,
    content: str,
    group: str,
    connection_name: str,
    prefix: str,
) -> None:

    admins = (
        db.query(Client)
        .filter(
            Client.connection_name == "ADMIN",
            Client.group_name == group,
        )
        .all()
    )

    if prefix == PRIVATE_KEYWORD:
        content = content.replace("Your", connection_name)
    elif prefix == VENDO_KEYWORD:
        content = content.replace("Vendo", connection_name)

    for admin in admins:
        enqueue_message(admin, content, group)

# De duplicate admin method
def notify_admin_deduped(
    db: Session,
    content: str,
    group: str,
    connection_name: str,
    prefix: str,
    state: ConnectionState,
) -> None:
  """
  Ensure admin receives only ONE notification per
  (group, prefix, connection_name, state) within time window
  """
  now = time.time()
  cache_key = (group, prefix, connection_name, state)

  last_sent = admin_dedupe_cache.get(cache_key)
  if last_sent and (now - last_sent) < ADMIN_DEDUPE_WINDOW:
    logger.debug(
      "[ADMIN-DEDUPE] Suppressed duplicate admin notif: %s",
      cache_key,
    )
    return

  admin_dedupe_cache[cache_key] = now

  admins = (
    db.query(Client)
    .filter(
      Client.connection_name == "ADMIN",
      Client.group_name == group,
    )
    .all()
  )

  if prefix == PRIVATE_KEYWORD:
    content = content.replace("Your", connection_name)
  elif prefix == VENDO_KEYWORD:
    content = content.replace("Vendo", connection_name)

  for admin in admins:
    enqueue_message(admin, content, group)



# ============================================================
# ISP Broadcast
# ============================================================
def notify_all_under_group(
    db: Session,
    content: str,
    group: str,
) -> None:

    clients = db.query(Client).filter(Client.group_name == group).all()

    for client in clients:
        if client.state == ConnectionState.DOWN:
            continue
        if client.status == BillingStatus.CUTOFF:
            continue

        enqueue_message(client, content, group)


# ============================================================
# Boot
# ============================================================
start_queue_worker()

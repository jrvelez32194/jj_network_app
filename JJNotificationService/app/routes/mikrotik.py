import time
import threading
import logging
from fastapi import APIRouter, Query
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils.messenger import send_message

router = APIRouter()
logger = logging.getLogger("mikrotik")

# --- DB session ---
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# --- Debounce / Stability config ---
last_state = {}          # Current detected state
notified_state = {}      # Last actually sent state
timers = {}              # Running debounce timers
last_changes = {}        # List of timestamps for recent changes
unstable_until = {}      # Timestamp until which UPs are ignored

DELAY = 180              # 3 minutes debounce (180s)
FLAP_THRESHOLD = 4       # Number of changes that defines instability
FLAP_WINDOW = 300        # 5 minutes window to check instability


def notify_clients(db: Session, template_name: str, connection_name: str = None, group_name: str = None):
    template = db.query(models.Template).filter(models.Template.title == template_name).first()
    if not template:
        logger.warning(f"Template '{template_name}' not found")
        return

    query = db.query(models.Client)
    if connection_name and not connection_name.startswith("ISP"):
        query = query.filter(models.Client.connection_name == connection_name)
    if group_name:
        query = query.filter(models.Client.group_name == group_name)

    clients = query.all()
    for client in clients:
        resp = send_message(client.messenger_id, template.content)
        log = models.MessageLog(
            client_id=client.id,
            template_id=template.id,
            status=resp.get("message_id", "failed"),
        )
        db.add(log)
        db.commit()
    logger.info(f"✅ Sent '{template_name}' to {len(clients)} clients")


def schedule_notify(state_key, template_name, connection_name, group_name, new_state):
    """Debounce and handle stability detection"""

    def task():
        logger.info(f"[{state_key}] Waiting {DELAY}s before confirming {new_state}")
        time.sleep(DELAY)

        # Still same state after waiting?
        if last_state.get(state_key) != new_state:
            logger.info(f"[{state_key}] State changed before stability delay, aborting send.")
            return

        prev_sent = notified_state.get(state_key)
        if new_state == "UP":
            # Skip UP if currently unstable
            now = time.time()
            if unstable_until.get(state_key, 0) > now:
                logger.info(f"[{state_key}] Skipping UP notification (still unstable until {time.ctime(unstable_until[state_key])})")
                return

        if prev_sent != new_state:
            db = SessionLocal()
            try:
                notify_clients(db, template_name, connection_name, group_name)
                notified_state[state_key] = new_state
            finally:
                db.close()
        else:
            logger.info(f"[{state_key}] {new_state} already notified before, skipping duplicate.")

    # Cancel old timer if running
    if timers.get(state_key) and timers[state_key].is_alive():
        timers[state_key] = None  # mark replaced

    t = threading.Thread(target=task, daemon=True)
    timers[state_key] = t
    t.start()


def record_change(state_key):
    """Track rapid state changes to detect flapping"""
    now = time.time()
    changes = last_changes.get(state_key, [])
    changes = [ts for ts in changes if now - ts < FLAP_WINDOW]  # keep only recent changes
    changes.append(now)
    last_changes[state_key] = changes

    if len(changes) >= FLAP_THRESHOLD:
        unstable_until[state_key] = now + DELAY  # wait another 3 min after last change
        logger.warning(f"[{state_key}] ⚠️ Detected flapping ({len(changes)} changes). Marked unstable until {time.ctime(unstable_until[state_key])}.")


# --- Endpoints ---
@router.get("/mikrotik/down")
def mikrotik_down(
    connection_name: str = Query(...),
    group_name: str = Query(...),
):
    key = f"{connection_name}_{group_name}"
    template_name = f"{connection_name}-DOWN"
    last_state[key] = "DOWN"
    record_change(key)

    logger.info(f"[{key}] DOWN detected")
    schedule_notify(key, template_name, connection_name, group_name, "DOWN")
    return {"status": f"scheduled {template_name} after {DELAY}s if stable"}


@router.get("/mikrotik/up")
def mikrotik_up(
    connection_name: str = Query(...),
    group_name: str = Query(...),
):
    key = f"{connection_name}_{group_name}"
    template_name = f"{connection_name}-UP"
    last_state[key] = "UP"
    record_change(key)

    logger.info(f"[{key}] UP detected")
    schedule_notify(key, template_name, connection_name, group_name, "UP")
    return {"status": f"scheduled {template_name} after {DELAY}s if stable"}

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session
import threading
import logging
from datetime import datetime, timedelta
import pytz

from app.database import get_db
from app.utils.billing import check_billing, apply_billing_to_client
from app.models import Client

router = APIRouter(prefix="/force", tags=["Billing Control"])
logger = logging.getLogger("force_billing")

PH_TZ = pytz.timezone("Asia/Manila")

# ==========================================================
# 🔔 Force Notification + Auto-Enforce After 1 Hour
# ==========================================================

def delayed_enforce(db_session_factory, group: str | None):
    """Run enforce 1 hour after notification."""
    db = db_session_factory()
    try:
        logger.info(f"⏰ Enforce job started for group='{group}' after 1-hour delay.")
        check_billing(db, mode="enforce", group_name=group)
        logger.info(f"✅ Enforce completed for group='{group}'.")
    except Exception as e:
        logger.error(f"❌ Delayed enforce failed for group='{group}': {e}")
    finally:
        db.close()


@router.post("/run")
def force_billing_run(
    mode: str = Query("notification", enum=["notification", "enforce"]),
    group: str | None = Query(None, description="Optional group name"),
    db: Session = Depends(get_db),
):
    """
    Manually trigger billing cycle for all clients or a specific group.
    If mode='notification', enforcement will automatically follow after 1 hour.
    """
    # Step 1: Run notification immediately
    check_billing(db, mode=mode, group_name=group)

    # Step 2: Schedule enforcement after 1 hour
    if mode == "notification":
        timer = threading.Timer(3600, delayed_enforce, args=(get_db, group))
        timer.daemon = True
        timer.start()

        run_time = (datetime.now(PH_TZ) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"🕒 Enforce scheduled for {run_time} (group='{group}')")

        return {
            "status": "success",
            "steps": ["notification", "enforce (after 1 hour)"],
            "group": group,
            "scheduled_enforce_time": run_time,
            "message": f"Notification done. Enforce scheduled for {run_time}.",
        }

    # If enforce is selected directly
    return {"status": "success", "mode": mode, "group": group}


# ==========================================================
# 🎯 Force Billing on One Client (with delayed enforce)
# ==========================================================

def delayed_enforce_client(db_session_factory, client_id: int):
    db = db_session_factory()
    try:
        client = db.query(Client).filter(Client.id == client_id).first()
        if not client:
            logger.warning(f"Client {client_id} not found for delayed enforce.")
            return
        logger.info(f"⏰ Enforce job started for client {client.name} after 1-hour delay.")
        apply_billing_to_client(db, client, "enforce")
        logger.info(f"✅ Enforce completed for client {client.name}.")
    except Exception as e:
        logger.error(f"❌ Delayed enforce failed for client {client_id}: {e}")
    finally:
        db.close()


@router.post("/client/{client_id}")
def force_billing_client(
    client_id: int,
    mode: str = Query("notification", enum=["notification", "enforce"]),
    db: Session = Depends(get_db),
):
    """
    Apply billing manually for a single client.
    If mode='notification', enforcement will automatically follow after 1 hour.
    """
    client = db.query(Client).filter(Client.id == client_id).first()
    if not client:
        return {"error": "Client not found"}

    # Step 1: Run notification immediately
    apply_billing_to_client(db, client, mode)

    # Step 2: Schedule enforcement after 1 hour
    if mode == "notification":
        timer = threading.Timer(3600, delayed_enforce_client, args=(get_db, client_id))
        timer.daemon = True
        timer.start()

        run_time = (datetime.now(PH_TZ) + timedelta(hours=1)).strftime("%Y-%m-%d %H:%M:%S %Z")
        logger.info(f"🕒 Enforce scheduled for {run_time} (client='{client.name}')")

        return {
            "status": "ok",
            "client": client.name,
            "steps": ["notification", "enforce (after 1 hour)"],
            "group": client.group_name,
            "scheduled_enforce_time": run_time,
            "message": f"Notification sent. Enforce will run automatically at {run_time}.",
        }

    # Direct enforce mode
    return {
        "status": "ok",
        "client": client.name,
        "steps": [mode],
        "group": client.group_name,
        "new_status": client.status.value if hasattr(client.status, "value") else client.status,
    }

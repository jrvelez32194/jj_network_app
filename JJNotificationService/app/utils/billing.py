import os
import asyncio
import json
import logging
from datetime import datetime, date
from sqlalchemy.orm import Session
from dateutil.relativedelta import relativedelta
import pytz

from app.models import Client, BillingStatus
from app.utils.mikrotik_config import MikroTikClient
from app.websocket_manager import manager
from app.utils.messenger import send_message
from app.utils.messages import get_messages, safe_format

logger = logging.getLogger("billing")

PH_TZ = pytz.timezone("Asia/Manila")
BILLING_FILTER = os.getenv("BILLING_FILTER", "PRIVATE").upper()

# =====================================================
# ✅ Router Management
# =====================================================

def load_all_mikrotiks():
    """Load all MikroTik routers from ROUTER_MAP_JSON in .env"""
    routers = []
    router_map_str = os.getenv("ROUTER_MAP_JSON", "{}")

    try:
        router_map = json.loads(router_map_str)
    except json.JSONDecodeError as e:
        logger.error(f"Invalid ROUTER_MAP_JSON: {e}")
        router_map = {}

    username = os.getenv("MIKROTIK_USER", "admin")
    password = os.getenv("MIKROTIK_PASS", "")

    for group, host in router_map.items():
        routers.append({
            "group": group.upper(),
            "client": MikroTikClient(host=host, username=username, password=password),
        })

    logger.info(f"Loaded {len(routers)} MikroTik router(s): {[r['group'] for r in routers]}")
    return routers


def get_router_for_client(client: Client, routers: list[dict]):
    """Select router based on client's group_name or connection_name."""
    if not routers:
        return None

    group_name = (client.group_name or "").upper().strip()

    # ✅ Direct match only — no alias remapping
    for r in routers:
        if r["group"].upper() == group_name:
            return r["client"]

    # Fallback: match by IP/host in connection_name
    if client.connection_name:
        for r in routers:
            if r["client"].host in client.connection_name:
                return r["client"]

    # Default fallback
    return routers[0]["client"]

# =====================================================
# ✅ Core Billing Logic
# =====================================================

def get_last_billing_date(client: Client) -> date:
    return client.billing_date or datetime.now(PH_TZ).date()


def enforce_billing_rules(
    client: Client,
    mikrotik: MikroTikClient,
    days_overdue: int,
    last_billing_date: date,
    db: Session,
    mode: str = "enforce",
):
    """Apply billing rules based on overdue days and mode ('notification' or 'enforce')."""
    if days_overdue < 0:
        return

    def safe_float(value):
        try:
            return float(value)
        except (TypeError, ValueError):
            return 0.0

    try:
        # ✅ Dynamic message templates
        messages = get_messages(client.group_name or "")

        # --- PAID ---
        if client.status == BillingStatus.PAID:
            if mode == "sync" and client.speed_limit != "Unlimited":
                client.speed_limit = "Unlimited"
                mikrotik.unblock_client(client.connection_name)
                mikrotik.set_speed_limit(client.connection_name, "Unlimited")
            return

        # --- DUE TODAY ---
        if days_overdue == 0 and client.status != BillingStatus.UNPAID:
            if mode == "enforce":
                client.status = BillingStatus.UNPAID
                mikrotik.unblock_client(client.connection_name)
                mikrotik.set_speed_limit(client.connection_name, "Unlimited")

            if mode == "notification":
                amount_value = safe_float(client.amt_monthly)
                logger.debug(
                    f"[DEBUG] {client.name} amt_monthly={client.amt_monthly!r} → safe_float={amount_value!r}"
                )

                # ✅ Safe message formatting using safe_format()
                message_text = safe_format(
                    messages["DUE_NOTICE"],
                    due_date=last_billing_date.strftime("%B %d, %Y"),
                    amount=amount_value,
                )

                send_message(client.messenger_id, message_text)
            return

        # --- LIMITED (4–6 days overdue) ---
        if 4 <= days_overdue < 7 and client.status != BillingStatus.LIMITED:
            if mode == "enforce":
                client.status = BillingStatus.LIMITED
                client.speed_limit = "5M/5M"
                mikrotik.set_speed_limit(client.connection_name, "5M/5M")

            if mode == "notification":
                send_message(client.messenger_id, messages["THROTTLE_NOTICE"])
            return

        # --- CUTOFF (7+ days overdue) ---
        if days_overdue >= 7 and client.status != BillingStatus.CUTOFF:
            if mode == "enforce":
                client.status = BillingStatus.CUTOFF
                client.speed_limit = "0M/0M"
                mikrotik.block_client(client.connection_name)
                mikrotik.set_speed_limit(client.connection_name, "0M/0M")

            if mode == "notification":
                send_message(client.messenger_id, messages["DISCONNECTION_NOTICE"])

    except Exception as e:
        logger.error(f"Billing rule failed for {client.name}: {e}")
    finally:
        db.add(client)
        db.commit()

# =====================================================
# ✅ Safe Broadcast Utility
# =====================================================

def safe_broadcast(message: dict):
    """Broadcast WebSocket message safely."""
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(message))
    except RuntimeError:
        asyncio.run(manager.broadcast(message))

# =====================================================
# ✅ Main Billing Cycle
# =====================================================

def check_billing(db: Session, mode: str = "enforce"):
    """Run billing cycle for all clients across routers."""
    today = datetime.now(PH_TZ)
    today_date = today.date()
    routers = load_all_mikrotiks()

    clients = db.query(Client).filter(
        Client.connection_name.ilike(f"%{BILLING_FILTER}%")
    ).all()

    for client in clients:
        if not client.billing_date or not client.connection_name:
            continue

        mikrotik = get_router_for_client(client, routers)
        if not mikrotik:
            logger.warning(f"No router found for {client.name}")
            continue

        last_billing_date = get_last_billing_date(client)
        days_overdue = (today_date - last_billing_date).days
        if days_overdue < 0:
            continue

        old_status = client.status
        enforce_billing_rules(
            client, mikrotik, days_overdue, last_billing_date, db, mode
        )

        # Broadcast if changed
        if mode == "enforce" and client.status != old_status:
            safe_broadcast({
                "event": "billing_update",
                "client_id": client.id,
                "status": client.status.value,
                "billing_date": client.billing_date.isoformat() if client.billing_date else None,
                "local_time": today.strftime("%Y-%m-%d %H:%M:%S %Z"),
            })

    db.commit()

# =====================================================
# ✅ Apply Billing for One Client
# =====================================================

def apply_billing_to_client(db: Session, client: Client, mode: str = "enforce"):
    today = datetime.now(PH_TZ).date()
    routers = load_all_mikrotiks()
    mikrotik = get_router_for_client(client, routers)
    if not mikrotik or not client.billing_date:
        return

    days_overdue = (today - get_last_billing_date(client)).days
    old_status = client.status
    enforce_billing_rules(
        client, mikrotik, days_overdue, get_last_billing_date(client), db, mode
    )

    if client.status != old_status:
        safe_broadcast({
            "event": "billing_update",
            "client_id": client.id,
            "status": client.status.value,
            "billing_date": client.billing_date.isoformat() if client.billing_date else None,
            "local_time": datetime.now(PH_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        })
    db.commit()

# =====================================================
# ✅ Billing Actions (Paid / Unpaid)
# =====================================================

def increment_billing_cycle(client: Client):
    client.billing_date = (
        (client.billing_date or datetime.now(PH_TZ).date()) + relativedelta(months=1)
    )


def decrement_billing_cycle(client: Client):
    client.billing_date = (
        (client.billing_date or datetime.now(PH_TZ).date()) - relativedelta(months=1)
    )


def handle_paid_client(db: Session, client: Client):
    """Handle a client marked as PAID."""
    try:
        if client.speed_limit != "Unlimited":
            client.speed_limit = "Unlimited"
        increment_billing_cycle(client)
        apply_billing_to_client(db, client, "enforce")
        db.refresh(client)
        safe_broadcast({
            "event": "billing_update",
            "client_id": client.id,
            "status": client.status.value if hasattr(client.status, "value") else client.status,
            "billing_date": client.billing_date.isoformat() if client.billing_date else None,
            "local_time": datetime.now(PH_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        })
        logger.info(f"✅ Client {client.name} marked as PAID and billing reapplied.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle paid client {client.name}: {e}")


def handle_unpaid_client(db: Session, client: Client, mode: str = "enforce"):
    """Handle a client being marked UNPAID — reapply billing rules."""
    try:
        apply_billing_to_client(db, client, mode)
        db.refresh(client)
        safe_broadcast({
            "event": "billing_update",
            "client_id": client.id,
            "status": client.status.value if hasattr(client.status, "value") else client.status,
            "billing_date": client.billing_date.isoformat() if client.billing_date else None,
            "local_time": datetime.now(PH_TZ).strftime("%Y-%m-%d %H:%M:%S %Z"),
        })
        logger.info(f"⚠️ Client {client.name} marked as UNPAID and billing reapplied.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle unpaid client {client.name}: {e}")

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
    """Strictly select router based on client's group_name."""
    if not routers:
        return None

    group_name = (client.group_name or "").upper().strip()
    for r in routers:
        if r["group"] == group_name:
            return r["client"]

    logger.warning(f"[{client.name}] No router matched group '{group_name}' — skipping.")
    return None


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
  """Apply billing rules based on overdue days and mode ('notification' or 'enforce'),
  and mirror notices to ADMIN client automatically.
  """

  if days_overdue < 0:
    logger.info(
      f"💰 [{client.name}] Paid in advance — next billing will apply on {last_billing_date}.")
    return

  def safe_float(value):
    try:
      return float(value)
    except (TypeError, ValueError):
      return 0.0

  try:
    messages = get_messages(client.group_name or "")
    payment_location = messages.get("PAYMENT_LOCATION",
                                    "Sitio Coronado, Malalag Cogon")

    # helper: mirror notice to admin
    def mirror_to_admin(notice_type: str, **kwargs):
        try:
          # ✅ Filter only admins that match the same group_name
          admins = (
            db.query(Client)
            .filter(Client.connection_name.ilike("ADMIN%"))
            .filter(Client.group_name == client.group_name)
            .filter(Client.messenger_id.isnot(None))
            .all()
          )

          if not admins:
            logger.warning(
              f"⚠️ No ADMIN accounts found for group '{client.group_name}' — skipping mirror.")
            return

          admin_msgs = get_messages(client.group_name or "", "ADMIN")
          if notice_type not in admin_msgs:
            logger.warning(
              f"⚠️ No admin message template for '{notice_type}' in group '{client.group_name}'")
            return

          msg_text = safe_format(admin_msgs[notice_type], **kwargs)

          for admin in admins:
            send_message(admin.messenger_id, msg_text)
            logger.info(
              f"📨 Mirrored {notice_type} to {admin.connection_name} (group={admin.group_name}) for [{client.name}]."
            )

        except Exception as e:
          logger.error(
            f"Failed to mirror {notice_type} to ADMIN(s) in group '{client.group_name}': {e}")

    # --- DUE TODAY ---
    if days_overdue == 0:
      if mode == "enforce":
        if client.status != BillingStatus.UNPAID:
          client.status = BillingStatus.UNPAID
          mikrotik.unblock_client(client.connection_name)
          mikrotik.set_speed_limit(client.connection_name, "Unlimited")
          logger.info(f"🔄 [{client.name}] Status set to UNPAID (due today).")

      if mode == "notification":
        amount_value = safe_float(client.amt_monthly)
        message_text = safe_format(
          messages["DUE_NOTICE"],
          due_date=last_billing_date.strftime("%B %d, %Y"),
          amount=amount_value,
          payment_location=payment_location,
        )
        send_message(client.messenger_id, message_text)
        logger.info(f"📩 [{client.name}] DUE notice sent.")

        # mirror to admin
        mirror_to_admin(
          "DUE_NOTICE",
          client_name=client.name,
          group_name=client.group_name,
          due_date=last_billing_date.strftime("%B %d, %Y"),
          amount=amount_value,
        )
      return

    # --- PAID STATUS CHECK ---
    if client.status == BillingStatus.PAID:
      if days_overdue >= 0:
        client.status = BillingStatus.UNPAID
        mikrotik.unblock_client(client.connection_name)
        mikrotik.set_speed_limit(client.connection_name, "Unlimited")
        logger.info(
          f"⚠️ [{client.name}] Payment period ended — reverted to UNPAID ({days_overdue}d).")
        return

      if mode in ["sync", "enforce"] and client.speed_limit != "Unlimited":
        mikrotik.unblock_client(client.connection_name)
        mikrotik.set_speed_limit(client.connection_name, "Unlimited")
        client.speed_limit = "Unlimited"
        logger.info(f"✅ [{client.name}] Synced: speed reset to Unlimited.")
      return

    # --- LIMITED (4–6 days overdue) ---
    if 4 <= days_overdue < 7 and client.status != BillingStatus.LIMITED:
      if mode == "enforce":
        client.status = BillingStatus.LIMITED
        client.speed_limit = "5M/5M"
        mikrotik.set_speed_limit(client.connection_name, "5M/5M")
        logger.info(f"⚠️ [{client.name}] Enforced limited speed (5M/5M).")

      if mode == "notification":
        throttle_msg = safe_format(messages["THROTTLE_NOTICE"],
                                   payment_location=payment_location)
        send_message(client.messenger_id, throttle_msg)
        logger.info(f"📩 [{client.name}] Throttle notice sent.")

        # mirror to admin
        mirror_to_admin(
          "THROTTLE_NOTICE",
          client_name=client.name,
          group_name=client.group_name,
          due_date=last_billing_date.strftime("%B %d, %Y"),
          amount=safe_float(client.amt_monthly),
        )
      return

    # --- CUTOFF (7+ days overdue) ---
    if days_overdue >= 7 and client.status != BillingStatus.CUTOFF:
      if mode == "enforce":
        client.status = BillingStatus.CUTOFF
        client.speed_limit = "0M/0M"
        mikrotik.block_client(client.connection_name)
        mikrotik.set_speed_limit(client.connection_name, "0M/0M")
        logger.info(f"⛔ [{client.name}] Client cutoff enforced.")

      if mode == "notification":
        disconnection_msg = safe_format(messages["DISCONNECTION_NOTICE"],
                                        payment_location=payment_location)
        send_message(client.messenger_id, disconnection_msg)
        logger.info(f"📩 [{client.name}] Disconnection notice sent.")

        # mirror to admin
        mirror_to_admin(
          "DISCONNECTION_NOTICE",
          client_name=client.name,
          group_name=client.group_name,
          due_date=last_billing_date.strftime("%B %d, %Y"),
          amount=safe_float(client.amt_monthly),
        )

  except Exception as e:
    logger.error(f"Billing rule failed for {client.name}: {e}")
  finally:
    db.add(client)


# =====================================================
# ✅ Safe Broadcast Utility
# =====================================================

def safe_broadcast(message: dict):
    try:
        loop = asyncio.get_running_loop()
        loop.create_task(manager.broadcast(message))
    except RuntimeError:
        asyncio.run(manager.broadcast(message))


# =====================================================
# ✅ Main Billing Cycle (Group Aware)
# =====================================================

def check_billing(db: Session, mode: str = "enforce", group_name: str = None):
    """
    Execute billing for a specific router group only (if provided).
    Prevents duplicate billing runs across routers.
    """
    today = datetime.now(PH_TZ)
    today_date = today.date()
    routers = load_all_mikrotiks()

    query = db.query(Client).filter(Client.connection_name.ilike(f"%{BILLING_FILTER}%"))
    if group_name:
        query = query.filter(Client.group_name == group_name)

    clients = query.all()
    total = cnt_due = cnt_limited = cnt_cutoff = cnt_skipped = 0

    logger.info(f"🕒 Billing started at {today.strftime('%Y-%m-%d %H:%M:%S %Z')}")
    logger.info(f"🔔 Starting billing run (mode={mode}) for group='{group_name}' — {len(clients)} clients.")

    for client in clients:
        db.refresh(client)
        total += 1

        if not client.billing_date or not client.connection_name:
            cnt_skipped += 1
            logger.debug(f"⏭️ Skipping {client.name}: missing billing_date or connection_name.")
            continue

        mikrotik = get_router_for_client(client, routers)
        if not mikrotik:
            cnt_skipped += 1
            continue

        last_billing_date = get_last_billing_date(client)
        days_overdue = (today_date - last_billing_date).days

        if days_overdue < 0:
            cnt_skipped += 1
            logger.info(f"💰 [{client.name}] Paid in advance — next billing cycle on {last_billing_date}.")
            continue

        if client.status == BillingStatus.UNPAID:
            cnt_due += 1
        elif client.status == BillingStatus.LIMITED:
            cnt_limited += 1
        elif client.status == BillingStatus.CUTOFF:
            cnt_cutoff += 1

        old_status = client.status
        enforce_billing_rules(client, mikrotik, days_overdue, last_billing_date, db, mode)

        if mode == "enforce" and client.status != old_status:
            logger.info(
                f"[{client.name}] ({client.group_name}) via {mikrotik.host} → {old_status.value} → {client.status.value}"
            )
            safe_broadcast({
                "event": "billing_update",
                "client_id": client.id,
                "status": client.status.value,
                "billing_date": client.billing_date.isoformat() if client.billing_date else None,
                "local_time": today.strftime("%Y-%m-%d %H:%M:%S %Z"),
            })

    db.commit()
    summary = {
        "group": group_name,
        "mode": mode,
        "total": total,
        "due": cnt_due,
        "limited": cnt_limited,
        "cutoff": cnt_cutoff,
        "skipped": cnt_skipped,
    }

    logger.info(f"🧾 Billing complete — {summary}")
    return summary


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
    enforce_billing_rules(client, mikrotik, days_overdue, get_last_billing_date(client), db, mode)

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

        logger.info(f"✅ [{client.name}] marked as PAID — next due {client.billing_date}.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle paid client {client.name}: {e}")


def handle_unpaid_client(db: Session, client: Client, mode: str = "enforce"):
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
        logger.info(f"⚠️ [{client.name}] marked as UNPAID and billing reapplied.")
    except Exception as e:
        db.rollback()
        logger.error(f"Failed to handle unpaid client {client.name}: {e}")

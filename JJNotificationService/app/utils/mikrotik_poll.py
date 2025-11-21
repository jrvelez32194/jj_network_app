# app/utils/mikrotik_poll.py
import time
import threading
import logging
import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("mikrotik_poll")
logger.setLevel(logging.INFO)

# ============================================================
# 🔧 Router mapping (configurable via environment variable)
# ============================================================
default_map = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or default_map
    logger.info(f"✅ Loaded router map: {ROUTER_MAP}")
except json.JSONDecodeError:
    ROUTER_MAP = default_map
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON format, using defaults.")

# ============================================================
# DB and debounce
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()


last_state = {}       # Last observed state (UP/DOWN)
notified_state = {}   # Last state actually notified
timers = {}
DELAY = 90  # seconds before sending notification

# Track per-group router status to avoid repeated group messages
# Values: "UP" | "DOWN" | None (unknown)
group_router_status: dict[str, str] = {}

# ============================================================
# Adaptive Spike detection & hold parameters
# ============================================================
BASE_SPIKE_WINDOW = 3 * 60
SPIKE_FLAP_THRESHOLD = 3
SPIKE_ESCALATE_SECONDS = 10 * 60

EARLY_SPIKE_WINDOW = 3 * 60
EARLY_SPIKE_THRESHOLD = 3

STABLE_CLEAR_WINDOW = 3 * 60

SPIKE_FLAP_WINDOW = BASE_SPIKE_WINDOW

HOLD_LEVELS = [
    (3, 3 * 60),
    (5, 5 * 60),
    (8, 8 * 60),
]

DEBOUNCE_SHORT = 30

# ============================================================
# Message composition helpers and maps
# ============================================================
GROUP_LOCATION = {"G1": "MALUNGON", "G2": "SURALLAH"}

# Group-specific provider down/up messages
GROUP_PROVIDER_DOWN_MSG = {
    "G1": "⚠️ All Internet Service Providers are down.",
    "G2": "⚠️ PLDT Provider is down.",
}
GROUP_PROVIDER_UP_MSG = {
    "G1": "✅ All Internet Service Providers are restored.",
    "G2": "✅ PLDT Provider is restored.",
}


def _parse_template_key(template_name: str) -> list:
    if not template_name:
        return []
    key = template_name.replace("_", "-").upper()
    parts = [p.strip() for p in key.split("-") if p.strip()]
    return parts


def _is_spike(parts: list[str]) -> bool:
    return "SPIKE" in parts


def _get_event(parts: list[str]) -> str | None:
    if "UP" in parts:
        return "UP"
    if "DOWN" in parts:
        return "DOWN"
    return None


def _get_group(parts: list[str]) -> str | None:
    for p in parts:
        if p.startswith("G"):
            return p
    return None


def _get_metric(parts: list[str]) -> str | None:
    if "PING" in parts:
        return "PING"
    if "CONNECTION" in parts:
        return "CONNECTION"
    if any(p == "VENDO" for p in parts):
        return "VENDO"
    if any(p == "PRIVATE" for p in parts):
        return "PRIVATE"
    return None


def _get_isp_token(parts: list[str]) -> str | None:
    for p in parts:
        if p.startswith("ISP"):
            return p
    return None


def _service_label_from_isp(isp_token: str | None) -> str | None:
    if isp_token == "ISP1":
        return "Primary Service Provider"
    if isp_token == "ISP2":
        return "Secondary Service Provider"
    if isp_token == "ISP":
        return "PLDT Provider"
    return None


def _compose_message(template_name: str, client_conn_name: str | None,
    client_is_admin: bool) -> str:
    parts = _parse_template_key(template_name)
    is_spike = _is_spike(parts)
    event = _get_event(parts)
    group = _get_group(parts)
    metric = _get_metric(parts)
    isp_token = _get_isp_token(parts)
    service_label = _service_label_from_isp(isp_token)

    location_suffix = GROUP_LOCATION.get(group, "")

    base = "Notification."

    if not is_spike:
        if metric == "CONNECTION" and service_label:
            if event == "UP":
                base = f"✅ {service_label} is back online. Service restored."
            else:
                base = f"⚠️ {service_label} is currently down. Please wait for restoration."
        elif metric == "PING" and service_label:
            if event == "UP":
                base = f"✅ {service_label} is now stable and running smoothly."
            else:
                base = f"⚠️ {service_label} is slow and experiencing high latency."
        elif metric == "VENDO":
            cn = client_conn_name or "VENDO"
            if event == "UP":
                base = f"✅ VENDO {cn} is now up and running smoothly."
            else:
                base = f"⚠️ VENDO {cn} is currently down. Please check cable and indicator light."
        elif metric == "PRIVATE":
            if client_is_admin:
                cn = client_conn_name or "PRIVATE"
                if event == "UP":
                    base = f"✅ {cn} is now up and running smoothly."
                else:
                    base = f"⚠️ {cn} is currently down. Please check the cable and plug."
            else:
                if event == "UP":
                    base = "✅ Your connection is now up and running smoothly."
                else:
                    base = "⚠️ Your connection is currently down. Please check the cable and plug."
        else:
            if event == "UP":
                base = "✅ Service is back online. Service restored."
            else:
                base = "⚠️ Service is currently down. Please wait for restoration."
    else:
        if metric in ("CONNECTION", "PING") and service_label:
            if event == "UP":
                base = f"✅ {service_label} is now stable and running smoothly again."
            else:
                base = f"⚠️ {service_label} is slow and unstable or experiencing latency."
        elif metric == "VENDO":
            cn = client_conn_name or "VENDO"
            if event == "UP":
                base = f"✅ VENDO {cn} is now stable."
            else:
                base = f"⚠️ VENDO {cn} is currently unstable. Please check cable and indicator light."
        elif metric == "PRIVATE":
            cn = client_conn_name or "PRIVATE"
            if client_is_admin:
                if event == "UP":
                    base = f"✅ {cn} is now stable."
                else:
                    base = f"⚠️ {cn} is currently unstable. Please check the cable and plug."
            else:
                if event == "UP":
                    base = "✅ Your connection is now stable."
                else:
                    base = "⚠️ Your connection is currently unstable. Please check the cable and plug."
        else:
            if event == "UP":
                base = "✅ Service is now stable and running smoothly again."
            else:
                base = "⚠️ Service is slow and unstable or experiencing latency."

    if metric in ("CONNECTION", "PING", "ISP1") and event == "DOWN" and group == "G1":
        base = f"{base} Switching to Secondary Service Provider to maintain stable connectivity."

    if (metric in ("PING", "ISP2") and event == "DOWN" and group == "G1") and metric in ("PING", "ISP1") and event == "UP" and group == "G1":
        base = f"{base} Primary Internet Service Provider will now handle all network traffic. You may experience slower internet connectivity at this time."

    if metric in ("CONNECTION", "PING", "ISP1") and event == "UP" and group == "G1":
        base = f"{base} Switching back to Primary Service Provider to maintain performance connectivity."

    if metric in ("CONNECTION", "PING") and location_suffix:
        base = f"{base} - {location_suffix}"

    return base

# ============================================================
# Notification helpers (merged, full-featured)
# ============================================================
def notify_clients(db: Session, template_name: str, connection_name: str = None,
    group_name: str | None = None):
    if not template_name:
        logger.warning("notify_clients() called without template_name")
        return

    template_key = template_name.replace("_", "-").upper()
    parts = _parse_template_key(template_key)
    metric = _get_metric(parts)
    is_spike = _is_spike(parts)
    event = _get_event(parts)

    template = db.query(models.Template).filter(
        models.Template.title == template_key).first()
    if not template:
        content_default = _compose_message(template_key, connection_name or "",
                                           False)
        template = models.Template(title=template_key, content=content_default)
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"🆕 Template '{template_key}' created with default content.")

    if metric in ("CONNECTION", "PING") or any(p.startswith("ISP") for p in parts):
        from sqlalchemy import and_

        base_query = db.query(models.Client)
        if group_name:
            base_query = base_query.filter(models.Client.group_name == group_name)

        non_admins = base_query.filter(
            ~models.Client.connection_name.ilike("%ADMIN%")).all()
        for client in non_admins:
            msg = _compose_message(template_key, client.connection_name, False)
            try:
                resp = send_message(client.messenger_id, msg)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            db.add(models.MessageLog(client_id=client.id, template_id=template.id,
                                     status=status))
            db.commit()
            logger.info(
                f"📩 Notified NON-ADMIN {client.name} ({client.connection_name}) with '{template_key}'")

        admins = base_query.filter(
            models.Client.connection_name.ilike("%ADMIN%")).all()
        for client in admins:
            msg = _compose_message(template_key, client.connection_name, True)
            try:
                resp = send_message(client.messenger_id, msg)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            db.add(models.MessageLog(client_id=client.id, template_id=template.id,
                                     status=status))
            db.commit()
            logger.info(
                f"📩 Notified ADMIN {client.name} ({client.connection_name}) with '{template_key}'")

        return

    if metric in ("VENDO", "PRIVATE"):
        candidates = (
            db.query(models.Client)
            .filter(
                models.Client.group_name == group_name,
                models.Client.connection_name == connection_name,
                ~models.Client.connection_name.ilike("%ADMIN%")
            )
            .all()
        )

        for client in candidates:
            client_conn = client.connection_name or ""
            client_is_admin = "ADMIN" in client_conn.upper()

            # ❌ NEW RULE: PRIVATE + (UNPAID or CUT_OFF) = NO NOTIFICATION
            if metric == "PRIVATE" and client.status in (BillingStatus.UNPAID,
                                                         BillingStatus.CUTOFF):
              logger.info(
                f"⏭️ Skipping notification for PRIVATE client {client.name} "
                f"({client.connection_name}) because status = {client.status}"
              )
              continue

            if is_spike:
                if metric == "PRIVATE":
                    if client.status == BillingStatus.LIMITED:
                        message_text = (
                            "⚠️ Connection is unstable. This may be due to LIMITED CONNECTION POLICY. "
                            "Please settle your payment to restore full service."
                        )
                    else:
                        message_text = (
                            "⚠️ Your connection is unstable. Kindly check the cables and indicator lights. "
                            "The black device should show 5 lights and the white device should not have a red light. "
                            "Please report to the administrator if the issue persists or if no action is taken within a day."
                        )
                else:
                    message_text = (
                        "⚠️ Vendo is unstable. Kindly check the cables and indicator light. "
                        "The black device should show 5 lights. "
                        "Please report to the administrator if the issue persists or if no action is taken within a day."
                    )
            else:
                message_text = _compose_message(template_key, client_conn,
                                                client_is_admin)

            try:
                resp = send_message(client.messenger_id, message_text)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"

            db.add(models.MessageLog(client_id=client.id, template_id=template.id,
                                     status=status))
            db.commit()

            logger.info(
                f"📩 Notified NON-ADMIN {client.name} ({client.connection_name}) with '{template_key}'"
            )

        admin_clients = (
            db.query(models.Client)
            .filter(
                models.Client.group_name == group_name,
                models.Client.connection_name.ilike("%ADMIN%")
            )
            .all()
        )

        cn = connection_name or metric

        if is_spike:
            notify_admin(
                db,
                group_name,
                cn,
                candidates[0].status if candidates else None,
                template_key,
            )
        else:
            for admin in admin_clients:
                if metric == "VENDO":
                    prefix = "🏧 [VENDO Alert]"
                else:
                    prefix = "🔒 [PRIVATE Alert]"

                if event == "UP":
                    msg = f"{prefix} {cn} is now up and running smoothly."
                else:
                    msg = f"{prefix} {cn} is currently down. Please check the cable and plug."

                try:
                    resp = send_message(admin.messenger_id, msg)
                    status = resp.get("message_id", "failed")
                except Exception:
                    status = "failed"

                db.add(models.MessageLog(client_id=admin.id, template_id=template.id,
                                         status=status))
                db.commit()

                logger.info(
                    f"📩 [ADMIN NOTICE] {admin.name} ({admin.connection_name}) received '{template_key}' for {cn}"
                )

        return

    query = db.query(models.Client)
    if connection_name:
        from sqlalchemy import or_
        query = query.filter(
            or_(
                models.Client.connection_name == connection_name,
                models.Client.connection_name.ilike(f"{connection_name}%"),
                models.Client.connection_name.ilike(f"%{connection_name}%"),
            )
        )
    if group_name:
        query = query.filter(models.Client.group_name == group_name)

    for client in query.all():
        msg = _compose_message(template_key, client.connection_name,
                               "ADMIN" in (client.connection_name or "").upper())
        try:
            resp = send_message(client.messenger_id, msg)
            status = resp.get("message_id", "failed")
        except Exception:
            status = "failed"
        db.add(models.MessageLog(client_id=client.id, template_id=template.id,
                                 status=status))
        db.commit()
        logger.info(
            f"📩 Notified {client.name} ({client.connection_name}) with '{template_key}'")


def notify_admin(db: Session, group_name: str, connection_name: str,
    status: str, template_key: str, msg_normal: str = None):
    cn = connection_name

    admin_clients = (
        db.query(models.Client)
        .filter(
            models.Client.group_name == group_name,
            models.Client.connection_name.ilike("%ADMIN%")
        )
        .all()
    )

    if not msg_normal:
        if status == BillingStatus.LIMITED:
            admin_msg = (
                f"⚠️ {cn} has been spiking for 10 minutes. "
                f"This may be due to LIMITED CONNECTION POLICY of the private connection."
            )
        else:
            admin_msg = (
                f"⚠️ {cn} has been spiking for 10 minutes. "
                f"Please check the site and visit to verify."
            )
    else:
        admin_msg = msg_normal

    for admin in admin_clients:
        try:
            send_message(admin.messenger_id, admin_msg)
            logger.info(
                f"📩 Notified ADMIN {admin.name} ({admin.connection_name}) with '{template_key}'"
            )
        except Exception as e:
            logger.error(f"Sending failed for ADMIN Notification: {e}")


def schedule_notify(state_key: str, template_name: str, connection_name: str,
    group_name: str, new_state: str):
    flip_history = getattr(schedule_notify, "_flip_history", {})
    setattr(schedule_notify, "_flip_history", flip_history)
    COOLDOWN = 120
    cooldown_state = getattr(schedule_notify, "_cooldown_state", {})
    setattr(schedule_notify, "_cooldown_state", cooldown_state)

    if timers.get(state_key) and timers[state_key].is_alive():
        logger.info(
            f"[{state_key}] Notification already scheduled, skipping duplicate.")
        return

    now = time.time()
    entry = flip_history.setdefault(
        state_key,
        {
            "flips": [],
            "spike_start": None,
            "spike_notified": False,
            "early_spike_sent": False,
            "recovery_sent": False,
            "cycle_id": 0,
        },
    )
    entry["flips"].append(now)
    cutoff = now - SPIKE_FLAP_WINDOW
    entry["flips"] = [t for t in entry["flips"] if t >= cutoff]

    recent_flips = [t for t in entry["flips"] if t >= now - EARLY_SPIKE_WINDOW]
    if len(recent_flips) >= EARLY_SPIKE_THRESHOLD and not entry.get("early_spike_sent", False):
        logger.warning(f"[{state_key}] ⚠️ Rapid flipping detected ({len(recent_flips)} in {EARLY_SPIKE_WINDOW//60}min) → Early SPIKE DOWN")
        db = SessionLocal()
        try:
            try:
                clients = db.query(models.Client).filter(
                    models.Client.connection_name == connection_name,
                    models.Client.group_name == group_name,
                ).all()
            except Exception:
                clients = []

            for c in clients:
                c.state = "DOWN"
                db.add(c)
            db.commit()

            spike_key = f"{connection_name}-{group_name}-SPIKE-DOWN".upper()
            notify_clients(db, spike_key, connection_name, group_name)

            entry["early_spike_sent"] = True
            entry["cycle_id"] = (entry.get("cycle_id", 0) or 0) + 1
            entry["recovery_sent"] = False
            if entry.get("spike_start") is None:
                entry["spike_start"] = recent_flips[0]

            flap_count_recent = len(entry["flips"])
            adaptive_hold = HOLD_LEVELS[0][1]
            for threshold, hold_time in HOLD_LEVELS:
                if flap_count_recent >= threshold:
                    adaptive_hold = hold_time
            entry["hold_down_until"] = time.time() + adaptive_hold
            logger.info(f"[{state_key}] Hold-down set to {adaptive_hold/60:.0f} minutes (flaps={flap_count_recent})")

        except Exception as e:
            logger.error(f"[{state_key}] Failed to process early spike: {e}")
            db.rollback()
        finally:
            db.close()

    if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD:
        if entry["spike_start"] is None:
            entry["spike_start"] = entry["flips"][0]
            logger.info(f"[{state_key}] Spiking detected, spike_start set to {entry['spike_start']}")
            if not entry.get("hold_down_until"):
                flap_count_recent = len(entry["flips"])
                adaptive_hold = HOLD_LEVELS[0][1]
                for threshold, hold_time in HOLD_LEVELS:
                    if flap_count_recent >= threshold:
                        adaptive_hold = hold_time
                entry["hold_down_until"] = time.time() + adaptive_hold
                logger.info(f"[{state_key}] Hold-down set to {adaptive_hold/60:.0f} minutes (flaps={flap_count_recent})")

    def task():
        start = time.time()
        stable_start = start
        flap_count = 0
        logger.info(
            f"[{state_key}] Waiting {DELAY}s stability window for {new_state}")

        while time.time() - start < DELAY:
            current = last_state.get(state_key)
            if current != new_state:
                flap_count += 1
                stable_start = time.time()
                now_inner = time.time()
                entry["flips"].append(now_inner)
                cutoff_inner = now_inner - SPIKE_FLAP_WINDOW
                entry["flips"] = [t for t in entry["flips"] if t >= cutoff_inner]
                if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD and entry["spike_start"] is None:
                    entry["spike_start"] = entry["flips"][0]
                    logger.info(f"[{state_key}] Spiking detected (during wait), spike_start set to {entry['spike_start']}")
                logger.info(
                    f"[{state_key}] Flap detected ({current} != {new_state}), resetting timer")
            if time.time() - stable_start >= 60:
                break
            time.sleep(5)

        final_state = last_state.get(state_key)
        if final_state != new_state:
            logger.info(
                f"[{state_key}] State changed again before sending, cancelled")
            timers.pop(state_key, None)
            return

        spike_start = entry.get("spike_start")
        spike_notified = entry.get("spike_notified", False)
        now_send = time.time()

        if spike_start and (now_send - spike_start >= SPIKE_ESCALATE_SECONDS) and not spike_notified:
            spike_template_key = f"{connection_name}-{group_name}-SPIKE-DOWN".upper()
            logger.info(f"[{state_key}] Spiking persisted >= {SPIKE_ESCALATE_SECONDS}s → sending SPIKE alert ({spike_template_key})")
            db = SessionLocal()
            try:
                notify_clients(db, spike_template_key, connection_name, group_name)
                entry["spike_notified"] = True
            finally:
                db.close()

            timers.pop(state_key, None)
            return

        hold_until = entry.get("hold_down_until")
        if new_state == "DOWN" and hold_until and time.time() < hold_until:
            logger.info(f"[{state_key}] DOWN suppressed due to hold (until {hold_until}). Waiting for stability...")
            while time.time() < hold_until:
                if last_state.get(state_key) != "DOWN":
                    logger.info(f"[{state_key}] State changed while holding (no longer DOWN). Cancel suppressed send.")
                    timers.pop(state_key, None)
                    return
                time.sleep(5)

            stable_confirm_seconds = 60
            stable_check_start = time.time()
            while time.time() - stable_check_start < stable_confirm_seconds:
                if last_state.get(state_key) != "DOWN":
                    logger.info(f"[{state_key}] Not stable during post-hold check. Cancel sending DOWN.")
                    timers.pop(state_key, None)
                    return
                time.sleep(5)
            logger.info(f"[{state_key}] Hold expired and connection stable for {stable_confirm_seconds}s. Proceeding with DOWN notification.")
            entry.pop("hold_down_until", None)

        if entry.get("early_spike_sent", False):
            spike_time = entry.get("spike_start")
            if spike_time and (now_send - spike_time >= STABLE_CLEAR_WINDOW) and not entry.get("recovery_sent", False):
                logger.info(f"[{state_key}] Early spike cycle stabilized → sending SPIKE-UP")
                db = SessionLocal()
                try:
                    spike_up_key = f"{connection_name}-{group_name}-SPIKE-UP".upper()
                    notify_clients(db, spike_up_key, connection_name, group_name)
                    entry["recovery_sent"] = True
                    entry["flips"] = []
                    entry["spike_start"] = None
                    entry["spike_notified"] = False
                    entry["early_spike_sent"] = False
                    entry["cycle_id"] = (entry.get("cycle_id") or 0)
                finally:
                    db.close()

        prev_notified = notified_state.get(state_key)
        if prev_notified == new_state:
            logger.info(f"[{state_key}] {new_state} already notified, skipping")
            timers.pop(state_key, None)
            return

        last_sent_time = cooldown_state.get(state_key, 0)
        if time.time() - last_sent_time < COOLDOWN:
            logger.info(
                f"[{state_key}] Skipping duplicate within cooldown window ({COOLDOWN}s)")
            timers.pop(state_key, None)
            return

        logger.info(
            f"[{state_key}] Stable {new_state} after {flap_count} flaps → sending {template_name}")
        db = SessionLocal()
        try:
            notify_clients(db, template_name, connection_name, group_name)
            notified_state[state_key] = new_state
            cooldown_state[state_key] = time.time()
            if entry.get("spike_start"):
                logger.info(f"[{state_key}] Clearing spike history (stabilized).")
                entry["flips"] = []
                entry["spike_start"] = None
                entry["spike_notified"] = False
                entry["early_spike_sent"] = False
                entry["recovery_sent"] = False
        finally:
            db.close()

        timers.pop(state_key, None)

    t = threading.Thread(target=task, daemon=True)
    timers[state_key] = t
    t.start()


# ============================================================
# WebSocket helper
# ============================================================
def broadcast_state_change(ws_manager, client: models.Client,
                           connection_name: str, new_state: str):
    if not ws_manager:
        return

    payload = {
        "event": "state_update",
        "id": int(getattr(client, "id", 0)),
        "messenger_id": getattr(client, "messenger_id", None),
        "client": getattr(client, "name", "Unknown"),
        "connection_name": connection_name,
        "state": new_state,
        "timestamp": time.time(),
    }

    try:
        ws_manager.safe_broadcast(payload)
    except Exception as e:
        logger.error(f"WebSocket broadcast failed: {e}")


# ============================================================
# Core processing
# ============================================================
def process_rule(
    db: Session,
    client: models.Client,
    connection_name: str,
    last_state_value: str,
    group_name: str,
    ws_manager=None,
    is_primary: bool = True,
):
    key = f"{connection_name}_{group_name}"

    if client:
        if client.state != last_state_value:
            logger.info(
                f"🔄 {client.name} ({connection_name}) {client.state} → {last_state_value}"
            )

            broadcast_state_change(ws_manager, client, connection_name,
                                   last_state_value)

            template_name = (
                f"{connection_name}-{group_name}-{last_state_value}"
                .replace("_", "-")
                .upper()
            )

            prev_state = last_state.get(key)
            prev_notified = notified_state.get(key)

            if prev_state == last_state_value and prev_notified == last_state_value:
                logger.info(
                    f"[{key}] State remains {last_state_value}, already notified → skip"
                )
                return

            if is_primary:
                schedule_notify(
                    key, template_name, connection_name, group_name, last_state_value
                )

            client.state = last_state_value
            db.add(client)
    else:
        broadcast_state_change(
            ws_manager,
            models.Client(id=0, messenger_id=None, name="Unknown"),
            connection_name,
            last_state_value,
        )

    last_state[key] = last_state_value


# ============================================================
# Polling logic (with group router connectivity handling)
# ============================================================
def poll_netwatch(
    host: str,
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    group_name: str = None,
):
    from sqlalchemy import or_

    mikrotik = MikroTikClient(host, username, password)

    # initialize group status if not present
    if group_name and group_name not in group_router_status:
        group_router_status[group_name] = None

    while True:
        # First, check router connectivity using ensure_connection()
        connected = False
        try:
            connected = mikrotik.ensure_connection()
        except Exception as e:
            logger.error(f"Error while checking connection to {host}: {e}")
            connected = False

        db: Session = next(get_db())
        try:
            # If router is unreachable, handle group-wide DOWN
            if not connected:
                prev = group_router_status.get(group_name)
                # Only act if status changed or unknown -> DOWN
                if prev != "DOWN":
                    logger.warning(f"🚨 Mikrotik for group {group_name} ({host}) is unreachable. Marking PRIVATE/VENDO as DOWN and notifying group.")

                    # Mark PRIVATE and VENDO clients as DOWN
                    affected = (
                        db.query(models.Client)
                        .filter(
                            models.Client.group_name == group_name,
                            (
                                models.Client.connection_name.ilike("%PRIVATE%")
                                | models.Client.connection_name.ilike("%VENDO%")
                            ),
                        )
                        .all()
                    )

                    for c in affected:
                        if c.state != "DOWN":
                            c.state = "DOWN"
                            db.add(c)
                    db.commit()

                    # Send group-wide message to Admin + Private + Vendo in group
                    recipients = (
                        db.query(models.Client)
                        .filter(
                            models.Client.group_name == group_name,
                            (
                                models.Client.connection_name.ilike("%ADMIN%")
                                | models.Client.connection_name.ilike("%PRIVATE%")
                                | models.Client.connection_name.ilike("%VENDO%")
                            )
                        )
                        .all()
                    )

                    msg = GROUP_PROVIDER_DOWN_MSG.get(group_name, "⚠️ All Service Providers are down.")
                    for r in recipients:
                        try:
                            send_message(r.messenger_id, msg)
                        except Exception as e:
                            logger.error(f"Failed to send group-down message to {r.name}: {e}")

                    group_router_status[group_name] = "DOWN"
                else:
                    # status already DOWN, no repeated notify
                    logger.debug(f"Group {group_name} already marked DOWN; skipping repeated group handling.")

                # Skip per-rule polling while router not reachable
                db.close()
                time.sleep(interval)
                continue

            # Router is reachable
            prev = group_router_status.get(group_name)
            if prev == "DOWN":
                # Transition DOWN -> UP: restore states and notify once
                logger.info(f"🔺 Mikrotik for group {group_name} ({host}) recovered. Marking PRIVATE/VENDO as UP and notifying group.")

                down_clients = (
                    db.query(models.Client)
                    .filter(
                        models.Client.group_name == group_name,
                        models.Client.state == "DOWN",
                        (
                            models.Client.connection_name.ilike("%PRIVATE%")
                            | models.Client.connection_name.ilike("%VENDO%")
                        )
                    )
                    .all()
                )

                for c in down_clients:
                    c.state = "UP"
                    db.add(c)
                db.commit()

                recipients = (
                    db.query(models.Client)
                    .filter(
                        models.Client.group_name == group_name,
                        (
                            models.Client.connection_name.ilike("%ADMIN%")
                            | models.Client.connection_name.ilike("%PRIVATE%")
                            | models.Client.connection_name.ilike("%VENDO%")
                        )
                    )
                    .all()
                )

                msg = GROUP_PROVIDER_UP_MSG.get(group_name, "✅ All Service Providers are restored.")
                for r in recipients:
                    try:
                        send_message(r.messenger_id, msg)
                    except Exception as e:
                        logger.error(f"Failed to send group-up message to {r.name}: {e}")

                group_router_status[group_name] = "UP"
            else:
                # Nothing to do for group status transition; ensure it's set to UP
                group_router_status[group_name] = "UP"

            # Proceed with normal netwatch rules polling
            rules = mikrotik.get_netwatch()
            if not rules:
                logger.warning(f"⚠️ No Netwatch rules found for {host}")
                db.close()
                time.sleep(interval)
                continue

            seen_connections = []

            for rule in rules:
                connection_name = rule.get("comment") or rule.get("host")
                connection_name = (
                    connection_name.replace("_", "-") if connection_name else connection_name
                )
                current_state = (rule.get("status") or "unknown").upper()
                seen_connections.append(connection_name)

                key = f"{connection_name}_{group_name}"
                prev_state = last_state.get(key)
                if current_state == "UNKNOWN":
                    logger.debug(
                        f"[{key}] Ignoring transient UNKNOWN (keeping {prev_state})")
                    continue

                if prev_state and prev_state != current_state:
                    time.sleep(2)
                    confirm = (rule.get("status") or current_state).upper()
                    if confirm != current_state:
                        logger.debug(f"[{key}] Ignored flicker {current_state} → {confirm}")
                        continue

                clients = (
                    db.query(models.Client)
                    .filter(
                        or_(
                            models.Client.connection_name == connection_name,
                            models.Client.connection_name.ilike(f"{connection_name}%"),
                            models.Client.connection_name.ilike(f"%{connection_name}%"),
                        )
                    )
                    .all()
                )

                if not clients:
                    logger.debug(f"No clients found for connection {connection_name}")
                    continue

                for i, client in enumerate(clients):
                    effective_group = getattr(client, "group_name",
                                              None) or group_name or "default"
                    is_primary = i == 0
                    process_rule(
                        db,
                        client,
                        connection_name,
                        current_state,
                        effective_group,
                        ws_manager,
                        is_primary=is_primary,
                    )

                db.commit()

            # Mark unmatched clients as UNKNOWN (unchanged)
            all_clients = db.query(models.Client).filter(
                models.Client.group_name == group_name
            ).all()

            def is_seen(client_name: str | None, seen_list: list[str | None]) -> bool:
                if not client_name:
                    return False
                cname = client_name.lower()
                for s in seen_list:
                    if not s:
                        continue
                    s_lower = s.lower()
                    if s_lower == cname or s_lower.startswith(cname):
                        return True
                return False

            for client in all_clients:
                if not is_seen(client.connection_name, seen_connections):
                    if client.state != "UNKNOWN":
                        logger.info(
                            f"🔄 {client.connection_name} → UNKNOWN (not matched in Netwatch)"
                        )
                        process_rule(
                            db, client, client.connection_name, "UNKNOWN", group_name,
                            ws_manager
                        )
            db.commit()

            # Cleanup stale states
            active_keys = {f"{c.connection_name}_{group_name}" for c in all_clients}
            stale_keys = [
                key for key in list(last_state.keys()) if key not in active_keys
            ]
            if stale_keys:
                for key in stale_keys:
                    timers.pop(key, None)
                    notified_state.pop(key, None)
                    last_state.pop(key, None)
                logger.info(
                    f"🧹 Cleaned up {len(stale_keys)} stale state entr"
                    f"{'y' if len(stale_keys) == 1 else 'ies'}."
                )

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error updating client states for {host}: {e}")
        finally:
            try:
                db.close()
            except Exception:
                pass

        time.sleep(interval)


def initialize_state_cache():
    db = SessionLocal()
    try:
        clients = db.query(models.Client).all()
        for c in clients:
            group = c.group_name or "default"
            key = f"{c.connection_name}_{group}"
            last_state[key] = c.state or "UNKNOWN"
            notified_state[key] = None
        logger.info(f"🧠 Initialized state cache for {len(clients)} clients (notified_state cleared).")
    except Exception as e:
        logger.error(f"❌ Failed to initialize state cache: {e}")
    finally:
        db.close()


# ============================================================
# Start polling threads per router group
# ============================================================
def start_polling(username: str, password: str, interval: int = 30,
    ws_manager=None, router_map=None):
    routers = router_map or ROUTER_MAP

    initialize_state_cache()

    for group_name, host in routers.items():
        # initialize group_router_status
        group_router_status.setdefault(group_name, None)

        thread = threading.Thread(
            target=poll_netwatch,
            args=(host, username, password, interval, ws_manager, group_name),
            daemon=True,
        )
        thread.start()
        logger.info(
            f"✅ Started Netwatch polling for group '{group_name}' at {host}")

# app/utils/mikrotik_poll.py
import time
import threading
import logging
import os
import json
from typing import Optional, Dict, Any
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("mikrotik_poll")
logger.setLevel(logging.INFO)

# ============================================================
# Configuration / Defaults
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

GROUP_LOCATION = {"G1": "MALUNGON", "G2": "SURALLAH"}

# Notification debounce / scheduling defaults
DELAY = 90  # seconds to wait for stability before sending a regular UP/DOWN notification
COOLDOWN = 120  # seconds between sending the same notification for the same key

# Spike (flapping) detection defaults (confirmed)
SPIKE_FLAP_WINDOW = 5 * 60       # 5 minutes window to count flaps
SPIKE_FLAP_THRESHOLD = 3         # >=3 flips in the window => considered flapping
SPIKE_ESCALATE_SECONDS = 10 * 60 # 10 minutes of continuous spiking before SPIKE escalation

# ============================================================
# Shared runtime state (thread-safe access via lock)
# ============================================================
_state_lock = threading.Lock()
last_state: Dict[str, str] = {}       # key -> last observed state (UP/DOWN/UNKNOWN)
notified_state: Dict[str, Optional[str]] = {}   # key -> last state that was actually notified
timers: Dict[str, threading.Thread] = {}        # key -> current notify thread
# flip_history stores per-state_key info for spiking detection
flip_history: Dict[str, Dict[str, Any]] = {}
# cooldown_state stores last sent timestamp per key
cooldown_state: Dict[str, float] = {}

# ============================================================
# Helper parsing / composition functions (kept from your design)
# ============================================================
def _parse_template_key(template_name: str) -> list:
    if not template_name:
        return []
    key = template_name.replace("_", "-").upper()
    parts = [p.strip() for p in key.split("-") if p.strip()]
    return parts


def _is_spike(parts: list[str]) -> bool:
    return "SPIKE" in parts


def _get_event(parts: list[str]) -> Optional[str]:
    if "UP" in parts:
        return "UP"
    if "DOWN" in parts:
        return "DOWN"
    return None


def _get_group(parts: list[str]) -> Optional[str]:
    for p in parts:
        if p.startswith("G"):
            return p
    return None


def _get_metric(parts: list[str]) -> Optional[str]:
    if "PING" in parts:
        return "PING"
    if "CONNECTION" in parts:
        return "CONNECTION"
    if any(p == "VENDO" for p in parts):
        return "VENDO"
    if any(p == "PRIVATE" for p in parts):
        return "PRIVATE"
    return None


def _get_isp_token(parts: list[str]) -> Optional[str]:
    for p in parts:
        if p.startswith("ISP"):
            return p
    return None


def _service_label_from_isp(isp_token: Optional[str]) -> Optional[str]:
    if isp_token == "ISP1":
        return "Primary Service Provider"
    if isp_token == "ISP2":
        return "Secondary Service Provider"
    if isp_token == "ISP":
        return "PLDT Provider"
    return None


def _compose_message(template_name: str, client_conn_name: Optional[str],
                     client_is_admin: bool) -> str:
    """Compose message text according to your specification (fallback)."""
    parts = _parse_template_key(template_name)
    is_spike = _is_spike(parts)
    event = _get_event(parts)
    group = _get_group(parts)
    metric = _get_metric(parts)
    isp_token = _get_isp_token(parts)
    service_label = _service_label_from_isp(isp_token)
    location_suffix = GROUP_LOCATION.get(group, "")

    base = "Notification."

    # NORMAL (non-spike)
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

    # SPIKE messages (fallback)
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

    # Append location suffix only for ISP-type notifications (CONNECTION/PING)
    if metric in ("CONNECTION", "PING") and location_suffix:
        base = f"{base} - {location_suffix}"

    return base

# ============================================================
# notify_clients() - unchanged functional behavior, with safe DB usage
# ============================================================
def notify_clients(db: Session, template_name: str, connection_name: Optional[str] = None,
                   group_name: Optional[str] = None):
    if not template_name:
        logger.warning("notify_clients() called without template_name")
        return

    template_key = template_name.replace("_", "-").upper()
    parts = _parse_template_key(template_key)
    metric = _get_metric(parts)
    is_spike = _is_spike(parts)
    event = _get_event(parts)

    # Ensure template row exists
    template = db.query(models.Template).filter(models.Template.title == template_key).first()
    if not template:
        content_default = _compose_message(template_key, connection_name or "", False)
        template = models.Template(title=template_key, content=content_default)
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"🆕 Template '{template_key}' created with default content.")

    # ISP / PING / CONNECTION / ISPx handling
    if metric in ("CONNECTION", "PING") or any(p.startswith("ISP") for p in parts):
        from sqlalchemy import and_

        base_query = db.query(models.Client)
        if group_name:
            base_query = base_query.filter(models.Client.group_name == group_name)

        # Non-admins
        non_admins = base_query.filter(~models.Client.connection_name.ilike("%ADMIN%")).all()
        for client in non_admins:
            msg = _compose_message(template_key, client.connection_name, False)
            try:
                resp = send_message(client.messenger_id, msg)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            db.add(models.MessageLog(client_id=client.id, template_id=template.id, status=status))
            db.commit()
            logger.info(f"📩 Notified NON-ADMIN {client.name} ({client.connection_name}) with '{template_key}'")

        # Admins
        admins = base_query.filter(models.Client.connection_name.ilike("%ADMIN%")).all()
        for client in admins:
            msg = _compose_message(template_key, client.connection_name, True)
            try:
                resp = send_message(client.messenger_id, msg)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            db.add(models.MessageLog(client_id=client.id, template_id=template.id, status=status))
            db.commit()
            logger.info(f"📩 Notified ADMIN {client.name} ({client.connection_name}) with '{template_key}'")
        return

    # VENDO / PRIVATE handling (same logic / grammar you already used)
    if metric in ("VENDO", "PRIVATE"):
        from sqlalchemy import or_

        base_query = db.query(models.Client)
        if group_name:
            base_query = base_query.filter(models.Client.group_name == group_name)

        if connection_name:
            candidates = base_query.filter(
                or_(
                    models.Client.connection_name == connection_name,
                    models.Client.connection_name.ilike(f"{connection_name}%"),
                    models.Client.connection_name.ilike(f"%{connection_name}%"),
                )
            ).all()
        else:
            candidates = base_query.filter(models.Client.connection_name.ilike(f"%{metric}%")).all()

        if not candidates:
            logger.info(f"No mapped clients found for {metric} ({connection_name})")
            return

        # Notify mapped clients
        for client in candidates:
            client_conn = client.connection_name or ""
            client_is_admin = "ADMIN" in client_conn.upper()

            if is_spike:
                if client_is_admin:
                    cn = connection_name or client_conn or metric
                    admin_msg = f"{cn} has been spiking for 10 minutes. Please check the site and visit to verify."
                    message_text = admin_msg
                else:
                    if metric == "PRIVATE":
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
                message_text = _compose_message(template_key, client_conn, client_is_admin)

            try:
                resp = send_message(client.messenger_id, message_text)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"

            db.add(models.MessageLog(client_id=client.id, template_id=template.id, status=status))
            db.commit()
            logger.info(f"📩 Notified {'ADMIN' if client_is_admin else 'NON-ADMIN'} {client.name} ({client.connection_name}) with '{template_key}'")

        # Also notify admins in same group
        admin_clients = db.query(models.Client).filter(
            models.Client.group_name == group_name,
            models.Client.connection_name.ilike("%ADMIN%")
        ).all()

        cn = connection_name or metric
        for admin in admin_clients:
            if is_spike:
                msg = f"{cn} has been spiking for 10 minutes. Please check the site and visit to verify."
            else:
                prefix = "🏧 [VENDO Alert]" if metric == "VENDO" else "🔒 [PRIVATE Alert]"
                if _get_event(parts) == "UP":
                    msg = f"{prefix} {cn} is now up and running smoothly."
                else:
                    msg = f"{prefix} {cn} is currently down. Please check the cable and plug."

            try:
                resp = send_message(admin.messenger_id, msg)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"

            db.add(models.MessageLog(client_id=admin.id, template_id=template.id, status=status))
            db.commit()
            logger.info(f"📩 [ADMIN NOTICE] {admin.name} ({admin.connection_name}) received '{template_key}' for {cn}")
        return

    # Generic fallback send (if not ISP/VENDO/PRIVATE)
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
        msg = _compose_message(template_key, client.connection_name, "ADMIN" in (client.connection_name or "").upper())
        try:
            resp = send_message(client.messenger_id, msg)
            status = resp.get("message_id", "failed")
        except Exception:
            status = "failed"
        db.add(models.MessageLog(client_id=client.id, template_id=template.id, status=status))
        db.commit()
        logger.info(f"📩 Notified {client.name} ({client.connection_name}) with '{template_key}'")

# ============================================================
# schedule_notify() - thread-safe, with early instability advisory and escalation
# ============================================================
def schedule_notify(state_key: str, template_name: str, connection_name: str,
                    group_name: str, new_state: str):
    """
    Debounced notifier that:
      - waits for DELAY seconds of stability before sending regular UP/DOWN
      - detects flapping (spikes) and sends:
         * an EARLY instability advisory when flips >= SPIKE_FLAP_THRESHOLD inside SPIKE_FLAP_WINDOW
         * a SPIKE escalation alert if spiking persists for SPIKE_ESCALATE_SECONDS
      - enforces per-key cooldowns to avoid spam
    """

    # Avoid duplicate concurrent threads for same state_key
    with _state_lock:
        running = timers.get(state_key)
        if running and running.is_alive():
            logger.info(f"[{state_key}] Notification already scheduled, skipping duplicate.")
            return

    now = time.time()

    # Update flip history for spike detection (thread-safe)
    with _state_lock:
        entry = flip_history.setdefault(state_key, {
            "flips": [],
            "spike_start": None,
            "spike_notified": False,
            "early_notified": False,  # tracks the early instability advisory send
        })
        entry["flips"].append(now)
        cutoff = now - SPIKE_FLAP_WINDOW
        entry["flips"] = [t for t in entry["flips"] if t >= cutoff]

        # If flips exceed threshold and spike_start not yet set -> set it
        if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD:
            if entry["spike_start"] is None:
                entry["spike_start"] = entry["flips"][0]
                logger.info(f"[{state_key}] Spiking detected, spike_start set to {entry['spike_start']}")

            # Early instability advisory: send once per spike event
            if not entry.get("early_notified", False):
                # Build a sensible unstable template for ISP1 (we keep naming pattern)
                # Prefer using CONNECTION metric for early advisory unless template includes PING
                parts = _parse_template_key(template_name)
                metric = _get_metric(parts) or "CONNECTION"
                isp_token = _get_isp_token(parts) or ("ISP1" if "ISP1" in state_key.upper() else None)

                if isp_token == "ISP1" or (connection_name and "ISP1" in connection_name.upper()) or (template_name and "ISP1" in template_name.upper()):
                    unstable_template_key = f"{isp_token or 'ISP1'}-{metric}-{group_name}-DOWN".upper()
                    logger.info(f"[{state_key}] Sending early instability advisory ({unstable_template_key})")
                    db = SessionLocal()
                    try:
                        notify_clients(db, unstable_template_key, connection_name, group_name)
                        entry["early_notified"] = True
                        # set cooldown for this key to avoid immediate repeats
                        cooldown_state[state_key] = time.time()
                    finally:
                        db.close()

    def _task():
        start = time.time()
        stable_start = start
        flap_count = 0
        logger.info(f"[{state_key}] Waiting {DELAY}s stability window for {new_state}")

        while time.time() - start < DELAY:
            with _state_lock:
                current = last_state.get(state_key)
            if current != new_state:
                flap_count += 1
                stable_start = time.time()
                # update flip history while waiting
                with _state_lock:
                    entry = flip_history.setdefault(state_key, {"flips": [],
                                                                "spike_start": None,
                                                                "spike_notified": False})
                    entry["flips"].append(now)
                    entry["flips"] = [t for t in entry["flips"] if t >= cutoff]

                    if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD:
                      if entry["spike_start"] is None:
                        entry["spike_start"] = entry["flips"][0]
                        logger.info(
                          f"[{state_key}] Spiking detected, spike_start set to {entry['spike_start']}")
                logger.info(f"[{state_key}] Flap detected ({current} != {new_state}), resetting timer")
            if time.time() - stable_start >= 60:  # stable for at least 60s
                break
            time.sleep(5)

        # Confirm final stable state
        with _state_lock:
            final_state = last_state.get(state_key)
        if final_state != new_state:
            logger.info(f"[{state_key}] State changed again before sending, cancelled")
            with _state_lock:
                timers.pop(state_key, None)
            return

        now_send = time.time()

        # Re-fetch entry safely
        with _state_lock:
            entry = flip_history.setdefault(state_key, {
                "flips": [],
                "spike_start": None,
                "spike_notified": False,
                "early_notified": False
            })
            spike_start = entry.get("spike_start")
            spike_notified = entry.get("spike_notified", False)

        # If spiking and has lasted SPIKE_ESCALATE_SECONDS -> send SPIKE escalation alert
        if spike_start and (now_send - spike_start >= SPIKE_ESCALATE_SECONDS) and not spike_notified:
            parts = _parse_template_key(template_name)
            metric = _get_metric(parts) or ("PING" if "PING" in template_name.upper() else "CONNECTION")
            spike_template_key = f"{metric}-SPIKE-{group_name}-DOWN".upper()
            logger.info(f"[{state_key}] Spiking persisted >= {SPIKE_ESCALATE_SECONDS}s → sending SPIKE alert ({spike_template_key})")
            db = SessionLocal()
            try:
                notify_clients(db, spike_template_key, connection_name, group_name)
                with _state_lock:
                    entry["spike_notified"] = True
                # Do not proceed with normal same-state notification after spike alert
            finally:
                db.close()
            with _state_lock:
                timers.pop(state_key, None)
            return

        # Debounce repeated notifications for same stable state
        with _state_lock:
            prev_notified = notified_state.get(state_key)
            last_sent_time = cooldown_state.get(state_key, 0)

        if prev_notified == new_state:
            logger.info(f"[{state_key}] {new_state} already notified, skipping")
            with _state_lock:
                timers.pop(state_key, None)
            return

        if time.time() - last_sent_time < COOLDOWN:
            logger.info(f"[{state_key}] Skipping duplicate within cooldown window ({COOLDOWN}s)")
            with _state_lock:
                timers.pop(state_key, None)
            return

        # Normal send
        logger.info(f"[{state_key}] Stable {new_state} after {flap_count} flaps → sending {template_name}")
        db = SessionLocal()
        try:
            notify_clients(db, template_name, connection_name, group_name)
            with _state_lock:
                notified_state[state_key] = new_state
                cooldown_state[state_key] = time.time()
                # clear spike tracking if stabilized
                if entry.get("spike_start"):
                    logger.info(f"[{state_key}] Clearing spike history (stabilized).")
                    entry["flips"] = []
                    entry["spike_start"] = None
                    entry["spike_notified"] = False
                    entry["early_notified"] = False
        finally:
            db.close()

        with _state_lock:
            timers.pop(state_key, None)

    t = threading.Thread(target=_task, daemon=True)
    with _state_lock:
        timers[state_key] = t
    t.start()

# ============================================================
# WebSocket broadcast helper
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
# process_rule() - process a single observed netwatch rule
# ============================================================
def process_rule(
    db: Session,
    client: Optional[models.Client],
    connection_name: str,
    last_state_value: str,
    group_name: str,
    ws_manager=None,
    is_primary: bool = True,
):
    key = f"{connection_name}_{group_name}"

    if client:
        if client.state != last_state_value:
            logger.info(f"🔄 {client.name} ({connection_name}) {client.state} → {last_state_value}")

            # Broadcast to frontend clients (WebSocket)
            broadcast_state_change(ws_manager, client, connection_name, last_state_value)

            template_name = f"{connection_name}-{group_name}-{last_state_value}".replace("_", "-").upper()

            with _state_lock:
                prev_state = last_state.get(key)
                prev_notified = notified_state.get(key)

            # Skip if same observed and already notified
            if prev_state == last_state_value and prev_notified == last_state_value:
                logger.info(f"[{key}] State remains {last_state_value}, already notified → skip")
            else:
                # Only primary (first client) triggers notification scheduling
                if is_primary:
                    schedule_notify(key, template_name, connection_name, group_name, last_state_value)

            # Update DB client state
            client.state = last_state_value
            db.add(client)
    else:
        # Unknown connection - still broadcast
        broadcast_state_change(
            ws_manager,
            models.Client(id=0, messenger_id=None, name="Unknown"),
            connection_name,
            last_state_value,
        )

    # Update last_state cache
    with _state_lock:
        last_state[key] = last_state_value

# ============================================================
# Polling logic for Netwatch rules
# ============================================================
def poll_netwatch(
    host: str,
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    group_name: Optional[str] = None,
):
    from sqlalchemy import or_

    mikrotik = MikroTikClient(host, username, password)

    while True:
        if not mikrotik.ensure_connection():
            logger.warning(f"❌ Cannot connect to {host}, retrying in {interval}s...")
            time.sleep(interval)
            continue

        rules = mikrotik.get_netwatch()
        if not rules:
            logger.warning(f"⚠️ No Netwatch rules found for {host}")
            time.sleep(interval)
            continue

        db: Session = next(get_db())
        try:
            seen_connections = []

            for rule in rules:
                connection_name = rule.get("comment") or rule.get("host")
                connection_name = (connection_name.replace("_", "-") if connection_name else connection_name)
                current_state = (rule.get("status") or "unknown").upper()
                seen_connections.append(connection_name)

                key = f"{connection_name}_{group_name}"
                prev_state = last_state.get(key)

                # Ignore transient UNKNOWNs
                if current_state == "UNKNOWN":
                    logger.debug(f"[{key}] Ignoring transient UNKNOWN (keeping {prev_state})")
                    continue

                # Debounce confirmation — avoid flickers
                if prev_state and prev_state != current_state:
                    time.sleep(2)
                    confirm = (rule.get("status") or current_state).upper()
                    if confirm != current_state:
                        logger.debug(f"[{key}] Ignored flicker {current_state} → {confirm}")
                        continue

                # Get all clients matching this connection_name
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

                # Process each client; only the first (index 0) triggers notifications
                for i, client in enumerate(clients):
                    effective_group = getattr(client, "group_name", None) or group_name or "default"
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

            # Mark unmatched clients as UNKNOWN
            all_clients = db.query(models.Client).filter(models.Client.group_name == group_name).all()

            def is_seen(client_name: Optional[str], seen_list: list[Optional[str]]) -> bool:
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
                        logger.info(f"🔄 {client.connection_name} → UNKNOWN (not matched in Netwatch)")
                        process_rule(db, client, client.connection_name, "UNKNOWN", group_name, ws_manager)
            db.commit()

            # Cleanup stale states
            active_keys = {f"{c.connection_name}_{group_name}" for c in all_clients}
            with _state_lock:
                stale_keys = [key for key in list(last_state.keys()) if key not in active_keys]
                if stale_keys:
                    for key in stale_keys:
                        timers.pop(key, None)
                        notified_state.pop(key, None)
                        last_state.pop(key, None)
                        flip_history.pop(key, None)
                    logger.info(f"🧹 Cleaned up {len(stale_keys)} stale state entr"
                                f"{'y' if len(stale_keys) == 1 else 'ies'}.")

        except Exception as e:
            db.rollback()
            logger.error(f"❌ Error updating client states for {host}: {e}")
        finally:
            db.close()

        time.sleep(interval)

# ============================================================
# Initialize in-memory cache on startup
# ============================================================
def initialize_state_cache():
    db = SessionLocal()
    try:
        clients = db.query(models.Client).all()
        with _state_lock:
            for c in clients:
                group = c.group_name or "default"
                key = f"{c.connection_name}_{group}"
                last_state[key] = c.state or "UNKNOWN"
                # allow initial notifications since process just started
                notified_state[key] = None
        logger.info(f"🧠 Initialized state cache for {len(clients)} clients (notified_state cleared).")
    except Exception as e:
        logger.error(f"❌ Failed to initialize state cache: {e}")
    finally:
        db.close()

# ============================================================
# Entrypoint to start polling threads
# ============================================================
def start_polling(username: str, password: str, interval: int = 30,
                  ws_manager=None, router_map=None):
    routers = router_map or ROUTER_MAP

    initialize_state_cache()

    for group_name, host in routers.items():
        thread = threading.Thread(
            target=poll_netwatch,
            args=(host, username, password, interval, ws_manager, group_name),
            daemon=True,
        )
        thread.start()
        logger.info(f"✅ Started Netwatch polling for group '{group_name}' at {host}")

# Local helper used by poll_netwatch to get DB session generator
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

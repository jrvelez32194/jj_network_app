# app/utils/mikrotik_poll.py
import time
import threading
import logging
import os
import json
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
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

# ============================================================
# Spike tracking (flip history, spiking windows)
# - flip_history keeps per-key timestamps of flips
# - spike_start indicates when spiking began
# - spike_notified prevents repeated spike alerts
# ============================================================
# stored on schedule_notify function object via attributes
# schedule_notify._flip_history: dict[state_key] -> {"flips": [timestamps], "spike_start": float|None, "spike_notified": bool}
# parameters for detection:
SPIKE_FLAP_WINDOW = 5 * 60      # 5 minutes window to count flaps
SPIKE_FLAP_THRESHOLD = 3        # >=3 flips inside window => considered spiking
SPIKE_ESCALATE_SECONDS = 10 * 60  # 10 minutes of spiking before admin "spiking" alert


# ============================================================
# Message composition helpers and maps
# ============================================================
GROUP_LOCATION = {"G1": "MALUNGON", "G2": "SURALLAH"}


def _parse_template_key(template_name: str) -> list:
    """Normalize and split a template name into parts (tokens)."""
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
  """
  Compose message text according to your specification.
  Admin messages get a location suffix (MALUNGON / SURALLAH) based on group token in template_name.
  This function still acts as a fallback for SPIKE templates if a DB template isn't present.
  """
  parts = _parse_template_key(template_name)
  is_spike = _is_spike(parts)
  event = _get_event(parts)
  group = _get_group(parts)
  metric = _get_metric(parts)
  isp_token = _get_isp_token(parts)
  service_label = _service_label_from_isp(isp_token)

  location_suffix = GROUP_LOCATION.get(group, "")

  # Default fallback messages
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
      # generic fallback
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
      # for quick fallback: non-admin vs admin wording handled elsewhere (notify_clients)
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

  # Append location suffix only for ISP-type notifications (CONNECTION or PING)
  if metric in ("CONNECTION", "PING") and location_suffix:
    base = f"{base} - {location_suffix}"

  return base


# ============================================================
# Notification helpers (merged, full-featured)
# ============================================================
def notify_clients(db: Session, template_name: str, connection_name: str = None,
    group_name: str | None = None):
  """
  Unified notify function that:
    - Parses template_name to detect NORMAL vs SPIKE and VENDO / PRIVATE / ISP
    - Auto-creates Template DB entries when missing (fallback content)
    - Routes messages:
        * ISP: send non-admin wording to non-admin clients, admin wording to admins
        * VENDO/PRIVATE: send to mapped clients + admins in same group (admin gets name-based message)
    - When SPIKE token is present, uses the spiking grammar you're asked for.
  """
  if not template_name:
    logger.warning("notify_clients() called without template_name")
    return

  template_key = template_name.replace("_", "-").upper()
  parts = _parse_template_key(template_key)
  metric = _get_metric(parts)
  is_spike = _is_spike(parts)
  event = _get_event(parts)

  # Ensure template row exists (so logs have a template_id). Use fallback content if missing.
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

  # ============================================================
  # 🛰 ISP (PING / CONNECTION / ISPx)
  # ============================================================
  if metric in ("CONNECTION", "PING") or any(
      p.startswith("ISP") for p in parts):
    from sqlalchemy import and_

    base_query = db.query(models.Client)
    if group_name:
      base_query = base_query.filter(models.Client.group_name == group_name)

    # Non-admin
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

    # Admin
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

  # ============================================================
  # 🧾 VENDO / PRIVATE
  # ============================================================
  if metric in ("VENDO", "PRIVATE"):
    from sqlalchemy import or_

    base_query = db.query(models.Client)
    if group_name:
      base_query = base_query.filter(models.Client.group_name == group_name)

    # Find mapped clients for the connection
    if connection_name:
      candidates = base_query.filter(
        or_(
          models.Client.connection_name == connection_name,
          models.Client.connection_name.ilike(f"{connection_name}%"),
          models.Client.connection_name.ilike(f"%{connection_name}%"),
        )
      ).all()
    else:
      candidates = base_query.filter(
        models.Client.connection_name.ilike(f"%{metric}%")).all()

    if not candidates:
      logger.info(f"No mapped clients found for {metric} ({connection_name})")
      return

    # Notify mapped clients (non-admin/admin content handled)
    for client in candidates:
      client_conn = client.connection_name or ""
      client_is_admin = "ADMIN" in client_conn.upper()

      # If it's a spiking event: override messages with the requested wording
      if is_spike:
        if client_is_admin:
          # Admins: short spiking alert (they asked for {connection} ... healthy/kindly visit)
          cn = connection_name or client_conn or metric
          admin_msg = f"{cn} has been spiking for 10 minutes. Please check the site and visit to verify."
          message_text = admin_msg
        else:
          # Non-admin: send unstable instructions (private/vendo differ slightly)
          if metric == "PRIVATE":
            message_text = (
              "⚠️ Your connection is unstable. Kindly check the cables and indicator lights. "
              "The black device should show 5 lights and the white device should not have a red light. "
              "Please report to the administrator if the issue persists or if no action is taken within a day."
            )
          else:  # VENDO
            message_text = (
              "⚠️ Vendo is unstable. Kindly check the cables and indicator light. "
              "The black device should show 5 lights. "
              "Please report to the administrator if the issue persists or if no action is taken within a day."
            )
      else:
        # Non-spike -> use the normal composition fallback
        message_text = _compose_message(template_key, client_conn, client_is_admin)

      try:
        resp = send_message(client.messenger_id, message_text)
        status = resp.get("message_id", "failed")
      except Exception:
        status = "failed"

      db.add(models.MessageLog(client_id=client.id, template_id=template.id,
                               status=status))
      db.commit()
      logger.info(
        f"📩 Notified {'ADMIN' if client_is_admin else 'NON-ADMIN'} {client.name} ({client.connection_name}) with '{template_key}'")

    # ----------------------------------------------------------
    # 📢 NEW: Also notify all admins in the same group (private/admin must always be notified)
    # If spiking: use spiking admin grammar. Otherwise use up/down messages.
    # ----------------------------------------------------------
    admin_clients = db.query(models.Client).filter(
      models.Client.group_name == group_name,
      models.Client.connection_name.ilike("%ADMIN%")
    ).all()

    cn = connection_name or metric
    for admin in admin_clients:
      if is_spike:
        # Spiking admin message (requested grammar)
        msg = f"{cn} has been spiking for 10 minutes. Please check the site and visit to verify."
      else:
        # Non-spike admin wording - keep previous behavior but improved grammar
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
        f"📩 [ADMIN NOTICE] {admin.name} ({admin.connection_name}) received '{template_key}' for {cn}")

    return

  # ============================================================
  # 🧩 Fallback (generic send)
  # ============================================================
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


def schedule_notify(state_key: str, template_name: str, connection_name: str,
    group_name: str, new_state: str):
  """
  Waits for a stability period (≤DELAYs) before sending a notification.
  Debounces duplicate threads and applies cooldown to avoid notification spam.

  Additionally:
    - Tracks flip history to detect spiking.
    - If flips >= SPIKE_FLAP_THRESHOLD inside SPIKE_FLAP_WINDOW, start spiking timer.
    - If spiking lasts SPIKE_ESCALATE_SECONDS, send spiking alerts (special wording).
  """
  # setup persistent flip history storage on function object
  flip_history = getattr(schedule_notify, "_flip_history", {})
  setattr(schedule_notify, "_flip_history", flip_history)
  COOLDOWN = 120  # seconds between notifications for same state
  cooldown_state = getattr(schedule_notify, "_cooldown_state", {})
  setattr(schedule_notify, "_cooldown_state", cooldown_state)

  # Avoid duplicate concurrent threads for same state_key
  if timers.get(state_key) and timers[state_key].is_alive():
    logger.info(
      f"[{state_key}] Notification already scheduled, skipping duplicate.")
    return

  # Update flip history for spike detection immediately
  now = time.time()
  entry = flip_history.setdefault(state_key, {"flips": [], "spike_start": None, "spike_notified": False})
  # Append this flip timestamp
  entry["flips"].append(now)
  # prune flips older than SPIKE_FLAP_WINDOW
  cutoff = now - SPIKE_FLAP_WINDOW
  entry["flips"] = [t for t in entry["flips"] if t >= cutoff]

  # Determine if flipping indicates spiking
  if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD:
    if entry["spike_start"] is None:
      entry["spike_start"] = entry["flips"][0]  # earliest flip within window
      logger.info(f"[{state_key}] Spiking detected, spike_start set to {entry['spike_start']}")
  else:
    # not enough flips to consider spiking; keep spike_start as-is (do not clear immediately)
    pass

  def task():
    start = time.time()
    stable_start = start
    flap_count = 0
    logger.info(
      f"[{state_key}] Waiting {DELAY}s stability window for {new_state}")

    # Wait for stable state window (DELAY) but keep monitoring flips for spiking
    while time.time() - start < DELAY:
      current = last_state.get(state_key)
      if current != new_state:
        flap_count += 1
        stable_start = time.time()
        # also update flip history (in case flips occur while waiting)
        now_inner = time.time()
        entry["flips"].append(now_inner)
        cutoff_inner = now_inner - SPIKE_FLAP_WINDOW
        entry["flips"] = [t for t in entry["flips"] if t >= cutoff_inner]
        if len(entry["flips"]) >= SPIKE_FLAP_THRESHOLD and entry["spike_start"] is None:
          entry["spike_start"] = entry["flips"][0]
          logger.info(f"[{state_key}] Spiking detected (during wait), spike_start set to {entry['spike_start']}")
        logger.info(
          f"[{state_key}] Flap detected ({current} != {new_state}), resetting timer")
      if time.time() - stable_start >= 60:  # stable for at least 60s
        break
      time.sleep(5)

    # Confirm final stable state
    final_state = last_state.get(state_key)
    if final_state != new_state:
      logger.info(
        f"[{state_key}] State changed again before sending, cancelled")
      timers.pop(state_key, None)
      return

    # If currently spiking (spike_start exists and not yet escalated)
    spike_start = entry.get("spike_start")
    spike_notified = entry.get("spike_notified", False)
    now_send = time.time()

    # If spiking and has lasted SPIKE_ESCALATE_SECONDS, send spiking alert (special messages)
    if spike_start and (now_send - spike_start >= SPIKE_ESCALATE_SECONDS) and not spike_notified:
      # Build a template key that includes SPIKE token and metric if possible to allow _compose_message fallback.
      parts = _parse_template_key(template_name)
      metric = _get_metric(parts) or ("PRIVATE" if "PRIVATE" in (connection_name or "").upper() else ("VENDO" if "VENDO" in (connection_name or "").upper() else None))
      spike_template_key = None
      if metric:
        # include metric so notify_clients can detect it
        spike_template_key = f"{metric}-SPIKE-{group_name}-DOWN".upper()
      else:
        spike_template_key = f"{connection_name}-{group_name}-SPIKE".upper()

      logger.info(f"[{state_key}] Spiking persisted >= {SPIKE_ESCALATE_SECONDS}s → sending SPIKE alert ({spike_template_key})")
      db = SessionLocal()
      try:
        notify_clients(db, spike_template_key, connection_name, group_name)
        # mark spike notified to avoid repeating
        entry["spike_notified"] = True
      finally:
        db.close()

      # Do not proceed with normal same-state notification after spike alert here
      timers.pop(state_key, None)
      return

    # Debounce repeated notifications for same stable state
    prev_notified = notified_state.get(state_key)
    if prev_notified == new_state:
      logger.info(f"[{state_key}] {new_state} already notified, skipping")
      timers.pop(state_key, None)
      return

    # Cooldown check
    last_sent_time = cooldown_state.get(state_key, 0)
    if time.time() - last_sent_time < COOLDOWN:
      logger.info(
        f"[{state_key}] Skipping duplicate within cooldown window ({COOLDOWN}s)")
      timers.pop(state_key, None)
      return

    # Normal send (not spiking)
    logger.info(
      f"[{state_key}] Stable {new_state} after {flap_count} flaps → sending {template_name}")
    db = SessionLocal()
    try:
      notify_clients(db, template_name, connection_name, group_name)
      notified_state[state_key] = new_state
      cooldown_state[state_key] = time.time()
      # If stable and spiking had been flagged earlier, clear spike tracking
      if entry.get("spike_start"):
        logger.info(f"[{state_key}] Clearing spike history (stabilized).")
        entry["flips"] = []
        entry["spike_start"] = None
        entry["spike_notified"] = False
    finally:
      db.close()

    # Cleanup timer record
    timers.pop(state_key, None)

  # Create and start single notify thread
  t = threading.Thread(target=task, daemon=True)
  timers[state_key] = t
  t.start()


# ============================================================
# WebSocket helper
# ============================================================
def broadcast_state_change(ws_manager, client: models.Client,
                           connection_name: str, new_state: str):
    """Broadcast state changes to frontend via WebSocket manager."""
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
def process_rule(db: Session, client: models.Client, connection_name: str,
    last_state_value: str, group_name: str, ws_manager=None):
      """
      Handles state change detection, DB update, notifications, and broadcasting.
      Fix: Template name now includes group suffix (e.g., ISP1-CONNECTION-G1-UP)
      """
      key = f"{connection_name}_{group_name}"

      if client:
        if client.state != last_state_value:
          logger.info(
            f"🔄 {client.name} ({connection_name}) {client.state} → {last_state_value}")

          # Broadcast to frontend clients (WebSocket)
          broadcast_state_change(ws_manager, client, connection_name,
                                 last_state_value)

          # ✅ Include group name in template_name for distinct per-site templates
          template_name = f"{connection_name}-{group_name}-{last_state_value}".replace(
            "_", "-").upper()

          # Schedule delayed notification (debounced & spike aware)
          schedule_notify(key, template_name, connection_name, group_name,
                          last_state_value)

          # Update DB client state
          client.state = last_state_value
          db.add(client)
      else:
        # For unknown connections not mapped in DB
        broadcast_state_change(
          ws_manager,
          models.Client(id=0, messenger_id=None, name="Unknown"),
          connection_name,
          last_state_value,
        )

      # Track the latest observed state
      last_state[key] = last_state_value

# ============================================================
# Polling logic
# ============================================================
def poll_netwatch(
    host: str,
    username: str,
    password: str,
    interval: int = 30,
    ws_manager=None,
    group_name: str = None
):
  """Polls MikroTik Netwatch rules every `interval` seconds and updates DB."""
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
        connection_name = connection_name.replace("_", "-") if connection_name else connection_name
        current_state = (rule.get("status") or "unknown").upper()
        seen_connections.append(connection_name)

        # ✅ Skip transient UNKNOWNs — don't overwrite known UP/DOWN
        key = f"{connection_name}_{group_name}"
        prev_state = last_state.get(key)
        if current_state == "UNKNOWN":
          logger.debug(f"[{key}] Ignoring transient UNKNOWN (keeping {prev_state})")
          continue

        # ✅ Debounce confirmation — avoid flickers
        if prev_state and prev_state != current_state:
          time.sleep(2)
          confirm = (rule.get("status") or current_state).upper()
          if confirm != current_state:
            logger.debug(f"[{key}] Ignored flicker {current_state} → {confirm}")
            continue

        # ✅ Proceed as usual
        client = db.query(models.Client).filter(
          or_(
            models.Client.connection_name == connection_name,
            models.Client.connection_name.ilike(f"{connection_name}%"),
            models.Client.connection_name.ilike(f"%{connection_name}%"),
          )
        ).first()

        effective_group = getattr(client, "group_name", None) or group_name or "default"

        process_rule(db, client, connection_name, current_state, effective_group, ws_manager)
        db.commit()

      # ============================================================
      # ✅ Mark unmatched clients as UNKNOWN (unchanged)
      # ============================================================
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
            logger.info(f"🔄 {client.connection_name} → UNKNOWN (not matched in Netwatch)")
            process_rule(db, client, client.connection_name, "UNKNOWN", group_name, ws_manager)
      db.commit()

      # ============================================================
      # 🧹 Cleanup stale states (unchanged)
      # ============================================================
      active_keys = {f"{c.connection_name}_{group_name}" for c in all_clients}
      stale_keys = [key for key in list(last_state.keys()) if key not in active_keys]
      if stale_keys:
        for key in stale_keys:
          timers.pop(key, None)
          notified_state.pop(key, None)
          last_state.pop(key, None)
        logger.info(f"🧹 Cleaned up {len(stale_keys)} stale state entr{'y' if len(stale_keys)==1 else 'ies'}.")

    except Exception as e:
      db.rollback()
      logger.error(f"❌ Error updating client states for {host}: {e}")
    finally:
      db.close()

    time.sleep(interval)

def initialize_state_cache():
  """Load last known client states from DB into memory on startup."""
  db = SessionLocal()
  try:
    clients = db.query(models.Client).all()
    for c in clients:
      group = c.group_name or "default"
      key = f"{c.connection_name}_{group}"
      last_state[key] = c.state or "UNKNOWN"
      notified_state[key] = c.state or "UNKNOWN"
    logger.info(f"🧠 Initialized state cache for {len(clients)} clients.")
  except Exception as e:
    logger.error(f"❌ Failed to initialize state cache: {e}")
  finally:
    db.close()

# ============================================================
# Start polling threads per router group
# ============================================================
def start_polling(username: str, password: str, interval: int = 30,
    ws_manager=None, router_map=None):
  """Start Netwatch polling for each MikroTik router by group."""
  routers = router_map or ROUTER_MAP

  # 🧠 Initialize in-memory state cache
  initialize_state_cache()

  for group_name, host in routers.items():
    thread = threading.Thread(
      target=poll_netwatch,
      args=(host, username, password, interval, ws_manager, group_name),
      daemon=True,
    )
    thread.start()
    logger.info(
      f"✅ Started Netwatch polling for group '{group_name}' at {host}")
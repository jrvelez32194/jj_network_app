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
        base = f"VENDO {cn} is now up and running smoothly."
      else:
        base = f"VENDO {cn} is currently down. Please check cable and indicator light."
    elif metric == "PRIVATE":
      if client_is_admin:
        cn = client_conn_name or "PRIVATE"
        if event == "UP":
          base = f"{cn} is now up and running smoothly."
        else:
          base = f"{cn} is currently down. Please check the cable and plug."
      else:
        if event == "UP":
          base = "Your connection is now up and running smoothly."
        else:
          base = "Your connection is currently down. Please check the cable and plug."
    else:
      # generic fallback
      if event == "UP":
        base = "✅ Service is back online. Service restored."
      else:
        base = "⚠️ Service is currently down. Please wait for restoration."

  # SPIKE messages
  else:
    if metric in ("CONNECTION", "PING") and service_label:
      if event == "UP":
        base = f"✅ {service_label} is now stable and running smoothly again."
      else:
        base = f"⚠️ {service_label} is slow and unstable or experiencing latency."
    elif metric == "VENDO":
      cn = client_conn_name or "VENDO"
      if event == "UP":
        base = f"VENDO {cn} is now stable."
      else:
        base = f"VENDO {cn} is currently unstable. Please check cable and indicator light."
    elif metric == "PRIVATE":
      if client_is_admin:
        cn = client_conn_name or "PRIVATE"
        if event == "UP":
          base = f"{cn} is now stable."
        else:
          base = f"{cn} is currently unstable. Please check the cable and plug."
      else:
        if event == "UP":
          base = "Your connection is now stable."
        else:
          base = "Your connection is currently unstable. Please check the cable and plug."
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
                   group_name: str = None):
    """
    Unified notify function that:
      - parses template_name to detect NORMAL vs SPIKE and VENDO / PRIVATE / ISP
      - auto-creates Template DB entries for VENDO/PRIVATE when missing
      - routes messages:
          * ISP: send non-admin wording to all non-admin clients in the group_name
                 send admin wording (with location suffix) only to admin clients in the group_name
          * VENDO/PRIVATE: only send to clients mapped to VENDO/PRIVATE (client.connection_name must contain token or match)
                 admins may also receive based on admin detection (same as above)
    """
    if not template_name:
        logger.warning("notify_clients() called without template_name")
        return

    # Normalize template key
    template_key = template_name.replace("_", "-").upper()
    parts = _parse_template_key(template_key)
    metric = _get_metric(parts)
    is_spike = _is_spike(parts)

    # Ensure template row exists for VENDO/PRIVATE (auto-create) OR for any template so logs have template_id
    template = db.query(models.Template).filter(models.Template.title == template_key).first()
    if not template:
        # create default content using non-admin composition (so DB has some meaningful content)
        content_default = _compose_message(template_key, connection_name or "", False)
        template = models.Template(title=template_key, content=content_default)
        db.add(template)
        db.commit()
        db.refresh(template)
        logger.info(f"Template '{template_key}' created with default content.")

    # ---------------------
    # ISP handling
    # ---------------------
    if metric in ("CONNECTION", "PING") or any(p.startswith("ISP") for p in parts):
        # For ISP-type events, per your spec:
        # - send to all non-admin clients (within the same group_name) using non-admin wording
        # - send to admin clients (within the same group_name) using admin wording (with suffix)
        from sqlalchemy import and_

        # Build base query limited to group_name if provided
        base_query = db.query(models.Client)
        if group_name:
            base_query = base_query.filter(models.Client.group_name == group_name)

        # Non-admin clients: connection_name DOES NOT contain 'ADMIN'
        non_admin_clients = base_query.filter(~models.Client.connection_name.ilike("%ADMIN%")).all()

        for client in non_admin_clients:
            client_conn = client.connection_name or ""
            message_text = _compose_message(template_key, client_conn, False)
            try:
                resp = send_message(client.messenger_id, message_text)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            log = models.MessageLog(client_id=client.id, template_id=template.id, status=status)
            db.add(log)
            db.commit()
            logger.info(f"📩 Notified NON-ADMIN {client.name} ({client.connection_name}) with '{template_key}'")

        # Admin clients: connection_name contains 'ADMIN' (only they receive admin-suffixed text)
        admin_clients = base_query.filter(models.Client.connection_name.ilike("%ADMIN%")).all()
        for client in admin_clients:
            client_conn = client.connection_name or ""
            message_text = _compose_message(template_key, client_conn, True)
            try:
                resp = send_message(client.messenger_id, message_text)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            log = models.MessageLog(client_id=client.id, template_id=template.id, status=status)
            db.add(log)
            db.commit()
            logger.info(f"📩 Notified ADMIN {client.name} ({client.connection_name}) with '{template_key}'")

        return

    # ---------------------
    # VENDO / PRIVATE handling
    # ---------------------
    # For VENDO and PRIVATE we only send to clients mapped in DB via connection_name containing token or matching
    token = None
    if metric == "VENDO":
        token = "VENDO"
    elif metric == "PRIVATE":
        token = "PRIVATE"

    if token:
        # If a specific connection_name is provided in the Netwatch rule, prefer that for matching.
        # Otherwise, match any client with connection_name containing VENDO / PRIVATE.
        from sqlalchemy import or_

        base_query = db.query(models.Client)
        if group_name:
            base_query = base_query.filter(models.Client.group_name == group_name)

        if connection_name:
            # match clients where client.connection_name equals or contains the given connection_name
            candidates = base_query.filter(
                or_(
                    models.Client.connection_name == connection_name,
                    models.Client.connection_name.ilike(f"{connection_name}%"),
                    models.Client.connection_name.ilike(f"%{connection_name}%"),
                )
            ).all()
        else:
            # fallback: any client whose connection_name contains the token (VENDO / PRIVATE)
            candidates = base_query.filter(models.Client.connection_name.ilike(f"%{token}%")).all()

        if not candidates:
            logger.info(f"No mapped clients found for token={token} connection_name={connection_name}")
            return

        # Send messages to mapped clients
        for client in candidates:
            client_conn = client.connection_name or ""
            client_is_admin = "ADMIN" in client_conn.upper()
            message_text = _compose_message(template_key, client_conn, client_is_admin)
            try:
                resp = send_message(client.messenger_id, message_text)
                status = resp.get("message_id", "failed")
            except Exception:
                status = "failed"
            log = models.MessageLog(client_id=client.id, template_id=template.id, status=status)
            db.add(log)
            db.commit()
            logger.info(f"📩 Notified {'ADMIN' if client_is_admin else 'NON-ADMIN'} {client.name} ({client.connection_name}) with '{template_key}'")

        return

    # ---------------------
    # Fallback: generic template send to matching clients (preserve old behavior)
    # ---------------------
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

    clients = query.all()
    for client in clients:
        client_conn = client.connection_name or ""
        client_is_admin = "ADMIN" in client_conn.upper()
        message_text = _compose_message(template_key, client_conn, client_is_admin)
        try:
            resp = send_message(client.messenger_id, message_text)
            status = resp.get("message_id", "failed")
        except Exception:
            status = "failed"
        log = models.MessageLog(client_id=client.id, template_id=template.id, status=status)
        db.add(log)
        db.commit()
        logger.info(f"📩 Notified {client.name} ({client.connection_name}) with '{template_key}'")


def schedule_notify(state_key: str, template_name: str, connection_name: str,
    group_name: str, new_state: str):
  """Wait for stability (≤DELAYs) but tolerate brief flaps; send once stable."""

  def task():
    start = time.time()
    stable_start = start
    logger.info(
      f"[{state_key}] Waiting {DELAY}s stability window for {new_state}")

    while time.time() - start < DELAY:
      current = last_state.get(state_key)
      if current != new_state:
        # reset stability window if flapped
        stable_start = time.time()
        logger.info(
          f"[{state_key}] Flap detected ({current} != {new_state}), resetting timer")
      # exit early if stable long enough (≥60 s continuous)
      if time.time() - stable_start >= 60:
        break
      time.sleep(10)

    # confirm final state still matches before sending
    if last_state.get(state_key) == new_state:
      prev_notified = notified_state.get(state_key)
      if prev_notified != new_state:
        logger.info(
          f"[{state_key}] Stable {new_state} → sending {template_name}")
        db = SessionLocal()
        try:
          notify_clients(db, template_name, connection_name, group_name)
          notified_state[state_key] = new_state
        finally:
          db.close()
      else:
        logger.info(f"[{state_key}] {new_state} already notified, skipping")
    else:
      logger.info(
        f"[{state_key}] State changed again before sending, cancelled")

  if timers.get(state_key) and timers[state_key].is_alive():
    logger.info(f"[{state_key}] Cancelling old timer")
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

          # Schedule delayed notification (debounced)
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
      # Track all Netwatch connection names seen in this cycle
      seen_connections = []

      for rule in rules:
        connection_name = rule.get("comment") or rule.get("host")
        connection_name = connection_name.replace("_",
                                                  "-") if connection_name else connection_name
        last_state_value = (rule.get("status") or "unknown").upper()
        seen_connections.append(connection_name)

        # ✅ Try to find matching client (exact or fuzzy)
        client = db.query(models.Client).filter(
          or_(
            models.Client.connection_name == connection_name,
            models.Client.connection_name.ilike(f"{connection_name}%"),
            models.Client.connection_name.ilike(f"%{connection_name}%"),
          )
        ).first()

        effective_group = getattr(client, "group_name",
                                  None) or group_name or "default"

        process_rule(
          db,
          client,
          connection_name,
          last_state_value,
          effective_group,
          ws_manager,
        )
        db.commit()

      # ============================================================
      # ✅ Mark unmatched clients as UNKNOWN
      # ============================================================
      all_clients = db.query(models.Client).filter(
        models.Client.group_name == group_name
      ).all()

      def is_seen(client_name: str | None, seen_list: list[str | None]) -> bool:
        """Check if a DB client connection name was actually seen in MikroTik Netwatch."""
        if not client_name:
          return False
        cname = client_name.lower()
        for s in seen_list:
          if not s:
            continue
          s_lower = s.lower()
          # ✅ Only treat as seen if Netwatch comment exactly matches
          #    or starts with the client name (not the reverse).
          if s_lower == cname or s_lower.startswith(cname):
            return True
        return False

      for client in all_clients:
        if not is_seen(client.connection_name, seen_connections):
          if client.state != "UNKNOWN":
            logger.info(
              f"🔄 {client.connection_name} → UNKNOWN (not matched in Netwatch)")
            process_rule(db, client, client.connection_name, "UNKNOWN",
                         group_name, ws_manager)
      db.commit()

      # ============================================================
      # 🧹 Cleanup stale connection entries (renamed or deleted)
      # ============================================================
      active_keys = {f"{c.connection_name}_{group_name}" for c in all_clients}
      stale_keys = [key for key in list(last_state.keys()) if
                    key not in active_keys]
      if stale_keys:
        for key in stale_keys:
          timers.pop(key, None)
          notified_state.pop(key, None)
          last_state.pop(key, None)
        logger.info(
          f"🧹 Cleaned up {len(stale_keys)} stale state entr{'y' if len(stale_keys) == 1 else 'ies'}.")

    except Exception as e:
      db.rollback()
      logger.error(f"❌ Error updating client states for {host}: {e}")
    finally:
      db.close()

    time.sleep(interval)


# ============================================================
# Start polling threads per router group
# ============================================================
def start_polling(username: str, password: str, interval: int = 30,
    ws_manager=None, router_map=None):
  """Start Netwatch polling for each MikroTik router by group."""
  routers = router_map or ROUTER_MAP
  for group_name, host in routers.items():
    thread = threading.Thread(
      target=poll_netwatch,
      args=(host, username, password, interval, ws_manager, group_name),
      daemon=True,
    )
    thread.start()
    logger.info(
      f"✅ Started Netwatch polling for group '{group_name}' at {host}")

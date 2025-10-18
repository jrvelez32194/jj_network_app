import os
import time
import json
import threading
import logging
from typing import Optional, List
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app import models
from app.models import BillingStatus
from app.utils.messenger import send_message
from app.utils.mikrotik_config import MikroTikClient

# ============================================================
# 🧩 Logger Setup
# ============================================================
logger = logging.getLogger("mikrotik_poll")
logger.setLevel(logging.INFO)

# ============================================================
# 🌐 Router Mapping (Configurable)
# ============================================================
DEFAULT_MAP = {
    "G1": "192.168.4.1",
    "G2": "10.147.18.20",
}

try:
    ROUTER_MAP = json.loads(os.getenv("ROUTER_MAP_JSON", "{}")) or DEFAULT_MAP
    logger.info(f"✅ Loaded router map: {ROUTER_MAP}")
except json.JSONDecodeError:
    ROUTER_MAP = DEFAULT_MAP
    logger.warning("⚠️ Invalid ROUTER_MAP_JSON format, using defaults.")

# ============================================================
# 🗃️ DB Session Helper
# ============================================================
def get_db():
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

# ============================================================
# 🧠 Global State Tracking
# ============================================================
last_state = {}
notified_state = {}
spiking_active = {}

# ============================================================
# ⏱️ Timing Settings
# ============================================================
DELAY = 180
RECOVERY_STABLE_SECONDS = 120
FLAP_WINDOW = 120
FLAP_THRESHOLD = 3
SPIKING_DEBOUNCE_SECONDS = 10  # prevents duplicate SPIKING notifications

# ============================================================
# 🔁 Provider -> Admin Location mapping (per your admin examples)
# ============================================================
# G1 Primary/Secondary map to MALUNGON; G2 map to SURALLAH (per your spec)
PROVIDER_ADMIN_LOCATIONS = {
    ("ISP1", "G1"): "MALUNGON",
    ("ISP2", "G1"): "MALUNGON",
    ("ISP", "G2"): "SURALLAH",  # matches 'ISP-CONNECTION-G2' mapping in your spec
}

# ============================================================
# 🔍 Template Finder (searches for the most specific match)
# ============================================================
def find_template(db: Session, connection_name: Optional[str], group_name: Optional[str], state_key: str):
    """
    Looks up Template rows in this order:
      1. connection_name-group_name-state_key
      2. connection_name-group_name
      3. group_name-state_key
      4. connection_name-state_key
      5. state_key
    Returns Template instance or None.
    """
    s = (state_key or "").upper()
    candidates: List[str] = []

    if connection_name and group_name:
        candidates.append(f"{connection_name.upper()}-{group_name.upper()}-{s}")
    if connection_name and group_name:
        candidates.append(f"{connection_name.upper()}-{group_name.upper()}")
    if group_name:
        candidates.append(f"{group_name.upper()}-{s}")
    if connection_name:
        candidates.append(f"{connection_name.upper()}-{s}")
    candidates.append(s)

    for title in filter(None, candidates):
        tpl = db.query(models.Template).filter(models.Template.title.ilike(title)).first()
        if tpl:
            return tpl
    return None

# ============================================================
# 🧾 Provider label resolver (tries DB, falls back to heuristics)
# ============================================================
def resolve_provider_label(db: Session, connection_name: Optional[str], group_name: Optional[str]) -> str:
    """
    Try to fetch a friendly label from a hypothetical ProviderAlias model.
    If not present, fallback to heuristics:
      - G1 + ISP1-* => Primary Service Provider / Primary Internet
      - G1 + ISP2-* => Secondary Service Provider / Secondary Internet
      - G2 => PLDT Provider / PLDT
    Returns a short friendly label (e.g. 'Primary Service Provider').
    """
    name = (connection_name or "").upper()
    grp = (group_name or "").upper()

    # Try optional DB model first (if exists) -- graceful failure if not.
    try:
        if hasattr(models, "ProviderAlias"):
            pa = db.query(models.ProviderAlias).filter(models.ProviderAlias.name.ilike(name)).first()
            if pa and getattr(pa, "label", None):
                return pa.label
    except Exception:
        # If no ProviderAlias in models or query fails, ignore and use heuristics
        pass

    if grp == "G1":
        if name.startswith("ISP1-") or name.startswith("ISP1"):
            return "Primary Service Provider"
        if name.startswith("ISP2-") or name.startswith("ISP2"):
            return "Secondary Service Provider"
    if grp == "G2":
        # anything under G2 we map to PLDT per your examples
        return "PLDT Provider"

    # Generic fallback
    if "VENDO" in name:
        return f"VENDO {name}"
    if "PRIVATE" in name:
        return name

    # final fallback
    return name or "ISP Provider"

# ============================================================
# 🧩 Helper: Build Auto Template Content (matches your spec)
# ============================================================
def build_auto_template_content(conn_type: str, name: Optional[str], label: str, state_key: str, group_name: Optional[str]):
    """
    Builds the template content that will be auto-created if no template exists.
    This closely follows the user's message specifications for:
      - ISP (Primary/Secondary/PLDT)
      - VENDO
      - PRIVATE
    Supports normal UP/DOWN and SPIKE-UP / SPIKE-DOWN.
    """
    conn_type = (conn_type or "").lower()
    name_up = (name or "").strip()
    label = label or name_up or "Provider"
    g = (group_name or "").upper()

    # Normalize state and detect SPIKE variants
    # state_key is expected to be e.g. "UP", "DOWN", "SPIKE-UP", "SPIKE-DOWN", or "SPIKING"
    sk = (state_key or "").upper()

    # If we receive raw 'SPIKING', convert to SPIKE-DOWN (detection)
    if sk == "SPIKING":
        sk = "SPIKE-DOWN"

    # VENDO auto-templates
    if "vendo" in conn_type or name_up.upper().startswith("VENDO"):
        # Titles are usually like 'VENDO-UP' or 'VENDO-SPIKE-DOWN'
        if sk in ("UP", "SPIKE-UP"):
            return f"✅ VENDO '{name_up}' is now up and running smoothly."
        if sk in ("DOWN", "SPIKE-DOWN"):
            # different phrasing for spike vs down
            if sk == "SPIKE-DOWN":
                return f"⚠️ VENDO '{name_up}' is currently unstable. Please check indicator light."
            return f"⚠️ VENDO '{name_up}' is currently down. Please check cables and indicator light."

    # PRIVATE auto-templates (non-admin)
    if "private" in conn_type or name_up.upper().startswith("PRIVATE"):
        if sk in ("UP", "SPIKE-UP"):
            return f"✅ Your connection is now up and running smoothly." if (conn_type and "admin" not in conn_type) else f"✅ {name_up} is now up and running smoothly."
        if sk in ("DOWN", "SPIKE-DOWN"):
            if sk == "SPIKE-DOWN":
                # spiking unstable
                return f"⚠️ Your connection is currently unstable. Please the cable and plug." if (conn_type and "admin" not in conn_type) else f"⚠️ {name_up} is currently unstable. Please the cable and plug."
            return f"⚠️ Your connection is currently down. Please the cable and plug." if (conn_type and "admin" not in conn_type) else f"⚠️ {name_up} is currently down. Please the cable and plug."

    # ISP auto-templates (Primary/Secondary/PLDT)
    # We expect templates such as 'ISP1-CONNECTION-G1-UP' etc; build messages per your spec.
    if "isp" in conn_type or name_up.upper().startswith("ISP") or "ISP" in name_up.upper():
        # Determine simple label tokens like 'Primary Service Provider' / 'Secondary Service Provider' / 'PLDT Provider'
        provider_label = label

        # If group indicates G1 and name contains ISP1/ISP2, use Primary/Secondary mapping in phrasing
        # Map specific textual messages to the SK
        if sk == "UP":
            return f"✅ {provider_label} is back online. Service restored."
        if sk == "DOWN":
            return f"⚠️ {provider_label} is currently down. Please wait for restoration."
        if sk == "SPIKE-UP":
            return f"✅ {provider_label} is now stable and running smoothly again."
        if sk == "SPIKE-DOWN":
            return f"⚠️ {provider_label} is slow and unstable or experiencing latency."

    # Generic fallback — create a generic message based on state
    if sk == "UP":
        return f"✅ {label} is back online. Service restored."
    if sk == "DOWN":
        return f"⚠️ {label} is currently down. Please wait for restoration."
    if sk == "SPIKE-UP":
        return f"✅ {label} is now stable and running smoothly again."
    if sk == "SPIKE-DOWN":
        return f"⚠️ {label} is slow and unstable or experiencing latency."

    return None

# ============================================================
# 🧩 Helper: Personalize message per client
# ============================================================
def personalize_message(content: str, conn_type: str, name: Optional[str], group: Optional[str], provider_label: str, client):
    """
    Adjust content based on:
      - whether the client is ADMIN (append MALUNGON / SURALLAH tags per provider)
      - whether it's VENDO/PRIVATE vs ISP
      - small grammar fixes and placeholder substitution
    """
    if not content:
        return None

    msg = content.strip()
    conn_name_up = (name or "").upper()
    grp = (group or "").upper()

    # For ADMIN clients: append location tags where applicable
    is_admin = (client.connection_name or "").upper() == "ADMIN" or getattr(client, "is_admin", False)

    if is_admin:
        # determine a tag per provider mapping
        # try to identify provider key (ISP1, ISP2, ISP)
        provider_key = None
        # map common tokens to provider keys
        if conn_name_up.startswith("ISP1"):
            provider_key = "ISP1"
        elif conn_name_up.startswith("ISP2"):
            provider_key = "ISP2"
        elif "ISP" in conn_name_up:
            provider_key = "ISP"

        admin_tag = None
        if provider_key:
            admin_tag = PROVIDER_ADMIN_LOCATIONS.get((provider_key, grp))
        # If we have a tag, append it like " - MALUNGON"
        if admin_tag:
            # do not duplicate tag
            if not msg.endswith(f" - {admin_tag}"):
                msg = f"{msg} - {admin_tag}"

    # For non-admin and non-ISP (e.g. private/vendo) messages: ensure phrasing addresses "Your connection"
    if not is_admin:
        # If message contains the literal name of the connection (e.g. "VENDO 'VENDO1'"), we might leave it.
        # But for private connections, prefer "Your connection" wording if message is generic.
        if ("VENDO" not in conn_name_up) and ("'"+conn_name_up+"'" not in msg) and ("Your connection" not in msg) and ("VENDO" not in msg):
            # If the message is clearly ISP-targeted (contains provider_label), remove provider-specific phrase for client
            if provider_label and provider_label.upper() in msg.upper():
                # Replace provider_label with empty phrase and prepend "Your connection " if makes sense
                msg = msg.replace(provider_label, "").strip()
                # avoid producing bad grammar; if msg now starts with "is", prefix "Your connection "
                if msg and msg[0].lower() == "i":
                    msg = f"Your connection {msg}"
            # final safe attempt: if it doesn't reference the client's connection explicitly, add "Your connection" for clarity
            if "Your connection" not in msg and conn_type and ("private" in conn_type or "vendo" in conn_type):
                # for vendo/private we want "Your connection ..." for non-admin
                if not msg.startswith("✅ VENDO") and not msg.startswith("⚠️ VENDO"):
                    msg = f"Your connection {msg[0].lower() != 'i' and msg or 'is ' + msg}"

    return msg.strip()

# ============================================================
# 💬 Notification Sender (main)
# ============================================================
def notify_clients(db: Session, connection_name: str = None, group_name: str = None, state: str = None):
    """
    Main notification function:
      - Resolves provider label
      - Finds or auto-creates template based on the given state
      - Chooses recipients:
          - If connection_name is 'VENDO' or 'PRIVATE' (or contains those), only sends to clients mapped to that connection
          - Otherwise send to all clients for that group (plus ADMINs)
      - Personalizes messages and logs sending
    """
    if not state:
        logger.warning("⚠️ notify_clients called without a state. Skipping.")
        return

    raw_state = (state or "").upper()
    conn_name = (connection_name or "").strip()
    conn_type = conn_name.lower()
    grp = (group_name or "").upper() if group_name else None

    # Resolve friendly provider label from DB/heuristics
    provider_label = resolve_provider_label(db, conn_name, grp)

    # Normalize states:
    # Accept states like 'UP', 'DOWN', 'SPIKING', and produce SPIKE variants if needed.
    # If caller provided 'SPIKING', treat it as SPIKE-DOWN (deterioration) by default.
    state_key = raw_state
    if state_key == "SPIKING":
        state_key = "SPIKE-DOWN"

    # Try to find an exact template
    tpl = find_template(db, conn_name, group_name, state_key)

    # If not found, build auto content
    if not tpl:
        content = build_auto_template_content(conn_type, conn_name, provider_label, state_key, group_name)
        if not content:
            logger.info(f"⏩ No content built for auto-template for {conn_name}/{group_name}/{state_key}. Skipping.")
            return
        # Build a title for the template (consistent with your naming convention)
        # Titles for SPIKE- variants will include SPIKE in the title, e.g. ISP1-CONNECTION-G1-SPIKE-UP
        title = f"{(conn_name or '').upper()}-{(group_name or '').upper()}-{state_key}"
        # For VENDO or PRIVATE, prefer short titles like 'VENDO-UP' or 'PRIVATE-DOWN'
        if conn_name.upper().startswith("VENDO"):
            title = f"VENDO-{state_key}"
        if conn_name.upper().startswith("PRIVATE"):
            title = f"PRIVATE-{state_key}"

        tpl = models.Template(title=title, content=content)
        try:
            db.add(tpl)
            db.commit()
            db.refresh(tpl)
            logger.info(f"🧩 Auto-created template '{title}' with content: {content}")
        except Exception as e:
            db.rollback()
            logger.exception(f"❌ Failed to auto-create template '{title}': {e}")
            # continue without creating template (we will still use content)
            tpl = type("T", (), {"id": None, "content": content})()

    # =============================================================
    # 👥 Determine recipients
    # =============================================================
    # Base query: clients in the same group (if group provided)
    client_query = db.query(models.Client)
    filters = []
    if grp:
        filters.append(models.Client.group_name == grp)

    # If it's a VENDO or PRIVATE connection, only send to clients explicitly mapped to that connection_name
    send_to_mapped_only = False
    if conn_name and any(k in conn_type for k in ("vendo", "private")):
        send_to_mapped_only = True
        filters.append(models.Client.connection_name == conn_name)

    # If connection_name is provided and equals "ADMIN" behavior is handled per-client below
    if filters:
        recipients = client_query.filter(*filters).all()
    else:
        # fallback: all clients
        recipients = client_query.all()

    # Always include ADMINs for the group (so they receive ISP notices if applicable)
    admins = []
    try:
        admins = db.query(models.Client).filter(models.Client.connection_name.ilike("ADMIN"), models.Client.group_name == group_name).all()
    except Exception:
        # ignore if no admins or query fails
        admins = []

    # Combine recipients and admins without duplicates
    combined = {c.id: c for c in (recipients + admins)}.values()

    # =============================================================
    # 💬 Send Notifications per-client
    # =============================================================
    for client in combined:
        # Skip cutoffted clients
        if getattr(client, "status", None) == BillingStatus.CUTOFF:
            logger.info(f"⏩ Skipping {client.name} – CUTOFF")
            continue

        # If connection is VENDO/PRIVATE but the client isn't mapped to it, skip for non-admin cases
        if send_to_mapped_only and getattr(client, "connection_name", None) != conn_name:
            # But still allow admins (admins are included separately above)
            continue

        # Choose template content to use
        template_content = tpl.content if hasattr(tpl, "content") else None
        # Personalize
        try:
            final_msg = personalize_message(template_content, conn_type, conn_name, grp, provider_label, client)
        except Exception as e:
            logger.exception(f"❌ Error personalizing message for {client.name}: {e}")
            final_msg = template_content

        if not final_msg:
            logger.warning(f"⚠️ Empty message for {client.name} (skipping)")
            continue

        try:
            resp = send_message(client.messenger_id, final_msg)
            # Log message send to MessageLog (best-effort)
            try:
                db.add(models.MessageLog(
                    client_id=client.id,
                    template_id=getattr(tpl, "id", None),
                    status=resp.get("message_id", "sent") if isinstance(resp, dict) else "sent",
                ))
                db.commit()
            except Exception:
                db.rollback()
                logger.exception("❌ Failed to insert MessageLog (continuing).")
            logger.info(f"📩 Notified {client.name} ({connection_name}/{group_name}) -> {final_msg}")
        except Exception as e:
            logger.error(f"❌ Failed sending to {client.name}: {e}", exc_info=True)

# ============================================================
# ⏳ Debounced Notification
# ============================================================
def schedule_notify(state_key, connection_name, group_name, new_state):
    """
    Delay confirmation notifications to avoid churn. This function retains
    the semantics you had before (DELAY seconds) for UP/DOWN events.
    SPIKING events are handled immediately (and converted to SPIKE-DOWN).
    """
    if new_state == "SPIKING":
        logger.info(f"[{state_key}] Received SPIKING — handled immediately")
        # For legacy compatibility, call notify with SPIKE-DOWN
        with SessionLocal() as db:
            notify_clients(db, connection_name, group_name, "SPIKE-DOWN")
            notified_state[state_key] = "SPIKE-DOWN"
        return

    def task():
        logger.info(f"[{state_key}] Waiting {DELAY}s before confirming {new_state}")
        time.sleep(DELAY)
        if last_state.get(state_key) == new_state:
            if notified_state.get(state_key) != new_state:
                with SessionLocal() as db:
                    notify_clients(db, connection_name, group_name, new_state)
                    notified_state[state_key] = new_state
            else:
                logger.info(f"[{state_key}] {new_state} already notified, skipping")
        else:
            logger.info(f"[{state_key}] State changed before {DELAY}s expired, cancelling")

    threading.Thread(target=task, daemon=True).start()

# ============================================================
# 🧩 Core State Processor (spam-protected + SPIKING improved)
# ============================================================
def process_rule(db, client, connection_name, last_state_value, group_name,
    ws_manager=None):
  """
  Handles state transitions, broadcasts via websocket, and triggers notification
  logic with debouncing and spiking detection. For SPIKING:
    - when SPIKING is detected, notify as SPIKE-DOWN immediately (if not recently sent)
    - when state later recovers to UP while SPIKING was active, send SPIKE-UP after stability wait
  """
  key = f"{connection_name}_{group_name}"
  prev = last_state.get(key)

  # ✅ Recovery from UNKNOWN → UP (forced broadcast + notify)
  if prev in (None, "UNKNOWN") and last_state_value == "UP":
    logger.info(f"✅ Recovery detected: {connection_name} {prev} → UP")
    broadcast_state_change(ws_manager, client, connection_name, "UP")
    schedule_notify(key, connection_name, group_name, "UP")
    client.state = "UP"
    try:
      db.add(client)
      db.commit()
    except Exception:
      db.rollback()
    last_state[key] = "UP"
    return

  # If state didn't change, skip
  if prev == last_state_value:
    return

  # SPIKING detection path
  if last_state_value == "SPIKING":
    last_time = spiking_active.get(key, 0)
    if time.time() - last_time < SPIKING_DEBOUNCE_SECONDS:
      logger.info(
        f"⏩ Ignoring duplicate SPIKING within {SPIKING_DEBOUNCE_SECONDS}s for {key}")
      return

    logger.info(f"🚨 {key} detected SPIKING")
    placeholder = client or type("Placeholder", (),
                                 {"id": 0, "messenger_id": None,
                                  "name": "Unknown"})()
    broadcast_state_change(ws_manager, placeholder, connection_name, "SPIKING")

    # Notify SPIKE-DOWN immediately (if not recently notified)
    if notified_state.get(key) != "SPIKE-DOWN":
      with SessionLocal() as db:
        notify_clients(db, connection_name, group_name, "SPIKE-DOWN")
      notified_state[key] = "SPIKE-DOWN"
      spiking_active[key] = time.time()
    last_state[key] = "SPIKING"
    return

  # Recovery from SPIKING -> UP handling: send SPIKE-UP after stable window
  if prev == "SPIKING" and last_state_value == "UP":
    def recovery_task():
      time.sleep(RECOVERY_STABLE_SECONDS)
      if last_state.get(key) == "UP" and spiking_active.get(key):
        with SessionLocal() as db2:
          notify_clients(db2, connection_name, group_name, "SPIKE-UP")
        logger.info(f"✅ Sent SPIKE-UP recovery for {key}")
        spiking_active.pop(key, None)
        notified_state[key] = "SPIKE-UP"

    threading.Thread(target=recovery_task, daemon=True).start()

  # Broadcast and schedule normal notifications (UP/DOWN)
  if client and getattr(client, "state", None) != last_state_value:
    logger.info(
      f"🔄 {client.name} ({connection_name}/{group_name}) {getattr(client, 'state', None)} → {last_state_value}")
    broadcast_state_change(ws_manager, client, connection_name,
                           last_state_value)
    if last_state_value not in ["SPIKING"]:
      schedule_notify(key, connection_name, group_name, last_state_value)
    client.state = last_state_value
    try:
      db.add(client)
      db.commit()
    except Exception:
      db.rollback()
  else:
    prev_state = last_state.get(key)
    if prev_state != last_state_value:
      placeholder = client or type("Placeholder", (),
                                   {"id": 0, "messenger_id": None,
                                    "name": "Unknown"})()
      broadcast_state_change(ws_manager, placeholder, connection_name,
                             last_state_value)

  last_state[key] = last_state_value


# ============================================================
# 📡 WebSocket Broadcaster (safe fallback)
# ============================================================
def broadcast_state_change(ws_manager, client, connection_name, state_value):
    try:
        if not ws_manager:
            logger.debug(f"🕸️ No ws_manager available — skipping broadcast for {connection_name}")
            return
        # Ensure the payload matches frontend expectation (event + id + client)
        payload = {
            "event": "state_update",
            "id": getattr(client, "id", 0),
            "client": getattr(client, "name", "Unknown"),
            "client_id": getattr(client, "id", 0),
            "connection_name": connection_name,
            "state": state_value,
            "timestamp": time.time(),
        }
        # ws_manager may expect a dict or a JSON string; attempt both safely
        try:
            # Prefer a .broadcast(payload) interface
            if hasattr(ws_manager, "broadcast") and callable(ws_manager.broadcast):
                ws_manager.broadcast(payload)
            else:
                # if it's a simple callable
                ws_manager(payload)
        except Exception:
            # fallback to sending JSON string if broadcast expects text
            try:
                if hasattr(ws_manager, "broadcast") and callable(ws_manager.broadcast):
                    ws_manager.broadcast(json.dumps(payload))
                else:
                    ws_manager(json.dumps(payload))
            except Exception as e:
                raise e

        logger.info(f"📢 Broadcasted {state_value} for {connection_name}")
    except Exception as e:
        logger.warning(f"⚠️ Failed to broadcast state for {connection_name}: {e}")

# ============================================================
# 🔁 Polling Loop
# ============================================================
def poll_netwatch(host, username, password, interval=30, ws_manager=None,
    group_name=None):
  mikrotik = MikroTikClient(host, username, password)
  change_history = {}
  counter = 0

  logger.info(
    f"🚀 poll_netwatch started for {host} [{group_name}] interval={interval}s")

  while True:
    try:
      if not mikrotik.ensure_connection():
        logger.warning(
          f"❌ [{group_name}] Cannot connect to {host}, retrying in {interval}s...")
        time.sleep(interval)
        continue

      rules = mikrotik.get_netwatch() or []

      # ✅ Deduplicate Netwatch rules by comment
      seen, unique_rules = set(), []
      for rule in rules:
        comment = rule.get("comment") or rule.get("host")
        if comment not in seen:
          seen.add(comment)
          unique_rules.append(rule)
      rules = unique_rules

      with SessionLocal() as db:
        try:
          # =====================================================
          # 🧩 Process each rule normally
          # =====================================================
          matched_clients = set()

          for rule in rules:
            connection_name = (
                  rule.get("comment") or rule.get("host") or "").strip()
            state_val = (rule.get("status") or "UNKNOWN").upper()
            # Log raw rule for easier debugging when matches fail
            logger.debug(f"🔧 Netwatch rule raw: {rule}")

            key = f"{connection_name}_{group_name}"
            now = time.time()

            # Maintain change history for spike detection
            history = [(t, s) for (t, s) in change_history.get(key, []) if
                       now - t < FLAP_WINDOW]
            if not history or history[-1][1] != state_val:
              history.append((now, state_val))
            change_history[key] = history

            # 🚨 Detect SPIKING (frequent flaps)
            if len(history) >= FLAP_THRESHOLD and len(
                {s for _, s in history}) > 1:
              state_val = "SPIKING"
              change_history[key] = []
              logger.info(
                f"🚨 Detected SPIKING for {connection_name} ({group_name}) history={history}")

            normalized_rule = connection_name.lower()

            # ------------------------------------------------------------
            # ✅ STRONG MATCHING LOGIC
            # ------------------------------------------------------------
            client = None
            matched_type = None

            # 1️⃣ Exact match
            client = (
              db.query(models.Client)
              .filter(models.Client.connection_name.ilike(connection_name))
              .first()
            )
            if client:
              matched_type = "exact"

            # 2️⃣ Partial match (contains)
            if not client:
              candidates = (
                db.query(models.Client)
                .filter(models.Client.group_name == group_name)
                .all()
              )
              for c in candidates:
                cname = (c.connection_name or "").lower()
                if cname and cname in normalized_rule and normalized_rule != cname:
                  client = c
                  matched_type = "contained"
                  break

            # 3️⃣ Skip unmatched
            if not client:
              logger.debug(
                f"⚠️ [{group_name}] Ignored rule '{connection_name}' — no client match found.")
              continue

            # 4️⃣ Validate group
            if getattr(client, "group_name",
                       None) and group_name and client.group_name != group_name:
              logger.debug(
                f"⚠️ Skipped '{connection_name}' (group mismatch: {client.group_name})")
              continue

            # ✅ Log successful match
            logger.info(
              f"🔍 [{group_name}] Matched '{connection_name}' -> '{client.connection_name}' "
              f"(match={matched_type}, state={state_val})"
            )

            matched_clients.add(client.connection_name.lower())

            # ✅ Process matched rule
            effective_group = getattr(client, "group_name", group_name)
            process_rule(db, client, connection_name, state_val,
                         effective_group, ws_manager)

          # =====================================================
          # 🧩 DEBUG: print summary of match results
          # =====================================================
          logger.info(
            f"🧩 [{group_name}] Netwatch poll cycle: {len(rules)} rules total")
          logger.info(
            f"🧩 [{group_name}] Matched clients this round: {matched_clients}")
          all_clients = [c.connection_name for c in
                         db.query(models.Client).filter(
                           models.Client.group_name == group_name).all()]
          logger.info(f"🧩 [{group_name}] All clients from DB: {all_clients}")

          # =====================================================
          # 🆕 Force UNKNOWN for clients not matched this cycle
          # =====================================================
          try:
            db_clients = db.query(models.Client).filter(
              models.Client.group_name == group_name).all()
            for c in db_clients:
              cname = (c.connection_name or "").strip()
              if not cname:
                continue
              # 🧠 Case-insensitive + whitespace normalized check
              if cname.strip().lower() not in {m.strip().lower() for m in
                                               matched_clients}:
                current_state = getattr(c, "state", None)
                if current_state != "UNKNOWN":
                  logger.info(
                    f"⚠️ [{group_name}] Client '{c.connection_name}' not matched to any Netwatch rule — setting UNKNOWN"
                  )
                  process_rule(db, c, c.connection_name, "UNKNOWN", group_name,
                               ws_manager)
                  broadcast_state_change(ws_manager, c, c.connection_name,
                                         "UNKNOWN")
          except Exception as exc:
            logger.exception(
              f"💥 Error while forcing UNKNOWN for {group_name}: {exc}")

          # =====================================================
          # 🧩 Detect DB clients missing from Netwatch
          # =====================================================
          observed = {
            ((r.get("comment") or r.get("host") or "").strip().lower())
            for r in rules if (r.get("comment") or r.get("host"))
          }
          logger.debug(
            f"🔎 [{group_name}] Observed {len(observed)} netwatch names")

          try:
            db_clients = db.query(models.Client).filter(
              models.Client.group_name == group_name).all()
            for c in db_clients:
              cname = (c.connection_name or "").strip()
              if not cname:
                continue
              ncname = cname.lower()

              matched = False
              if ncname in observed:
                matched = True
              elif any(ncname in obs and obs != ncname for obs in observed):
                matched = True
              elif any(obs in ncname and obs != ncname for obs in observed):
                matched = True

              if not matched:
                current_state = getattr(c, "state", None)
                if current_state != "UNKNOWN":
                  logger.info(
                    f"⚠️ [{group_name}] Client '{c.connection_name}' not observed in Netwatch — setting UNKNOWN"
                  )
                  process_rule(db, c, c.connection_name, "UNKNOWN",
                               getattr(c, "group_name", group_name), ws_manager)
                  broadcast_state_change(ws_manager, c, c.connection_name,
                                         "UNKNOWN")
          except Exception as exc:
            logger.exception(
              f"💥 Error while reconciling DB vs observed for {group_name}: {exc}")

          # Commit all updates
          db.commit()
        except Exception as e:
          db.rollback()
          logger.exception(
            f"💥 DB processing error during poll for {group_name}: {e}")

      # =====================================================
      # 💓 Heartbeat
      # =====================================================
      counter += 1
      if counter % 10 == 0:
        logger.info(f"❤️ [{group_name}] poll_netwatch still active for {host}")

      logger.debug(f"✅ [{group_name}] Polled {len(rules)} rules from {host}")
      time.sleep(interval)

    except Exception as e:
      logger.exception(
        f"💥 Unexpected error in poll_netwatch({group_name}): {e}")
      time.sleep(interval)
# ============================================================
# 🚀 Polling Starter (unchanged except log polish)
# ============================================================
def start_polling(username, password, interval, ws_manager, router_map):
    """Start background threads to poll each MikroTik router by group."""
    for group_name, host in router_map.items():
        try:
            logger.info(f"🛰️ Starting Netwatch polling for group '{group_name}' ({host})")
            thread = threading.Thread(
                target=poll_netwatch,
                args=(host, username, password, interval, ws_manager, group_name),
                daemon=True,
            )
            thread.start()
            logger.info(f"✅ Polling thread started for '{group_name}' (host={host})")
        except Exception as e:
            logger.exception(f"❌ Failed to start polling for {group_name}: {e}")

# Optional: simple test runner when executed directly (useful for local testing)
if __name__ == "__main__":
    import argparse

    parser = argparse.ArgumentParser(description="Start Netwatch polling (local tester)")
    parser.add_argument("--username", required=True)
    parser.add_argument("--password", required=True)
    parser.add_argument("--interval", type=int, default=30)
    args = parser.parse_args()

    # Minimal fake ws_manager for local runs (prints payloads)
    class _LocalWSManager:
        def broadcast(self, payload):
            print("[LOCAL WS BROADCAST]", payload)

    start_polling(args.username, args.password, args.interval, _LocalWSManager(), ROUTER_MAP)
    # keep the main thread alive
    while True:
        time.sleep(60)

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

logger = logging.getLogger("netwatch poll")
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
    "G1": "❗ All Internet Service Providers are down. It may be due to a brownout or device issue. Please wait.",
    "G2": "❗ PLDT Provider is down. It may be due to a brownout or device issue. Please wait.",
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

  if isp_token == "ISP1" and event == "DOWN" and group == "G1":
    base = f"{base} Switching to Secondary Service Provider to maintain stable connectivity."

  elif isp_token == "ISP2" and event == "DOWN" and group == "G1":
    base = f"{base} Primary Service Provider will now carry all the load. Expect slower connectivity."

  elif isp_token == "ISP1" and isp_token == "ISP2" and event == "DOWN" and group == "G1":
    base = "⚠️ All Internet Service Providers are slow and unstable. Please wait for the restoration."

  base = f"{base} - {location_suffix}"

  return base



def notify_clients(db: Session, template_key: str, connection_name: str = None,
    group_name: str | None = None) :


    # check if there's a template exist
    template = db.query(models.Template).filter(
      models.Template.title == template_key).first()
    if not template:

      return





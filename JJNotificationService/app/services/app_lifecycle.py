import os
import json
import logging
import threading
from datetime import datetime
import pytz
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from app.services.netwatch_serviceV2 import start_polling, ROUTER_MAP
from app.websocket_manager import manager
from app.services.billing_service import BillingService
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("app_lifecycle")

# ✅ Load .env (important for Docker/local)
load_dotenv()

# ✅ Define Manila timezone globally
MANILA_TZ = pytz.timezone("Asia/Manila")

# ✅ Load scheduler times from .env
NOTIFICATION_TIME = os.getenv("NOTIFICATION_TIME", "10:30")
ENFORCEMENT_TIME = os.getenv("ENFORCEMENT_TIME", "11:00")

NOTIF_HOUR, NOTIF_MINUTE = map(int, NOTIFICATION_TIME.split(":"))
ENFORCE_HOUR, ENFORCE_MINUTE = map(int, ENFORCEMENT_TIME.split(":"))

# ✅ Global in-memory record for daily events
_last_state = {"notification": {}, "enforcement": {}}
_last_lock = threading.Lock()
STATE_FILE = "lifecycle_state.json"

# ✅ Shared global scheduler (prevents duplicates)
SCHEDULER = BackgroundScheduler(timezone=MANILA_TZ)

# ------------------------------------------------------------------
# 🔹 Safe JSON Loader
# ------------------------------------------------------------------
def _safe_load_json(path):
    """Safely load JSON from a file. Returns {} if file missing, empty, or invalid."""
    if not os.path.exists(path) or os.path.getsize(path) == 0:
        return {}
    try:
        with open(path, "r") as f:
            return json.load(f)
    except json.JSONDecodeError:
        logger.warning(f"⚠️ Invalid or empty JSON in {path}, resetting lifecycle state.")
        return {}
    except Exception as e:
        logger.warning(f"⚠️ Unexpected error loading {path}: {e}")
        return {}

# ------------------------------------------------------------------
# 🔹 Persistent State Helpers
# ------------------------------------------------------------------
def _load_state():
    """Load persisted lifecycle state from disk."""
    global _last_state
    try:
        data = _safe_load_json(STATE_FILE)
        for section in ["notification", "enforcement"]:
            if section in data:
                _last_state[section] = {
                    k: datetime.strptime(v, "%Y-%m-%d").date()
                    for k, v in data[section].items()
                }
        if any(len(v) > 0 for v in _last_state.values()):
            logger.info(f"📂 Loaded lifecycle state for {len(_last_state['notification'])} routers.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to load lifecycle state: {e}")

def _save_state():
    """Save in-memory lifecycle state to disk."""
    try:
        with open(STATE_FILE, "w") as f:
            json.dump(
                {
                    "notification": {k: v.strftime("%Y-%m-%d") for k, v in _last_state["notification"].items()},
                    "enforcement": {k: v.strftime("%Y-%m-%d") for k, v in _last_state["enforcement"].items()},
                },
                f,
            )
        logger.debug("💾 Lifecycle state saved.")
    except Exception as e:
        logger.warning(f"⚠️ Failed to save lifecycle state: {e}")

# ------------------------------------------------------------------
# 🔹 AppLifecycle Class
# ------------------------------------------------------------------
class AppLifecycle:
    """Handles a single MikroTik’s background lifecycle (polling + billing)."""

    def __init__(self, host: str, user: str, password: str, poll_interval: int, group_name: str):
        self.host = host
        self.user = user
        self.password = password
        self.poll_interval = poll_interval
        self.group_name = group_name
        self.scheduler = SCHEDULER  # ✅ shared scheduler

        # ✅ FIX: include group_name in BillingService
        self.billing_service = BillingService(host, user, password, group_name)

        # ✅ runtime guards
        self._notification_running = False
        self._enforcement_running = False

    # ------------------------------------------------------------------
    # 🔹 Initial Poll
    # ------------------------------------------------------------------
    def initial_poll(self):
        """Run MikroTik rule poll once at startup."""
        try:
            logger.info(f"🔄 [{self.group_name}] Running initial MikroTik poll at startup...")
            mt = MikroTikClient(self.host, self.user, self.password)
            rules = mt.get_netwatch()
            logger.info(f"✅ [{self.group_name}] Initial poll finished → Found {len(rules) if rules else 0} rules")
        except Exception as e:
            logger.error(f"❌ [{self.group_name}] Initial MikroTik poll failed: {e}")

    # ------------------------------------------------------------------
    # 🔹 Continuous Polling
    # ------------------------------------------------------------------
    def start_polling(self):
      """Continuously poll MikroTik for connection changes in background."""
      try:
        router_map = {self.group_name: self.host}
        logger.info(
          f"🛰️ [{self.group_name}] start_polling invoked with router_map={router_map}")

        # ✅ Start actual polling threads directly (mikrotik_poll handles threading internally)
        start_polling(
          username=self.user,
          password=self.password,
          interval=self.poll_interval,
          ws_manager=manager,
          router_map=router_map,
        )

        logger.info(
          f"✅ [{self.group_name}] Netwatch polling started via mikrotik_poll.start_polling()")

      except Exception as e:
        logger.error(f"❌ [{self.group_name}] Polling startup error: {e}")

    # ------------------------------------------------------------------
    # 🔹 Scheduler for Billing (with group isolation)
    # ------------------------------------------------------------------
    def start_scheduler(self):
        """Start billing and maintenance schedulers (with persistent catch-up)."""
        _load_state()
        today = datetime.now(MANILA_TZ).date()
        now = datetime.now(MANILA_TZ)

        with _last_lock:
            notif_last = _last_state["notification"].get(self.group_name)
            enforce_last = _last_state["enforcement"].get(self.group_name)

            notif_time = now.replace(hour=NOTIF_HOUR, minute=NOTIF_MINUTE, second=0, microsecond=0)
            enforce_time = now.replace(hour=ENFORCE_HOUR, minute=ENFORCE_MINUTE, second=0, microsecond=0)

            # 🕒 Notification catch-up (safe)
            if not notif_last or notif_last < today:
                elapsed = (now - notif_time).total_seconds()
                if now > notif_time and 3600 < elapsed < 7200:  # within 1h–2h window
                    logger.info(f"⏰ [{self.group_name}] Missed notification — triggering catch-up.")
                    self._run_notification(today)
                else:
                    logger.info(f"🕐 [{self.group_name}] Skipping notification catch-up (too close/too late).")

            # ⚙️ Enforcement catch-up (safe)
            if not enforce_last or enforce_last < today:
                elapsed = (now - enforce_time).total_seconds()
                if now > enforce_time and 3600 < elapsed < 7200:
                    logger.info(f"⏰ [{self.group_name}] Missed enforcement — triggering catch-up.")
                    self._run_enforcement(today)
                else:
                    logger.info(f"🕐 [{self.group_name}] Skipping enforcement catch-up (too close/too late).")

        # 🔄 Regular sync every 10s (per group)
        job_id_sync = f"sync_{self.group_name}"
        if not self.scheduler.get_job(job_id_sync):
            self.scheduler.add_job(
                lambda: self.billing_service.run("sync"),
                "interval",
                seconds=10,
                id=job_id_sync,
            )

        # 🕗 Daily notification (per group)
        job_id_notif = f"notification_{self.group_name}"
        if not self.scheduler.get_job(job_id_notif):
            self.scheduler.add_job(
                lambda: self._run_notification(datetime.now(MANILA_TZ).date()),
                "cron",
                hour=NOTIF_HOUR,
                minute=NOTIF_MINUTE,
                id=job_id_notif,
                misfire_grace_time=3600,
                timezone=MANILA_TZ,
            )

        # 🕘 Daily enforcement (per group)
        job_id_enforce = f"enforce_{self.group_name}"
        if not self.scheduler.get_job(job_id_enforce):
            self.scheduler.add_job(
                lambda: self._run_enforcement(datetime.now(MANILA_TZ).date()),
                "cron",
                hour=ENFORCE_HOUR,
                minute=ENFORCE_MINUTE,
                id=job_id_enforce,
                misfire_grace_time=3600,
                timezone=MANILA_TZ,
            )

        if not self.scheduler.running:
            self.scheduler.start()
            logger.info("✅ Global scheduler started (shared for all groups)")
        else:
            logger.info(f"🔁 Scheduler already running — attached jobs for {self.group_name}")

    # ------------------------------------------------------------------
    # 🔹 Execution Wrappers (group isolated)
    # ------------------------------------------------------------------
    def _run_notification(self, today):
        with _last_lock:
            last_sent = _last_state["notification"].get(self.group_name)
            if last_sent == today:
                logger.info(f"🕐 [{self.group_name}] Notification already sent today — skip.")
                return
            if self._notification_running:
                logger.info(f"🛑 [{self.group_name}] Notification already running — skip duplicate.")
                return

            self._notification_running = True
            try:
                self.billing_service.run("notification")
                _last_state["notification"][self.group_name] = today
                _save_state()
                logger.info(f"📩 [{self.group_name}] Notification executed successfully.")
            except Exception as e:
                logger.error(f"❌ [{self.group_name}] Notification failed: {e}")
            finally:
                self._notification_running = False

    def _run_enforcement(self, today):
        with _last_lock:
            last_sent = _last_state["enforcement"].get(self.group_name)
            if last_sent == today:
                logger.info(f"🕐 [{self.group_name}] Enforcement already done today — skip.")
                return
            if self._enforcement_running:
                logger.info(f"🛑 [{self.group_name}] Enforcement already running — skip duplicate.")
                return

            self._enforcement_running = True
            try:
                self.billing_service.run("enforce")
                _last_state["enforcement"][self.group_name] = today
                _save_state()
                logger.info(f"⚙️ [{self.group_name}] Enforcement executed successfully.")
            except Exception as e:
                logger.error(f"❌ [{self.group_name}] Enforcement failed: {e}")
            finally:
                self._enforcement_running = False

    # ------------------------------------------------------------------
    # 🔹 Lifecycle Start & Stop
    # ------------------------------------------------------------------
    def startup(self):
        logger.info(f"🚀 Starting lifecycle for {self.group_name}")
        self.initial_poll()
        self.start_polling()
        self.start_scheduler()

    def shutdown(self):
        try:
            logger.info(f"🛑 [{self.group_name}] Shutting down scheduler...")
            if self.scheduler.running:
                self.scheduler.shutdown()
        except Exception as e:
            logger.error(f"❌ [{self.group_name}] Error during shutdown: {e}")

# ------------------------------------------------------------------
# 🔸 Load All MikroTik Routers from ROUTER_MAP
# ------------------------------------------------------------------
def load_all_mikrotiks():
    mikrotiks = []
    username = os.getenv("MIKROTIK_USER", "admin")
    password = os.getenv("MIKROTIK_PASS", "")
    poll_interval = int(os.getenv("MIKROTIK_POLL_INTERVAL", 30))
    seen_groups = set()

    for group_name, host in ROUTER_MAP.items():
        if group_name in seen_groups:
            logger.warning(f"⚠️ Skipping duplicate lifecycle for '{group_name}'")
            continue
        seen_groups.add(group_name)

        mikrotiks.append({
            "host": host,
            "user": username,
            "password": password,
            "poll_interval": poll_interval,
            "group_name": group_name,
        })

    logger.info(f"✅ Loaded {len(mikrotiks)} routers from ROUTER_MAP")
    return mikrotiks

# ------------------------------------------------------------------
# 🔸 Start All Lifecycles (Called by main.py)
# ------------------------------------------------------------------
def start_all_lifecycles():
    mikrotiks = load_all_mikrotiks()
    if not mikrotiks:
        logger.warning("⚠️ No MikroTik routers found in ROUTER_MAP.")
        return []

    lifecycles = []
    for cfg in mikrotiks:
        lifecycle = AppLifecycle(**cfg)
        lifecycle.startup()
        lifecycles.append(lifecycle)
        logger.info(f"✅ Started lifecycle for MikroTik group '{cfg['group_name']}'")

    logger.info(f"🌍 Total MikroTik routers active: {len(lifecycles)}")
    return lifecycles

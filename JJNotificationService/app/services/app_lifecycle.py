import os
import logging
import threading
from apscheduler.schedulers.background import BackgroundScheduler
from dotenv import load_dotenv
from app.utils.mikrotik_poll import start_polling, ROUTER_MAP
from app.websocket_manager import manager
from app.services.billing_service import BillingService
from app.utils.mikrotik_config import MikroTikClient

logger = logging.getLogger("app_lifecycle")

# ✅ Load .env (important for Docker/local)
load_dotenv()


class AppLifecycle:
    """Handles a single MikroTik’s background lifecycle (polling + billing)."""

    def __init__(self, host: str, user: str, password: str, poll_interval: int, group_name: str):
        self.host = host
        self.user = user
        self.password = password
        self.poll_interval = poll_interval
        self.group_name = group_name
        self.scheduler = BackgroundScheduler()
        self.billing_service = BillingService(host, user, password)

    # ------------------------------------------------------------------
    # 🔹 Initial Poll
    # ------------------------------------------------------------------
    def initial_poll(self):
        """Run MikroTik rule poll once at startup."""
        try:
            logger.info(f"🔄 [{self.group_name}] Running initial MikroTik poll at startup...")
            mt = MikroTikClient(self.host, self.user, self.password)
            rules = mt.get_netwatch()
            logger.info(
                f"✅ [{self.group_name}] Initial poll finished → Found {len(rules) if rules else 0} rules"
            )
        except Exception as e:
            logger.error(f"❌ [{self.group_name}] Initial MikroTik poll failed: {e}")

    # ------------------------------------------------------------------
    # 🔹 Continuous Polling
    # ------------------------------------------------------------------
    def start_polling(self):
        """Continuously poll MikroTik for connection changes in background."""

        def background_polling():
            try:
                start_polling(
                    username=self.user,
                    password=self.password,
                    interval=self.poll_interval,
                    ws_manager=manager,
                )
            except Exception as e:
                logger.error(f"❌ [{self.group_name}] Polling thread error: {e}")

        thread = threading.Thread(target=background_polling, daemon=True)
        thread.start()
        logger.info(
            f"✅ [{self.group_name}] Continuous MikroTik polling started (every {self.poll_interval}s)"
        )

    # ------------------------------------------------------------------
    # 🔹 Scheduler for Billing
    # ------------------------------------------------------------------
    def start_scheduler(self):
        """Start billing and maintenance schedulers."""
        try:
            self.scheduler.add_job(self.billing_service.run, "interval", seconds=10)
            self.scheduler.start()
            logger.info(f"✅ [{self.group_name}] Scheduler started (billing every 10s)")
        except Exception as e:
            logger.error(f"❌ [{self.group_name}] Scheduler failed to start: {e}")

    # ------------------------------------------------------------------
    # 🔹 Lifecycle Start & Stop
    # ------------------------------------------------------------------
    def startup(self):
        """Start all background services."""
        logger.info(f"🚀 Starting lifecycle for {self.group_name}")
        self.initial_poll()
        self.start_polling()
        self.start_scheduler()

    def shutdown(self):
        """Cleanly shut down scheduler."""
        try:
            logger.info(f"🛑 [{self.group_name}] Shutting down scheduler...")
            self.scheduler.shutdown()
        except Exception as e:
            logger.error(f"❌ [{self.group_name}] Error during shutdown: {e}")


# ------------------------------------------------------------------
# 🔸 Load All MikroTik Routers from ROUTER_MAP
# ------------------------------------------------------------------
def load_all_mikrotiks():
    """Load all MikroTik routers from ROUTER_MAP_JSON."""
    mikrotiks = []
    username = os.getenv("MIKROTIK_USER", "admin")
    password = os.getenv("MIKROTIK_PASS", "")
    poll_interval = int(os.getenv("MIKROTIK_POLL_INTERVAL", 30))

    for group_name, host in ROUTER_MAP.items():
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

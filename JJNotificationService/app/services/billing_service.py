import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.utils.mikrotik_config import MikroTikClient
from app.utils.billing import check_billing

logger = logging.getLogger("billing_service")


class BillingService:
    def __init__(self, host: str, user: str, password: str, group_name: str):
        """
        BillingService handles billing-related operations for a specific MikroTik group.
        Each instance is bound to one router (group_name).
        """
        self.host = host
        self.user = user
        self.password = password
        self.group_name = group_name  # ✅ identify router group this service belongs to

    def run(self, mode: str = "enforce"):
        """
        Execute the billing workflow for this MikroTik group.
        Modes:
          - 'notification': Send billing notices
          - 'enforce': Apply restrictions (cutoff/limit)
          - 'sync': Periodic background synchronization
        """
        valid_modes = {"notification", "enforce", "sync"}
        if mode not in valid_modes:
            logger.error(f"⚠️ Invalid mode '{mode}' — must be one of {valid_modes}")
            return

        db: Session = SessionLocal()
        mikrotik = MikroTikClient(self.host, self.user, self.password)

        try:
            # ✅ Limit to this group only
            check_billing(db, mode=mode, group_name=self.group_name)
            logger.info(f"✅ [{self.group_name}] Billing '{mode}' executed successfully.")

        except Exception as e:
            logger.error(
                f"❌ [{self.group_name}] Billing job failed during '{mode}': {e}",
                exc_info=True
            )

        finally:
            # ✅ Always close DB and MikroTik connections
            db.close()
            try:
                if mikrotik and getattr(mikrotik, "api_pool", None):
                    mikrotik.api_pool.disconnect()
                    logger.debug(f"🔌 [{self.group_name}] MikroTik connection closed.")
            except Exception as e:
                logger.debug(f"⚠️ [{self.group_name}] Error closing MikroTik connection: {e}")

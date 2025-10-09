import logging
from sqlalchemy.orm import Session
from app.database import SessionLocal
from app.utils.mikrotik_config import MikroTikClient
from app.utils.billing import check_billing

logger = logging.getLogger("billing_service")


class BillingService:
    def __init__(self, host: str, user: str, password: str):
        self.host = host
        self.user = user
        self.password = password

    def run(self):
        """
        Run the unified billing cycle:
        - Evaluates each client's due/overdue status
        - Sends notices or applies actions (limit, cutoff, unblock)
        - Broadcasts updates to WebSocket clients
        """
        db: Session = SessionLocal()
        mikrotik = MikroTikClient(self.host, self.user, self.password)

        try:
            check_billing(db)
            logger.info("✅ Billing job executed successfully")
        except Exception as e:
            logger.error(f"❌ Billing job failed: {e}", exc_info=True)
        finally:
            db.close()
            try:
                if mikrotik and mikrotik.api_pool:
                    mikrotik.api_pool.disconnect()
                    logger.debug("🔌 MikroTik connection closed")
            except Exception:
                pass

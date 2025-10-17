import os
import sys
import logging
from fastapi import FastAPI, WebSocket
from fastapi.middleware.cors import CORSMiddleware

from app.routes import mikrotik, clients, templates, messages, message_logs
from app.routes import system_monitor, force_billing, settings
from app.websocket_manager import manager
from app.services.app_lifecycle import start_all_lifecycles, load_all_mikrotiks
from app.services.billing_service import BillingService

# ============================================================
# 📝 Logging Config
# ============================================================
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s - %(message)s",
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger("main")

# ============================================================
# 🚀 FastAPI App
# ============================================================
app = FastAPI(title="MikroTik Billing System")

# ============================================================
# 💓 Health & Readiness Checks
# ============================================================

@app.get("/health", tags=["system"])
def health_check():
    """
    Fast, lightweight endpoint used by Docker to detect container liveness.
    Always returns OK — even during startup.
    """
    return {"status": "ok"}

# This variable will be toggled once all lifecycles have started
is_ready = False

@app.get("/ready", tags=["system"])
def readiness_check():
    """
    Returns OK only when the app has finished initializing lifecycles.
    Useful for orchestrators or dependency containers.
    """
    return {"status": "ready" if is_ready else "initializing"}

# ============================================================
# 🌍 Environment Setup
# ============================================================
ENV = os.getenv("ENV", "dev")

if ENV == "dev":
    vite_api_base_url = os.getenv("VITE_API_BASE_URL", "http://localhost:5173")
    origins = [
        vite_api_base_url,
        "http://localhost",
        "http://localhost:80",
        "http://localhost:3000",
        "http://127.0.0.1",
    ]
else:
    origins = ["*"]

app.add_middleware(
    CORSMiddleware,
    allow_origins=origins,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# ============================================================
# 🚦 Routers
# ============================================================
app.include_router(clients.router, prefix="/clients", tags=["clients"])
app.include_router(templates.router, prefix="/templates", tags=["templates"])
app.include_router(messages.router, prefix="/messages", tags=["messages"])
app.include_router(mikrotik.router, prefix="/api")
app.include_router(message_logs.router, prefix="/message_logs", tags=["message_logs"])
app.include_router(system_monitor.router, tags=["system-monitor"])
app.include_router(force_billing.router, tags=["force-billing"])
app.include_router(settings.router, tags=["settings"])


# ============================================================
# 🔌 WebSocket Connection
# ============================================================
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    await manager.connect(websocket)
    try:
        while True:
            await websocket.receive_text()
    except Exception:
        await manager.disconnect(websocket)

# ============================================================
# ⚡ Manual Billing Trigger (Admin / Testing Only)
# ============================================================
@app.post("/billing/run/{mode}")
def run_billing_now(mode: str):
    routers = load_all_mikrotiks()
    if not routers:
        return {"message": "⚠️ No MikroTik routers configured."}

    results = []
    for cfg in routers:
        billing_service = BillingService(cfg["host"], cfg["user"], cfg["password"])
        try:
            billing_service.run(mode)
            results.append({"host": cfg["host"], "status": "ok"})
        except Exception as e:
            results.append({"host": cfg["host"], "status": f"error: {e}"})

    return {
        "message": f"✅ Manual billing triggered ({mode}) for {len(routers)} router(s).",
        "results": results,
    }

# ============================================================
# 🚀 Lifecycle Management
# ============================================================
lifecycles = []
ENABLE_SCHEDULER = os.getenv("ENABLE_SCHEDULER", "true").lower() == "true"
INSTANCE_ROLE = os.getenv("INSTANCE_ROLE", "main").lower()  # "main" or "replica"


@app.on_event("startup")
def startup_event():
    """Start background polling and billing for all MikroTik routers."""
    global lifecycles, is_ready

    logger.info(f"🚀 FastAPI startup (PID {os.getpid()}) — role: {INSTANCE_ROLE}")

    if not ENABLE_SCHEDULER or INSTANCE_ROLE != "main":
        logger.info("⏸️ Scheduler disabled for this instance.")
        is_ready = True
        return

    try:
        logger.info("🧠 Initializing all MikroTik lifecycles...")
        lifecycles = start_all_lifecycles()
        logger.info(f"✅ {len(lifecycles)} MikroTik lifecycle(s) started successfully.")
    except Exception as e:
        logger.error(f"❌ Failed to start lifecycles: {e}")
    finally:
        # Mark system as ready regardless of lifecycle failures
        is_ready = True
        logger.info("✅ Application marked as ready.")


@app.on_event("shutdown")
def shutdown_event():
    """Stop all background schedulers cleanly."""
    logger.info("🛑 Shutting down — stopping all schedulers...")
    for lifecycle in lifecycles:
        try:
            lifecycle.shutdown()
        except Exception as e:
            logger.warning(f"⚠️ Failed to stop lifecycle cleanly: {e}")
    logger.info("✅ All MikroTik schedulers stopped cleanly.")

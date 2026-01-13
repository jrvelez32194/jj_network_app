import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# ============================================================
# Load environment variables
# ============================================================
app_env = os.getenv("APP_ENV", "local")
env_file = ".env.docker" if app_env == "docker" and os.path.exists(".env.docker") else ".env.local"
load_dotenv(env_file)

# ============================================================
# Database configuration
# ============================================================
DB_USER = os.getenv("DB_USER", "postgres")
DB_PASSWORD = os.getenv("DB_PASSWORD", "postgres")
DB_NAME = os.getenv("DB_NAME", "postgres")
DB_HOST = os.getenv("DB_HOST", "localhost")
DB_PORT = os.getenv("DB_PORT", "5432")

# Build DSN
database_url = f"postgresql://{DB_USER}:{DB_PASSWORD}@{DB_HOST}:{DB_PORT}/{DB_NAME}"

# Force pg8000 driver for sync
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)

print(f"🚀 Running in {app_env} mode → Connecting to {database_url}")

# ============================================================
# SQLAlchemy setup (sync)
# ============================================================
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

def get_db():
    """Yield a sync DB session for FastAPI routes or services."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

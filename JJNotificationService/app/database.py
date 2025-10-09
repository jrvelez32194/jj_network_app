import os
from sqlalchemy import create_engine
from sqlalchemy.orm import sessionmaker, declarative_base
from dotenv import load_dotenv

# -------------------------
# Load environment
# -------------------------
app_env = os.getenv("APP_ENV", "local")

if app_env == "docker" and os.path.exists(".env.docker"):
    load_dotenv(".env.docker")
else:
    load_dotenv(".env.local")

# -------------------------
# Database config
# -------------------------
db_user = os.getenv("DB_USER", "postgres")
db_password = os.getenv("DB_PASSWORD", "postgres")
db_name = os.getenv("DB_NAME", "postgres")
db_host = os.getenv("DB_HOST", "localhost")
db_port = os.getenv("DB_PORT", "5432")

# Build DSN
database_url = f"postgresql://{db_user}:{db_password}@{db_host}:{db_port}/{db_name}"

# ✅ Force pg8000 driver (avoids psycopg2)
if database_url.startswith("postgresql://"):
    database_url = database_url.replace("postgresql://", "postgresql+pg8000://", 1)

print(f"🚀 Running in {app_env} mode → Connecting to {database_url}")

# -------------------------
# SQLAlchemy setup
# -------------------------
engine = create_engine(database_url, pool_pre_ping=True)
SessionLocal = sessionmaker(autocommit=False, autoflush=False, bind=engine)
Base = declarative_base()

# -------------------------
# FastAPI DB dependency
# -------------------------
def get_db():
    """Yield a database session for FastAPI routes."""
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()

from logging.config import fileConfig
from sqlalchemy import create_engine, pool
from alembic import context

import os
import sys
from dotenv import load_dotenv

# 🔹 Load environment variables from .env (must be in project root)
load_dotenv()

# Add app directory to sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), ".."))

from app.database import Base
from app import models  # ✅ Import all models so Alembic sees them

# Alembic Config object
config = context.config

# -------------------------
# 🔹 Database URL handling
# -------------------------
env = os.getenv("ENV", "dev").lower()  # default to dev if not set

if env == "dev":
    db_host = os.getenv("DB_HOST", "localhost")
else:
    db_host = os.getenv("DB_HOST", "jj_db")

DATABASE_URL = (
    f"postgresql+pg8000://{os.getenv('DB_USER')}:{os.getenv('DB_PASSWORD')}"
    f"@{db_host}:{os.getenv('DB_PORT', 5432)}/{os.getenv('DB_NAME')}"
)

if not os.getenv("DB_USER") or not os.getenv("DB_PASSWORD") or not os.getenv("DB_NAME"):
    raise ValueError("❌ Missing one of DB_USER, DB_PASSWORD, DB_NAME in .env")

# 🐞 Debug helper — shows which DB Alembic is connecting to
print(f"🔗 Alembic connecting to {DATABASE_URL}")

# ✅ Push into alembic config
config.set_main_option("sqlalchemy.url", DATABASE_URL)

# Logging config
if config.config_file_name is not None:
    fileConfig(config.config_file_name)

# Target metadata (used for autogenerate)
target_metadata = Base.metadata


def run_migrations_offline():
    """Run migrations in 'offline' mode."""
    context.configure(
        url=DATABASE_URL,
        target_metadata=target_metadata,
        literal_binds=True,
        dialect_opts={"paramstyle": "named"},
    )

    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online():
    """Run migrations in 'online' mode."""
    connectable = create_engine(DATABASE_URL, poolclass=pool.NullPool)

    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)

        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()

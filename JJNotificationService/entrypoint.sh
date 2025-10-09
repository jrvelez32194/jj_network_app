#!/bin/sh
set -e

echo "⏳ Waiting for Postgres at $DB_HOST:$DB_PORT..."

# If pg_isready is available, use it
if command -v pg_isready > /dev/null 2>&1; then
    until pg_isready -h "$DB_HOST" -p "$DB_PORT" -U "$DB_USER"; do
        >&2 echo "Postgres is unavailable - sleeping"
        sleep 2
    done
else
    echo "⚠️ pg_isready not found, falling back to netcat (nc)..."
    until nc -z "$DB_HOST" "$DB_PORT"; do
        >&2 echo "Postgres is unavailable - sleeping"
        sleep 2
    done
fi

echo "✅ Postgres is up - running Alembic migrations..."
alembic upgrade head || {
    echo "❌ Alembic migration failed!"
    exit 1
}

echo "🚀 Starting FastAPI app..."
exec uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload

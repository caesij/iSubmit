#!/bin/sh
set -e

echo "Initializing database..."
python manage.py bootstrap_database

echo "Collecting static files..."
python manage.py collectstatic --noinput

echo "Starting server..."
exec uvicorn config.asgi:application \
    --host 0.0.0.0 \
    --port 8000 \
    --reload \
    --reload-dir /app/backend

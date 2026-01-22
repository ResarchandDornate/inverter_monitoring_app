#!/bin/sh

echo "Running migrations..."
python manage.py migrate --noinput

echo "Collecting static files..."
python manage.py collectstatic --noinput || true

echo "Starting Gunicorn..."
gunicorn inverter_app_backend.wsgi:application \
    --bind 0.0.0.0:8000 \
    --workers 3
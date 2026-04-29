#!/bin/sh
set -e

echo "[entrypoint] Esperando PostgreSQL..."
until nc -z postgres 5432; do
  sleep 1
done

echo "[entrypoint] Esperando Redis..."
until nc -z redis 6379; do
  sleep 1
done

echo "[entrypoint] Migraciones..."
python manage.py migrate --noinput

echo "[entrypoint] Recolectando estáticos..."
python manage.py collectstatic --noinput

echo "[entrypoint] Iniciando Gunicorn..."
exec gunicorn core.wsgi:application --bind 0.0.0.0:8000 --workers 3 --access-logfile - --error-logfile -

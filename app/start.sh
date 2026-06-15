#!/bin/sh
set -e

pip install --quiet --no-cache-dir -r /app/requirements.txt

cd /app
exec gunicorn app:app \
  --bind 0.0.0.0:5000 \
  --workers 2 \
  --threads 2 \
  --timeout 30 \
  --access-logfile - \
  --error-logfile -

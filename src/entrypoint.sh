#!/bin/sh
set -e

cd /app/django/legal_backend

python manage.py migrate --noinput
python manage.py runserver 0.0.0.0:8000

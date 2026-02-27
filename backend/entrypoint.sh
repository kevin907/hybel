#!/bin/bash
set -e

echo "Waiting for PostgreSQL..."
while ! python -c "
import psycopg2, os, urllib.parse
url = os.environ.get('DATABASE_URL', '')
result = urllib.parse.urlparse(url)
psycopg2.connect(
    dbname=result.path[1:],
    user=result.username,
    password=result.password,
    host=result.hostname,
    port=result.port or 5432
)
" 2>/dev/null; do
    sleep 2
done
echo "PostgreSQL is ready"

echo "Running migrations..."
python manage.py migrate --noinput

echo "Ensuring PostgreSQL extensions..."
python manage.py shell -c "
from django.db import connection
with connection.cursor() as cursor:
    cursor.execute('CREATE EXTENSION IF NOT EXISTS pg_trgm;')
    cursor.execute('CREATE EXTENSION IF NOT EXISTS unaccent;')
"

if [ "$DEBUG" = "false" ]; then
    echo "Collecting static files..."
    python manage.py collectstatic --noinput
fi

if [ "$DEBUG" = "true" ]; then
    python manage.py shell -c "
from django.contrib.auth import get_user_model
User = get_user_model()
if not User.objects.filter(is_superuser=True).exists():
    User.objects.create_superuser('admin', 'admin@hybel.no', 'admin')
    print('Created superuser: admin / admin')
"
fi

exec "$@"

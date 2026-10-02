#!/bin/bash
# Запуск Superset: миграции, админ, затем сервер. При первом старте —
# подключение базы analytics, загрузка ДДУС из data/*.xlsx и сборка дашборда.
set -e
DATA_URI="postgresql://bi:bi@db:5432/analytics"

superset db upgrade
superset fab create-admin --username admin --firstname Admin --lastname User \
    --email admin@local --password "${ADMIN_PASSWORD}" || true
superset init
superset set-database-uri -d "Аналитика" -u "$DATA_URI"

/usr/bin/run-server.sh &
SERVER=$!
until curl -sf http://localhost:8088/health >/dev/null; do sleep 2; done

XLSX=$(ls /app/data/*.xlsx 2>/dev/null | head -1 || true)
if [ -n "$XLSX" ]; then
    echo ">> Загружаю ДДУС из $XLSX"
    python /app/ddus/etl_ddus.py "$XLSX" --pg "$DATA_URI"
    if [ ! -f /app/superset_home/.ddus_built ]; then
        python /app/ddus/build_dashboard.py --url http://localhost:8088 \
            --user admin --password "${ADMIN_PASSWORD}" --db-name "Аналитика"
        touch /app/superset_home/.ddus_built
    fi
else
    echo ">> В папке data нет .xlsx — дашборд ДДУС не собран"
fi
echo ">> Superset готов: http://localhost:8088  (логин admin)"
wait $SERVER

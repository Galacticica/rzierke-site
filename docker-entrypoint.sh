#!/usr/bin/env bash
set -euo pipefail

cd /app

DEBUG=${DEBUG:-0}

if [ "$DEBUG" = "1" ]; then
	echo "Development mode: starting vite dev server and Django runserver"

	echo "Starting Vite (npm run dev)..."
	npm run dev &
	NPM_PID=$!

	cleanup() {
		echo "Shutting down..."
		kill -TERM "${NPM_PID}" 2>/dev/null || true
		wait ${NPM_PID} 2>/dev/null || true
	}

	trap 'cleanup; exit' SIGINT SIGTERM

	echo "Running database migrations..."
	python manage.py migrate --noinput
	echo "Starting Django dev server on 0.0.0.0:8000..."
	python manage.py runserver 0.0.0.0:8000 &

	wait ${NPM_PID}
else
	echo "Production mode: running migrations and collectstatic"
	python manage.py migrate --noinput
	python manage.py collectstatic --noinput || true

	PORT=${PORT:-8000}
	echo "Starting gunicorn on 0.0.0.0:${PORT}"
	exec gunicorn conf.wsgi:application \
		--bind 0.0.0.0:${PORT} \
		--workers 2 \
		--log-level info \
		--access-logfile - \
		--error-logfile -
fi
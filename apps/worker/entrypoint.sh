#!/bin/sh
set -e

# Use PORT environment variable or default to 8080
PORT=${PORT:-8080}
# Allow Gunicorn concurrency and timeout to be configured with safer defaults
WEB_CONCURRENCY=${WEB_CONCURRENCY:-2}
GUNICORN_TIMEOUT=${GUNICORN_TIMEOUT:-30}

# Start gunicorn with uvicorn workers
exec gunicorn --bind ":${PORT}" --workers "${WEB_CONCURRENCY}" --worker-class uvicorn.workers.UvicornWorker --timeout "${GUNICORN_TIMEOUT}" worker.app:app

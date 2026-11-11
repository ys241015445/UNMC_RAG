#!/bin/sh
set -eu

echo "[unmc-rag] rendering frontend"

: "${UNMC_RAG_APP_NAME:=UNMC Course Assistant}"
: "${UNMC_RAG_SCHOOL_EMAIL_DOMAIN:=unmc.edu}"
export UNMC_RAG_APP_NAME UNMC_RAG_SCHOOL_EMAIL_DOMAIN

envsubst '${UNMC_RAG_APP_NAME} ${UNMC_RAG_SCHOOL_EMAIL_DOMAIN}' \
  < /var/www/html/index.html.template \
  > /var/www/html/index.html

echo "[unmc-rag] starting uvicorn on 127.0.0.1:8000"
/usr/local/bin/uvicorn app.main:app --host 127.0.0.1 --port 8000 &
UVICORN_PID=$!

echo "[unmc-rag] waiting for uvicorn /health"
i=0
while [ "$i" -lt 45 ]; do
  if ! kill -0 "$UVICORN_PID" 2>/dev/null; then
    echo "[unmc-rag] uvicorn exited before becoming ready" >&2
    wait "$UVICORN_PID" || true
    exit 1
  fi
  if python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=2)" 2>/dev/null; then
    echo "[unmc-rag] uvicorn is ready"
    break
  fi
  i=$((i + 1))
  sleep 1
done

echo "[unmc-rag] starting nginx on :80"
/usr/sbin/nginx -g "daemon off;" &
NGINX_PID=$!

while kill -0 "$UVICORN_PID" 2>/dev/null && kill -0 "$NGINX_PID" 2>/dev/null; do
  sleep 1
done

echo "[unmc-rag] a process exited; shutting down" >&2
kill "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
wait "$UVICORN_PID" "$NGINX_PID" 2>/dev/null || true
exit 1

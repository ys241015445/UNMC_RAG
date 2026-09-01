#!/bin/sh
set -e

: "${UNMC_RAG_APP_NAME:=UNMC Course Assistant}"
: "${UNMC_RAG_SCHOOL_EMAIL_DOMAIN:=unmc.edu}"

export UNMC_RAG_APP_NAME UNMC_RAG_SCHOOL_EMAIL_DOMAIN

envsubst '${UNMC_RAG_APP_NAME} ${UNMC_RAG_SCHOOL_EMAIL_DOMAIN}' \
  < /var/www/html/index.html.template \
  > /var/www/html/index.html

# -n keeps supervisor in the foreground (PID 1). Use the Debian main config so
# conf.d snippets are included; do not pass conf.d/unmc-rag.conf as -c (that
# file is only [program:*] and is not a full supervisord config).
exec /usr/bin/supervisord -n -c /etc/supervisor/supervisord.conf

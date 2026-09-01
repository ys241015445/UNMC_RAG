#!/bin/sh
set -e

: "${UNMC_RAG_APP_NAME:=UNMC Course Assistant}"
: "${UNMC_RAG_SCHOOL_EMAIL_DOMAIN:=unmc.edu}"

export UNMC_RAG_APP_NAME UNMC_RAG_SCHOOL_EMAIL_DOMAIN

envsubst '${UNMC_RAG_APP_NAME} ${UNMC_RAG_SCHOOL_EMAIL_DOMAIN}' \
  < /var/www/html/index.html.template \
  > /var/www/html/index.html

exec /usr/bin/supervisord -c /etc/supervisor/conf.d/unmc-rag.conf

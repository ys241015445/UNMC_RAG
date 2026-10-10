# Coolify GitHub App: one image, one public port.
# nginx :80 (UI + /api /health /ready) → FastAPI 127.0.0.1:8000
# Secrets come from Coolify env. Never COPY .env.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PATH="/usr/local/bin:/usr/local/sbin:/usr/sbin:/usr/bin:/sbin:/bin" \
    UNMC_RAG_CORPUS_PATH=data/scraped/current_students/documents.jsonl,data/scraped/nfp/documents.jsonl

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default /etc/nginx/nginx.conf

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY data/scraped/current_students/documents.jsonl \
     /app/data/scraped/current_students/documents.jsonl
COPY data/scraped/nfp/documents.jsonl \
     /app/data/scraped/nfp/documents.jsonl
COPY frontend/index.html /var/www/html/index.html.template
COPY app/static /var/www/html/static
COPY deploy/nginx.conf /etc/nginx/nginx.conf
COPY deploy/docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh \
    && nginx -t

EXPOSE 80

ENTRYPOINT ["/docker-entrypoint.sh"]

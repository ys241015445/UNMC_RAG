# All-in-one image for Coolify: nginx :80 + FastAPI on 127.0.0.1:8000.
# Secrets (DATABASE_URL, LLM_API_KEY) come from Coolify env — never COPY .env.

FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    UNMC_RAG_CORPUS_PATH=data/scraped/current_students/documents.jsonl

WORKDIR /app

RUN apt-get update \
    && apt-get install -y --no-install-recommends \
        nginx \
        supervisor \
        gettext-base \
    && rm -rf /var/lib/apt/lists/* \
    && rm -f /etc/nginx/sites-enabled/default

COPY pyproject.toml README.md ./
COPY app ./app
RUN pip install --no-cache-dir .

COPY data/scraped/current_students/documents.jsonl \
     /app/data/scraped/current_students/documents.jsonl
COPY frontend/index.html /var/www/html/index.html.template
COPY app/static /var/www/html/static
COPY deploy/nginx.conf /etc/nginx/conf.d/default.conf
COPY deploy/supervisord.conf /etc/supervisor/conf.d/unmc-rag.conf
COPY deploy/docker-entrypoint.sh /docker-entrypoint.sh

RUN chmod +x /docker-entrypoint.sh

EXPOSE 80

HEALTHCHECK --interval=15s --timeout=5s --start-period=25s --retries=5 \
  CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1/health')"

ENTRYPOINT ["/docker-entrypoint.sh"]

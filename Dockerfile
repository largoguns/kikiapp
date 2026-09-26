# ─────────────────────────────────────────────────────────────────────────────
# Kiki App — imagen multi-stage sobre Alpine.
#
# Los assets de frontend (Tailwind compilado y librerías vendorizadas) van
# versionados en el repo, así que la imagen no necesita Node: sólo Python.
# Para regenerarlos: npm install && npm run build
# ─────────────────────────────────────────────────────────────────────────────

FROM python:3.12-alpine AS builder

# libffi/build-base sólo hacen falta si alguna dependencia no trae rueda musl.
RUN apk add --no-cache build-base libffi-dev

COPY requirements.txt /tmp/requirements.txt
RUN python -m venv /opt/venv \
    && /opt/venv/bin/pip install --no-cache-dir --upgrade pip \
    && /opt/venv/bin/pip install --no-cache-dir -r /tmp/requirements.txt


FROM python:3.12-alpine

RUN apk add --no-cache tzdata \
    && adduser -D -u 1000 kiki

COPY --from=builder /opt/venv /opt/venv

WORKDIR /app
COPY app/ ./app/
COPY static/ ./static/
COPY templates/ ./templates/
COPY tools/seed.py ./tools/seed.py

RUN mkdir -p /app/data && chown -R kiki:kiki /app

ENV PATH="/opt/venv/bin:$PATH" \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    DATA_DIR=/app/data \
    PORT=8080 \
    TZ=Europe/Madrid

USER kiki
EXPOSE 8080
VOLUME ["/app/data"]

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import os,urllib.request; urllib.request.urlopen(f\"http://127.0.0.1:{os.environ['PORT']}/api/health\").read()" || exit 1

CMD ["sh", "-c", "exec uvicorn app.main:app --host 0.0.0.0 --port ${PORT}"]

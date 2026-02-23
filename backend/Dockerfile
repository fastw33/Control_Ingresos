FROM python:3.11-slim

ENV DEBIAN_FRONTEND=noninteractive TZ=America/Bogota \
    PYTHONDONTWRITEBYTECODE=1 PYTHONUNBUFFERED=1

# SO deps mínimas + curl para healthcheck
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgomp1 tzdata curl \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

# Toolchain para compilar insightface (g++) y luego se purga
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt /app/requirements.txt
RUN python -m pip install --upgrade pip setuptools wheel \
    && pip install --no-cache-dir -r requirements.txt \
    && apt-get purge -y --auto-remove build-essential \
    && rm -rf /root/.cache/pip

# Resto de la app
COPY . /app

# Usuario no root y carpetas
RUN useradd -m appuser \
    && mkdir -p /home/appuser/.insightface /app/upload \
    && chown -R appuser:appuser /home/appuser /app
USER appuser

ENV INSIGHTFACE_HOME=/home/appuser/.insightface \
    OMP_NUM_THREADS=1 \
    ONNX_NUM_THREADS=1 \
    PORT=3000

# Healthcheck simple
HEALTHCHECK --interval=30s --timeout=3s --start-period=15s --retries=3 \
    CMD curl -fsS "http://127.0.0.1:${PORT:-3000}/health" || exit 1

# Arranque (formato shell como tu guía)
CMD sh -c "gunicorn -k uvicorn.workers.UvicornWorker -w 2 -b 0.0.0.0:${PORT:-3000} --timeout 60 --keep-alive 5 app.main:app"

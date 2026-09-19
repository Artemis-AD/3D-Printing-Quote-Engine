# Machine Shop Suite - 3D Printing Quote Engine
# Aussie 3D fork: fixed dead PrusaSlicer 2.7.0 AppImage URL (404).

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRUSA_SLICER_PATH=/usr/local/bin/prusa-slicer

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    libgtk-3-0 \
    libwebkit2gtk-4.0-37 \
    && rm -rf /var/lib/apt/lists/*

# PrusaSlicer 2.7.4 Linux x64 GTK3 AppImage (upstream Dockerfile 2.7.0 URL 404s)
RUN wget -q "https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.7.4/PrusaSlicer-2.7.4%2Blinux-x64-GTK3-202404050928.AppImage" \
    -O /usr/local/bin/PrusaSlicer.AppImage \
    && chmod +x /usr/local/bin/PrusaSlicer.AppImage \
    && cd /usr/local/bin \
    && ./PrusaSlicer.AppImage --appimage-extract \
    && ln -sf /usr/local/bin/squashfs-root/usr/bin/prusa-slicer /usr/local/bin/prusa-slicer \
    && rm PrusaSlicer.AppImage

WORKDIR /app

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app.py .
COPY config.py .
COPY utils.py .
COPY templates/ ./templates/
COPY static/ ./static/

RUN mkdir -p logs \
    && useradd -m -u 1000 appuser \
    && chown -R appuser:appuser /app

USER appuser

EXPOSE 5000

HEALTHCHECK --interval=30s --timeout=10s --start-period=40s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:5000/api/config', timeout=5)" || exit 1

CMD ["gunicorn", "--bind", "0.0.0.0:5000", "--workers", "2", "--timeout", "300", "--access-logfile", "-", "--error-logfile", "-", "app:app"]

# Machine Shop Suite - 3D Printing Quote Engine
# Aussie 3D fork: fixed dead PrusaSlicer download + slim Debian deps.

FROM python:3.11-slim AS base

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    PIP_NO_CACHE_DIR=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PRUSA_SLICER_PATH=/usr/local/bin/prusa-slicer

# wget/bzip2 for install; OpenGL/GTK/X11 stack so prusa-slicer links headless
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    ca-certificates \
    bzip2 \
    libgl1 \
    libglu1-mesa \
    libegl1 \
    libglib2.0-0 \
    libgtk-3-0 \
    libdbus-1-3 \
    libxcb1 \
    libx11-6 \
    libxi6 \
    libxext6 \
    libxrender1 \
    libsm6 \
    libice6 \
    libgomp1 \
    libpango-1.0-0 \
    libcairo2 \
    libatk1.0-0 \
    libgdk-pixbuf-2.0-0 \
    && rm -rf /var/lib/apt/lists/*

# Official linux-x64 GTK3 tarball (AppImage extract + webkit packages break on slim)
RUN wget -q "https://github.com/prusa3d/PrusaSlicer/releases/download/version_2.7.4/PrusaSlicer-2.7.4%2Blinux-x64-GTK3-202404050928.tar.bz2" \
    -O /tmp/prusaslicer.tar.bz2 \
    && mkdir -p /opt/prusaslicer \
    && tar -xjf /tmp/prusaslicer.tar.bz2 -C /opt/prusaslicer --strip-components=1 \
    && ln -sf /opt/prusaslicer/bin/prusa-slicer /usr/local/bin/prusa-slicer \
    && rm /tmp/prusaslicer.tar.bz2 \
    && test -x /usr/local/bin/prusa-slicer \
    && (ldd /usr/local/bin/prusa-slicer | tee /tmp/ldd.txt) \
    && ! grep -q "not found" /tmp/ldd.txt \
    && rm /tmp/ldd.txt

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

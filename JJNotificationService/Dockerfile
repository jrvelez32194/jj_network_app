# ====================================================
# 🐍 Base Image
# ====================================================
FROM python:3.10-slim

# ----------------------------------------------------
# Set working directory
# ----------------------------------------------------
WORKDIR /app

# ----------------------------------------------------
# 🧩 Install system dependencies
# ----------------------------------------------------
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    netcat-openbsd \
    tzdata && \
    ln -fs /usr/share/zoneinfo/Asia/Manila /etc/localtime && \
    dpkg-reconfigure -f noninteractive tzdata && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# ----------------------------------------------------
# 🕐 Timezone
# ----------------------------------------------------
ENV TZ=Asia/Manila

# ----------------------------------------------------
# ⚙️ Python dependencies
# ----------------------------------------------------
COPY requirements.txt .

# ✅ Upgrade pip safely and with retries/timeouts
RUN pip install --default-timeout=120 --retries=10 --no-cache-dir --upgrade pip==24.2 setuptools wheel && \
    PIP_DEFAULT_TIMEOUT=120 \
    pip install --no-cache-dir -r requirements.txt --timeout 120 --retries 10 --index-url https://pypi.org/simple --progress-bar off

# ----------------------------------------------------
# 📦 Copy app source
# ----------------------------------------------------
COPY . .

# ----------------------------------------------------
# 🧰 Entrypoint
# ----------------------------------------------------
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ----------------------------------------------------
# 🌐 Expose backend port
# ----------------------------------------------------
EXPOSE 8000

# ----------------------------------------------------
# 🚀 Environment Configs for Dev Autoreload
# ----------------------------------------------------
# Exclude .venv and migrations folders from uvicorn autoreload scan
ENV UVICORN_RELOAD_EXCLUDES=".venv,migrations,__pycache__"

# ----------------------------------------------------
# 🚀 Default entrypoint
# ----------------------------------------------------
ENTRYPOINT ["/entrypoint.sh"]

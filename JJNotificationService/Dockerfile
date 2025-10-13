# jjnotificationservice/Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# ----------------------------------------------------
# ✅ Install dependencies (including tzdata for Manila time)
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

# ✅ Set environment timezone variable
ENV TZ=Asia/Manila

# ----------------------------------------------------
# Copy Python dependencies and install
# ----------------------------------------------------
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# ----------------------------------------------------
# Copy application source
# ----------------------------------------------------
COPY . .

# ----------------------------------------------------
# Copy entrypoint script and set permissions
# ----------------------------------------------------
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# ----------------------------------------------------
# Expose backend port
# ----------------------------------------------------
EXPOSE 8000

# ----------------------------------------------------
# Default entrypoint
# ----------------------------------------------------
ENTRYPOINT ["/entrypoint.sh"]

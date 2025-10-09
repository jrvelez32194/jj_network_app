# jjnotificationservice/Dockerfile
FROM python:3.10-slim

# Set working directory
WORKDIR /app

# Install system dependencies for psycopg2 and others
RUN apt-get update && apt-get install -y \
    build-essential \
    libpq-dev \
    curl \
    netcat-openbsd \
 && rm -rf /var/lib/apt/lists/*

# Copy requirements first (for caching)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy app source
COPY . .

# Copy entrypoint script
COPY entrypoint.sh /entrypoint.sh
RUN chmod +x /entrypoint.sh

# Expose backend port
EXPOSE 8000

# Default entrypoint (will run wait-for-db → migrations → start app)
ENTRYPOINT ["/entrypoint.sh"]

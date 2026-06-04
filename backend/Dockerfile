FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 1. Install CPU torch FIRST (to avoid CUDA download chaos)
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# 2. Install rest of dependencies (includes alembic, fastapi, etc.)
RUN pip install --no-cache-dir --timeout 1000 -r requirements.txt

COPY . .
RUN mkdir -p /app/files

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]

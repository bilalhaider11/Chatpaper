FROM python:3.11-slim-bookworm

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    libpq-dev \
    libmagic1 \
    curl \
    libxcb1 \
    libgl1 \
    libglib2.0-0 \
    poppler-utils \
    tesseract-ocr \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# 1. Install CPU torch FIRST (to avoid CUDA download chaos)
RUN pip install --no-cache-dir \
    torch torchvision torchaudio \
    --index-url https://download.pytorch.org/whl/cpu

# 2. Install rest of dependencies (includes alembic, fastapi, etc.)
RUN pip install --no-cache-dir --timeout 1000 -r requirements.txt

# 3. Pre-download spaCy model so unstructured doesn't try to install it at
#    runtime as a non-root user (which fails with PermissionError).
RUN python -m spacy download en_core_web_sm

COPY . .
RUN mkdir -p /app/files

COPY docker-entrypoint.sh /docker-entrypoint.sh
RUN chmod +x /docker-entrypoint.sh \
    && adduser --disabled-password --gecos "" appuser \
    && chown -R appuser:appuser /app /docker-entrypoint.sh
USER appuser

ENV PYTHONUNBUFFERED=1
EXPOSE 8000

ENTRYPOINT ["/docker-entrypoint.sh"]

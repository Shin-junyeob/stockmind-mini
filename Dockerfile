# ── Build Stage ──────────────────────────────────────────────
FROM python:3.10-slim AS builder

WORKDIR /app

RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --upgrade pip \
    && pip install --prefix=/install --no-cache-dir -r requirements.txt


# ── Runtime Stage ─────────────────────────────────────────────
FROM python:3.10-slim AS runtime

WORKDIR /app

# Chrome + ChromeDriver (Selenium용)
RUN apt-get update && apt-get install -y --no-install-recommends \
    chromium \
    chromium-driver \
    && rm -rf /var/lib/apt/lists/*

# builder에서 설치된 패키지 복사
COPY --from=builder /install /usr/local

# 소스 복사
COPY src/ ./src/

ENV PYTHONPATH=/app/src
ENV PYTHONUNBUFFERED=1
ENV CHROME_BIN=/usr/bin/chromium

CMD ["python", "src/main.py"]

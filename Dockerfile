FROM python:3.10-slim

WORKDIR /app

# Install system dependencies required for Chromium
RUN apt-get update && apt-get install -y --no-install-recommends \
    wget gnupg ca-certificates build-essential \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 \
    libxkbcommon0 libgbm1 libasound2 libxshmfence1 \
    libxcomposite1 libxdamage1 libxrandr2 libxfixes3 \
    libpango-1.0-0 libpangocairo-1.0-0 libcairo2 \
    libx11-xcb1 \
    && rm -rf /var/lib/apt/lists/*

COPY . .

RUN pip install --no-cache-dir --upgrade pip setuptools wheel
RUN pip install --no-cache-dir -r requirements.txt

# FIX: Correct Playwright browser install path
ENV PLAYWRIGHT_BROWSERS_PATH=/ms-playwright
RUN mkdir -p /ms-playwright
RUN python -m playwright install chromium

ENV PORT=5000
EXPOSE 5000

CMD ["gunicorn", "-b", "0.0.0.0:5000", "app:app"]

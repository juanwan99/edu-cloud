FROM python:3.11-slim

WORKDIR /app

# System deps: Playwright Chromium for card PDF generation + Chinese fonts
RUN apt-get update && apt-get install -y --no-install-recommends \
    fonts-noto-cjk \
    libnss3 libatk1.0-0 libatk-bridge2.0-0 libcups2 libdrm2 \
    libxkbcommon0 libxcomposite1 libxdamage1 libxrandr2 libgbm1 \
    libpango-1.0-0 libcairo2 libasound2 libxshmfence1 \
    && rm -rf /var/lib/apt/lists/*

COPY pyproject.toml .
RUN pip install --no-cache-dir . && \
    python -m playwright install chromium

COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 9000

CMD ["python", "-m", "uvicorn", "edu_cloud.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9000"]

FROM python:3.11-slim

WORKDIR /app

COPY pyproject.toml .
RUN pip install --no-cache-dir .

COPY src/ src/
COPY alembic.ini .
COPY alembic/ alembic/

EXPOSE 9000

CMD ["python", "-m", "uvicorn", "edu_cloud.api.app:create_app", "--factory", "--host", "0.0.0.0", "--port", "9000"]

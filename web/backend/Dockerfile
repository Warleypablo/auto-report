FROM python:3.12-slim

WORKDIR /app

COPY web/backend/requirements.txt /app/web/backend/requirements.txt
RUN pip install --no-cache-dir -r /app/web/backend/requirements.txt

COPY web/backend /app/web/backend
COPY core /app/core
COPY utils /app/utils
COPY config /app/config

ENV PYTHONPATH=/app:/app/web/backend

WORKDIR /app/web/backend
EXPOSE 8000
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8000"]

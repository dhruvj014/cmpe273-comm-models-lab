
FROM python:3.11-slim

WORKDIR /app

# Context is project root (cmpe273-comm-models-lab)
COPY sync-rest/order_service/requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY common /app/common
COPY sync-rest/order_service/app /app/app

ENV PYTHONPATH=/app

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000"]

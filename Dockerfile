# Dockerfile
FROM python:3.10-slim

WORKDIR /app
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY app /app

EXPOSE 8090
CMD ["python", "orchestrator.py"]
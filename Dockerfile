# Clothing Segments API - Python/FastAPI with PyTorch
FROM python:3.11-slim

# System deps for building Python packages
RUN apt-get update && apt-get install -y --no-install-recommends \
    build-essential \
    && rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app

COPY requirements-full.txt .
RUN pip install --no-cache-dir -r requirements-full.txt

COPY app/ ./app/
COPY src/ ./src/
COPY run.py example_usage.py ./

# App module is app.main:app
EXPOSE 8080
CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8080"]

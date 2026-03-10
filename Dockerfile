FROM python:3.14-slim

WORKDIR /app

# Dépendances système pour matrix-nio (libolm)
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        libolm-dev \
        gcc \
        python3-dev \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

# Le volume montera la BDD + le .env
VOLUME ["/app/data"]

CMD ["python3", "main.py"]

FROM mcr.microsoft.com/playwright/python:v1.49.0-jammy

WORKDIR /app

# Deps de sistema (tzdata para zoneinfo)
ENV DEBIAN_FRONTEND=noninteractive
ENV TZ=America/Mexico_City
RUN ln -fs /usr/share/zoneinfo/America/Mexico_City /etc/localtime && \
    apt-get update && \
    apt-get install -y --no-install-recommends tzdata && \
    dpkg-reconfigure -f noninteractive tzdata && \
    rm -rf /var/lib/apt/lists/*

# Dependencias Python consolidadas (bot Telegram + dashboard web)
RUN pip install --no-cache-dir \
    'python-telegram-bot>=21.0' \
    'httpx>=0.27.0' \
    'openpyxl>=3.1.0' \
    'fastapi>=0.110' \
    'uvicorn[standard]>=0.27' \
    'python-dotenv>=1.0' \
    'tzdata' \
    'requests>=2.31' \
    'playwright>=1.49.0'

ENV PYTHONUNBUFFERED=1
ENV PYTHONPATH=/app

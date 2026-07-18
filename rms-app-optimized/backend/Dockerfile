FROM python:3.11-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app

# Runtime libraries required by WeasyPrint/Pillow plus curl for the container health check.
RUN apt-get update \
    && apt-get install -y --no-install-recommends \
       curl \
       libcairo2 \
       libffi8 \
       libgdk-pixbuf-2.0-0 \
       libpango-1.0-0 \
       libpangoft2-1.0-0 \
       shared-mime-info \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt ./
RUN pip install --upgrade pip && pip install -r requirements.txt

COPY . .

EXPOSE 8000
HEALTHCHECK --interval=20s --timeout=5s --start-period=30s --retries=3 \
  CMD curl -fsS http://localhost:8000/api/v1/health || exit 1

CMD ["uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", "8000", "--proxy-headers"]

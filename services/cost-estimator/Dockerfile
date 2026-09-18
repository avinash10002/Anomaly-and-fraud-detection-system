FROM python:3.12-slim

LABEL maintainer="MPLAD Anomaly Detector Hackathon Team"
LABEL description="Cost Estimator service — prototype demo rates only"

WORKDIR /app

# Install dependencies first (layer-cached)
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy application code and rate catalogue
COPY main.py       .
COPY estimator.py  .
COPY rates/        rates/

EXPOSE 8084

HEALTHCHECK --interval=15s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8084/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8084"]

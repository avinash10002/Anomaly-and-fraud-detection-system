FROM python:3.12-slim

LABEL description="MPLAD Image Engine — visual inspection & degradation timeline"

WORKDIR /app

# Install system libraries needed for OpenCV & Pillow
RUN apt-get update && apt-get install -y --no-install-recommends \
    libgl1 \
    libglib2.0-0 \
    wget \
    curl \
    && rm -rf /var/lib/apt/lists/*

RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

ENV PYTHONUNBUFFERED=1
ENV SERVICE_PORT=8082
ENV DETECTOR_BACKEND=auto

COPY . .

# Ensure static/annotated directory exists
RUN mkdir -p static/annotated

EXPOSE 8082

HEALTHCHECK --interval=20s --timeout=8s --start-period=30s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8082/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8082"]

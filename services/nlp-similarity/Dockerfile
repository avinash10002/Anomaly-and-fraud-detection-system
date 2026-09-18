FROM python:3.12-slim

LABEL description="MPLAD NLP Similarity Service — semantic WORK description similarity"

WORKDIR /app

# Ensure latest pip
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Configure model cache directory
ENV TRANSFORMERS_CACHE=/app/.cache
ENV SENTENCE_TRANSFORMERS_HOME=/app/.cache
ENV PYTHONUNBUFFERED=1

COPY . .

EXPOSE 8085

HEALTHCHECK --interval=30s --timeout=10s --start-period=90s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8085/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8085"]

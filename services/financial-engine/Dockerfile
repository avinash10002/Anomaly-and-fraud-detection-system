FROM python:3.12-slim

LABEL description="MPLAD Financial Engine — statistical + ML anomaly detection"

WORKDIR /app

# scikit-learn needs C build tools on slim — pre-built wheels avoid this
RUN pip install --no-cache-dir --upgrade pip

COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

COPY . .

EXPOSE 8081

HEALTHCHECK --interval=20s --timeout=8s --start-period=60s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8081/health')"

CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8081"]

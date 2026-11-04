# UC10 Doc Anonymizer — Presidio + spaCy FastAPI Service
# Self-contained build with Dutch and English spaCy LG models baked in at build time.
FROM python:3.12-slim

ARG NL_MODEL=https://github.com/explosion/spacy-models/releases/download/nl_core_news_lg-3.7.0/nl_core_news_lg-3.7.0-py3-none-any.whl
ARG EN_MODEL=https://github.com/explosion/spacy-models/releases/download/en_core_web_lg-3.7.1/en_core_web_lg-3.7.1-py3-none-any.whl

WORKDIR /app

# Install system dependencies (if needed by packages like lxml or pymupdf)
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    && rm -rf /var/lib/apt/lists/*

COPY requirements.txt .

# Pre-install models so service can run offline and as non-root user
RUN pip install --no-cache-dir -r requirements.txt "$NL_MODEL" "$EN_MODEL"

COPY app.py .

RUN useradd --system --no-create-home presidio
USER presidio

EXPOSE 5002

HEALTHCHECK --interval=30s --timeout=5s --start-period=60s --retries=3 \
    CMD python3 -c "import urllib.request; urllib.request.urlopen('http://localhost:5002/health')" || exit 1

CMD ["uvicorn", "app:app", "--host", "0.0.0.0", "--port", "5002"]

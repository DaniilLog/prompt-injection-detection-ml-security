
FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1 \
    OMP_NUM_THREADS=1

WORKDIR /app

# Non-root application user
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 \
       --no-create-home appuser

# Install runtime dependencies
COPY requirements-runtime.txt /app/

RUN python -m pip install \
    --no-cache-dir \
    -r requirements-runtime.txt

# API, inference and monitoring
COPY --chown=10001:10001 \
    src/__init__.py \
    src/api.py \
    src/predict.py \
    src/inference_worker.py \
    src/observability.py \
    /app/src/

# Web interface
COPY --chown=10001:10001 \
    static/ /app/static/

# Verified model
COPY --chown=10001:10001 \
    models/baseline_tfidf_logreg.joblib \
    /app/models/

# Model SHA256 reference
COPY --chown=10001:10001 \
    security/model.sha256 \
    /app/security/

USER 10001:10001

EXPOSE 8000

# Readiness check
HEALTHCHECK --interval=30s \
    --timeout=5s \
    --start-period=30s \
    --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://127.0.0.1:8000/health', timeout=3).read()" || exit 1

# Single API process with isolated ML worker
CMD ["python", "-m", "uvicorn", \
     "src.api:app", \
     "--host", "0.0.0.0", \
     "--port", "8000", \
     "--workers", "1", \
     "--no-proxy-headers", \
     "--no-access-log"]

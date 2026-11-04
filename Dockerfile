FROM python:3.12.16-slim-trixie

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    OPENBLAS_NUM_THREADS=1

WORKDIR /app

# Non-root application user
RUN groupadd --gid 10001 appuser \
    && useradd --uid 10001 --gid 10001 \
       --no-create-home appuser

# Runtime dependencies only
COPY requirements-runtime.txt ./

RUN python -m pip install \
    --no-cache-dir \
    -r requirements-runtime.txt

# Application and verified model artifact
COPY --chown=10001:10001 \
    src/__init__.py src/predict.py /app/src/

COPY --chown=10001:10001 \
    models/baseline_tfidf_logreg.joblib /app/models/

COPY --chown=10001:10001 \
    security/model.sha256 /app/security/

# Never run application as root
USER 10001:10001

# Prediction smoke test
CMD ["python", "-c", "from src.predict import predict; print(predict({'text': 'What is machine learning?'}))"]

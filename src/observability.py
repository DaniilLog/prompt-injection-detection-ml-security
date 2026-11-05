
import json
import logging
from datetime import UTC, datetime

from prometheus_client import Counter, Histogram

MODEL_VERSION = "lab2-v1"

REQUESTS = Counter(
    "ml_api_requests_total",
    "Total HTTP requests",
    ["route", "method", "status"],
)

DURATION = Histogram(
    "ml_api_request_duration_seconds",
    "HTTP request duration in seconds",
    ["route", "method"],
    buckets=(0.005, 0.01, 0.025, 0.05, 0.1,
             0.25, 0.5, 1, 2, 5),
)

REJECTIONS = Counter(
    "ml_api_rejections_total",
    "Rejected prediction requests",
    ["reason"],
)

REASONS = {
    400: "malformed_request",
    401: "authentication",
    413: "body_size",
    415: "media_type",
    422: "validation",
    429: "rate_limit",
    504: "inference_timeout",
    503: "service_unavailable",
}

KNOWN_ROUTES = {
    "/",
    "/health",
    "/predict",
    "/metrics",
    "/static",
}

access_logger = logging.getLogger("ml_security.access")
access_logger.setLevel(logging.INFO)
access_logger.propagate = False

if not access_logger.handlers:
    handler = logging.StreamHandler()
    handler.setFormatter(logging.Formatter("%(message)s"))
    access_logger.addHandler(handler)


def record_request(
    request_id,
    method,
    route,
    status,
    duration,
):
    # Фиксированный набор labels:
    # пользовательские данные не допускаются.
    if route not in KNOWN_ROUTES:
        route = "unmatched"

    if method not in {"GET", "POST"}:
        method = "OTHER"

    # Не учитываем сам сбор метрик.
    if route != "/metrics":
        REQUESTS.labels(
            route=route,
            method=method,
            status=str(status),
        ).inc()

        DURATION.labels(
            route=route,
            method=method,
        ).observe(duration)

        if route == "/predict" and status in REASONS:
            REJECTIONS.labels(
                reason=REASONS[status]
            ).inc()

    event = {
        "timestamp": datetime.now(UTC).isoformat(),
        "request_id": request_id,
        "route": route,
        "method": method,
        "status": status,
        "duration_ms": round(duration * 1000, 2),
        "model_version": MODEL_VERSION,
        "failure_type": (
            REASONS.get(status, "none")
            if route == "/predict"
            else "none"
        ),
    }

    # Не записываем токены, тела запросов
    # или персональные данные.
    access_logger.info(
        json.dumps(event, ensure_ascii=False)
    )

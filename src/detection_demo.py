
import json
import time
from datetime import UTC, datetime
from pathlib import Path

import httpx
from prometheus_client.parser import text_string_to_metric_families

BASE_URL = "http://127.0.0.1:8000"
CONFIG = Path.home() / ".config/ml-project"

THRESHOLD = 3
WINDOW_SECONDS = 60


def read_token(filename):
    return (CONFIG / filename).read_text(
        encoding="utf-8"
    ).strip()


def get_401_count(metrics_text):
    for family in text_string_to_metric_families(
        metrics_text
    ):
        for sample in family.samples:
            if (
                sample.name == "ml_api_requests_total"
                and sample.labels.get("route") == "/predict"
                and sample.labels.get("method") == "POST"
                and sample.labels.get("status") == "401"
            ):
                return float(sample.value)

    return 0.0


def collect_count(client, metrics_token):
    response = client.get(
        "/metrics",
        headers={
            "Authorization": f"Bearer {metrics_token}"
        },
    )
    response.raise_for_status()
    return get_401_count(response.text)


def valid_prediction(client, api_token):
    response = client.post(
        "/predict",
        headers={
            "Authorization": f"Bearer {api_token}"
        },
        json={"text": "What is machine learning?"},
    )
    if response.status_code != 200:
        raise RuntimeError(
            f"Valid prediction failed: HTTP {response.status_code}"
        )
    return response.json()["prediction"]


def main():
    api_token = read_token("api_token")
    metrics_token = read_token("metrics_token")

    print("=== DETECTION SCENARIO ===")
    print("Rule: >= 3 HTTP 401 responses within 60 seconds")

    with httpx.Client(
        base_url=BASE_URL,
        timeout=10,
    ) as client:

        # 1. Проверка нормального состояния
        health = client.get("/health")
        if health.status_code != 200:
            raise RuntimeError(
                f"Health check failed: HTTP {health.status_code}"
            )
        initial_prediction = valid_prediction(
            client, api_token
        )

        print("\nBEFORE SCENARIO")
        print("Health:", health.status_code)
        print("Prediction:", initial_prediction)

        before = collect_count(client, metrics_token)
        print("401 counter before:", before)

        # 2. Контролируемые негативные запросы
        started_utc = datetime.now(UTC).isoformat()
        started = time.monotonic()

        attempts = []

        print("\nSIMULATED INVALID AUTH REQUESTS")

        for i in range(THRESHOLD):
            response = client.post(
                "/predict",
                headers={
                    "Authorization": (
                        "Bearer invalid-demonstration-token"
                    )
                },
                json={"text": "Hello"},
            )

        if response.status_code != 401:
            raise RuntimeError(
                f"Expected HTTP 401, got {response.status_code}"
            )

            request_id = response.json()["request_id"]

            attempts.append({
                "status": response.status_code,
                "request_id": request_id,
            })

            print(
                f"Attempt {i + 1}: "
                f"HTTP {response.status_code}, "
                f"request_id={request_id}"
            )

        # 3. Считывание метрик после сценария
        after = collect_count(client, metrics_token)
        elapsed = time.monotonic() - started
        finished_utc = datetime.now(UTC).isoformat()

        delta = after - before
        triggered = (
            delta >= THRESHOLD
            and elapsed <= WINDOW_SECONDS
        )

        print("\nDETECTION RESULT")
        print("401 counter after:", after)
        print("New 401 responses:", delta)
        print("Elapsed seconds:", round(elapsed, 3))
        print(
            "ALERT:",
            "TRIGGERED" if triggered else "NOT TRIGGERED"
        )

        # 4. Проверка восстановления
        recovery_health = client.get("/health")
        recovery_prediction = valid_prediction(
            client, api_token
        )

        print("\nRECOVERY CHECK")
        print("Health:", recovery_health.status_code)
        print("Prediction:", recovery_prediction)

        recovered = (
            recovery_health.status_code == 200
            and recovery_prediction in {"BENIGN", "INJECTION"}
        )

    # 5. Сохранение доказательств
    report = {
        "scenario": "controlled_invalid_auth",
        "simulation": True,
        "rule": {
            "http_status": 401,
            "threshold": THRESHOLD,
            "window_seconds": WINDOW_SECONDS,
        },
        "started_utc": started_utc,
        "finished_utc": finished_utc,
        "elapsed_seconds": round(elapsed, 3),
        "counter_before": before,
        "counter_after": after,
        "counter_delta": delta,
        "attempts": attempts,
        "alert_triggered": triggered,
        "health_after": recovery_health.status_code,
        "prediction_after": recovery_prediction,
        "recovered": recovered,
    }

    output = Path("metrics/detection_demo.json")
    output.parent.mkdir(parents=True, exist_ok=True)

    output.write_text(
        json.dumps(report, indent=4),
        encoding="utf-8",
    )

    print("\nReport saved:", output)

    if not triggered or not recovered:
        raise SystemExit(1)

    print("\nDETECTION SCENARIO PASSED")


if __name__ == "__main__":
    main()

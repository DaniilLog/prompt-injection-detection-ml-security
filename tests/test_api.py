
from unittest.mock import Mock

import pytest
from fastapi.testclient import TestClient

import src.predict as model_io
from src import api

TEST_TOKEN = "test-only-token-12345678901234567890"
AUTH = {"Authorization": f"Bearer {TEST_TOKEN}"}



@pytest.fixture
def client(monkeypatch):
    monkeypatch.setenv("ML_API_TOKEN", TEST_TOKEN)

    model = Mock()
    model.predict.return_value = [0]

    class FakeWorker:
        def __init__(self, timeout_seconds=5.0):
            self.ready = False

        def start(self):
            self.ready = True

        def predict(self, text):
            label = int(model.predict([text])[0])

            return {
                "label": label,
                "class_name": (
                    "INJECTION" if label == 1 else "BENIGN"
                ),
            }

        def stop(self):
            self.ready = False

    monkeypatch.setattr(api, "ModelWorker", FakeWorker)

    with TestClient(api.app) as test_client:
        with api.rate_lock:
            api.rate_history.clear()

        yield test_client, model


# 1. Положительная проверка /health
def test_health_healthy(client):
    http, _ = client

    response = http.get("/health")

    assert response.status_code == 200
    assert response.json() == {
        "status": "healthy",
        "model_version": "lab2-v1",
    }


# 2. Проверка веб-интерфейса
def test_web_interface(client):
    http, _ = client

    page = http.get("/")
    script = http.get("/static/app.js")

    assert page.status_code == 200
    assert "Prompt Injection Detector" in page.text
    assert script.status_code == 200


# 3. Успешное предсказание
def test_valid_prediction(client):
    http, model = client

    response = http.post(
        "/predict",
        headers=AUTH,
        json={"text": "What is machine learning?"},
    )

    assert response.status_code == 200

    data = response.json()

    assert data["prediction"] == "BENIGN"
    assert data["model_version"] == "lab2-v1"
    assert data["request_id"]

    model.predict.assert_called_once_with(
        ["What is machine learning?"]
    )


# 4–5. Отсутствующий и неверный токен
@pytest.mark.parametrize(
    "authorization",
    [
        None,
        "Bearer wrong-token",
    ],
)
def test_invalid_auth(client, authorization):
    http, model = client

    headers = {}

    if authorization is not None:
        headers["Authorization"] = authorization

    response = http.post(
        "/predict",
        headers=headers,
        json={"text": "Hello"},
    )

    assert response.status_code == 401
    assert response.json()["error"] == "Unauthorized"
    model.predict.assert_not_called()


# 6–10. Нарушения схемы и ограничений текста
@pytest.mark.parametrize(
    "payload",
    [
        {"text": ""},
        {"text": 123},
        {},
        {"text": "A" * (api.MAX_TEXT_LENGTH + 1)},
        {"text": "Hello\x00world"},
    ],
)
def test_invalid_input(client, payload):
    http, model = client

    response = http.post(
        "/predict",
        headers=AUTH,
        json=payload,
    )

    assert response.status_code == 422
    model.predict.assert_not_called()


# 11. Неподдерживаемый Content-Type
def test_unsupported_media_type(client):
    http, model = client

    response = http.post(
        "/predict",
        headers={
            **AUTH,
            "Content-Type": "text/plain",
        },
        content="Hello",
    )

    assert response.status_code == 415
    model.predict.assert_not_called()


# 12. Превышение размера тела запроса
def test_body_too_large(client):
    http, model = client

    response = http.post(
        "/predict",
        headers={
            **AUTH,
            "Content-Type": "application/json",
        },
        content=b"x" * (api.MAX_BODY_BYTES + 1),
    )

    assert response.status_code == 413
    model.predict.assert_not_called()


# 13. Некорректный JSON
def test_malformed_json(client):
    http, model = client

    response = http.post(
        "/predict",
        headers={
            **AUTH,
            "Content-Type": "application/json",
        },
        content=b'{"text":',
    )

    assert response.status_code == 400
    model.predict.assert_not_called()


# 14. Rate limiting: только три запроса
def test_rate_limit(client, monkeypatch):
    http, model = client

    # Малый лимит исключительно для теста.
    monkeypatch.setattr(api, "RATE_LIMIT", 2)

    responses = [
        http.post(
            "/predict",
            headers=AUTH,
            json={"text": "Hello"},
        )
        for _ in range(3)
    ]

    assert [r.status_code for r in responses] == [
        200, 200, 429
    ]

    assert model.predict.call_count == 2


# 15. Неверный SHA256: модель не загружается
def test_health_unavailable_on_bad_hash(
    monkeypatch, tmp_path
):
    model_path = tmp_path / "invalid_model.joblib"
    model_path.write_bytes(b"fake-model-for-test")

    hash_path = tmp_path / "model.sha256"
    hash_path.write_text(
        "0" * 64
        + "  models/baseline_tfidf_logreg.joblib\n",
        encoding="utf-8",
    )

    monkeypatch.setattr(
        model_io, "MODEL_PATH", model_path
    )
    monkeypatch.setattr(
        model_io, "HASH_PATH", hash_path
    )
    monkeypatch.setenv("ML_API_TOKEN", TEST_TOKEN)

    # Проверяем, что десериализация не вызывается.
    load_spy = Mock()
    monkeypatch.setattr(
        model_io.joblib, "load", load_spy
    )


    class HashMismatchWorker:
        ready = False

        def __init__(self, timeout_seconds=5.0):
            pass

        def start(self):
            # Вызываем настоящую проверку SHA256.
            model_io.load_model()

        def stop(self):
            pass

    monkeypatch.setattr(
        api, "ModelWorker", HashMismatchWorker
    )

    model_io.load_model.cache_clear()

    try:
        with TestClient(api.app) as http:
            health = http.get("/health")

            prediction = http.post(
                "/predict",
                headers=AUTH,
                json={"text": "Hello"},
            )

            assert health.status_code == 503
            assert health.json()["status"] == "unavailable"
            assert prediction.status_code == 503

            load_spy.assert_not_called()
    finally:
        model_io.load_model.cache_clear()

def test_rate_limit_invalid_tokens(client, monkeypatch):
    http, model = client

    # Тестируем только три запроса.
    monkeypatch.setattr(api, "RATE_LIMIT", 2)

    responses = [
        http.post(
            "/predict",
            headers={
                "Authorization": "Bearer invalid-test-token"
            },
            json={"text": "Hello"},
        )
        for _ in range(3)
    ]

    assert [r.status_code for r in responses] == [
        401, 401, 429
    ]

    model.predict.assert_not_called()

def test_worker_timeout(client, monkeypatch):
    http, model = client
    worker = http.app.state.worker

    def simulated_timeout(text):
        worker.ready = False
        raise api.WorkerTimeout("Simulated timeout")

    monkeypatch.setattr(
        worker, "predict", simulated_timeout
    )

    response = http.post(
        "/predict",
        headers=AUTH,
        json={"text": "What is machine learning?"},
    )

    assert response.status_code == 504
    assert response.json()["error"] == "Prediction timed out"

    # После сбоя worker сервис не должен быть healthy.
    health = http.get("/health")

    assert health.status_code == 503
    assert health.json()["status"] == "unavailable"

    # Настоящее предсказание не выполнялось.
    model.predict.assert_not_called()


import asyncio
import json
import logging
import os
import secrets
import time
import uuid
from collections import defaultdict, deque
from contextlib import asynccontextmanager
from pathlib import Path
from threading import Lock

from fastapi import FastAPI, Request
from fastapi.responses import FileResponse, JSONResponse, Response
from fastapi.staticfiles import StaticFiles
from prometheus_client import CONTENT_TYPE_LATEST, generate_latest

from src.inference_worker import (
    ModelWorker,
    WorkerBusy,
    WorkerTimeout,
    WorkerUnavailable,
)
from src.observability import record_request
from src.predict import MAX_TEXT_LENGTH

# ============================================================
# 1. Конфигурация приложения
# ============================================================

MODEL_VERSION = "lab2-v1"

MAX_BODY_BYTES = 32 * 1024

RATE_LIMIT = 10
RATE_WINDOW = 60

INFERENCE_TIMEOUT = 5.0

WEB_DIR = Path(__file__).resolve().parent.parent / "static"

logger = logging.getLogger(__name__)

# Rate limiting по IP-адресу.
# Хранилище рассчитано на один процесс.
rate_history = defaultdict(deque)
rate_lock = Lock()


# ============================================================
# 2. Инициализация и завершение приложения
# ============================================================

@asynccontextmanager
async def lifespan(app: FastAPI):

    app.state.worker = ModelWorker(
        timeout_seconds=INFERENCE_TIMEOUT
    )

    app.state.api_token = None

    # API-токен получаем только из переменной окружения.
    token = os.environ.get("ML_API_TOKEN", "")

    if len(token) < 24:
        logger.error("API authentication not configured")
    else:
        app.state.api_token = token

    # ML-worker самостоятельно загружает модель
    # и проверяет SHA256 до десериализации.
    try:
        app.state.worker.start()

        logger.info(
            "Model worker initialized successfully"
        )

    except Exception as exc:  # noqa: BLE001
        logger.error(
            "Model worker initialization failed: %s",
            type(exc).__name__,
        )

    # Очищаем лимитер при запуске приложения.
    with rate_lock:
        rate_history.clear()

    try:
        yield

    finally:
        # Корректно останавливаем отдельный ML-процесс.
        app.state.worker.stop()

        app.state.worker = None
        app.state.api_token = None

        logger.info("Application shutdown completed")


# ============================================================
# 3. Создание FastAPI
# ============================================================

app = FastAPI(
    title="Prompt Injection Detection API",
    description="Secure ML inference service",
    version="1.0.0",
    lifespan=lifespan,
)


# ============================================================
# 4. Middleware мониторинга
# ============================================================

@app.middleware("http")
async def monitoring_middleware(
    request: Request,
    call_next,
):
    # Создаем единый идентификатор запроса
    # для ответа клиенту и серверных логов.
    request.state.request_id = str(uuid.uuid4())

    started = time.perf_counter()
    status = 500

    try:
        response = await call_next(request)

        status = response.status_code

        return response

    finally:
        duration = time.perf_counter() - started

        matched_route = request.scope.get("route")

        route = getattr(
            matched_route,
            "path",
            "unmatched",
        )

        record_request(
            request_id=request.state.request_id,
            method=request.method,
            route=route,
            status=status,
            duration=duration,
        )


# ============================================================
# 5. Формирование безопасных ошибок
# ============================================================

def error_response(
    status,
    message,
    request_id,
):
    headers = {}

    if status == 401:
        headers["WWW-Authenticate"] = "Bearer"

    if status == 429:
        headers["Retry-After"] = str(RATE_WINDOW)

    return JSONResponse(
        status_code=status,
        content={
            "error": message,
            "request_id": request_id,
        },
        headers=headers,
    )


# ============================================================
# 6. Аутентификация
# ============================================================

def check_auth(request: Request):
    expected = request.app.state.api_token

    if not expected:
        return False

    authorization = request.headers.get(
        "authorization",
        "",
    )

    scheme, separator, supplied = (
        authorization.partition(" ")
    )

    if separator != " ":
        return False

    if scheme.lower() != "bearer":
        return False

    return secrets.compare_digest(
        supplied,
        expected,
    )


# ============================================================
# 7. Rate limiting по IP
# ============================================================

def check_rate_limit(request: Request):

    # Используем IP непосредственного подключения.
    # Не доверяем произвольным X-Forwarded-For.
    client_ip = (
        request.client.host
        if request.client is not None
        else "unknown"
    )

    now = time.monotonic()

    with rate_lock:

        # Ограничиваем количество IP в памяти.
        if (
            client_ip not in rate_history
            and len(rate_history) >= 1024
        ):
            expired = [
                key
                for key, events in rate_history.items()
                if (
                    not events
                    or now - events[-1] >= RATE_WINDOW
                )
            ]

            for key in expired:
                del rate_history[key]

            if len(rate_history) >= 1024:
                return False

        events = rate_history[client_ip]

        # Удаляем запросы за пределами окна.
        while (
            events
            and now - events[0] >= RATE_WINDOW
        ):
            events.popleft()

        if len(events) >= RATE_LIMIT:
            return False

        events.append(now)

        return True


# ============================================================
# 8. Запрет специальных JSON-значений
# ============================================================

def reject_json_constant(value):
    raise ValueError("Non-finite JSON value")


# ============================================================
# 9. GET /health
# ============================================================

@app.get("/health")
def health(request: Request):

    worker = getattr(
        request.app.state,
        "worker",
        None,
    )

    # Сервис готов только при работающем worker
    # и настроенной аутентификации.
    if (
        worker is None
        or not worker.ready
        or request.app.state.api_token is None
    ):
        return JSONResponse(
            status_code=503,
            content={
                "status": "unavailable",
            },
        )

    return {
        "status": "healthy",
        "model_version": MODEL_VERSION,
    }


# ============================================================
# 10. POST /predict
# ============================================================

@app.post("/predict")
async def predict_endpoint(request: Request):

    request_id = request.state.request_id

    # --------------------------------------------------------
    # 10.1. Проверка готовности ML-worker
    # --------------------------------------------------------

    worker = request.app.state.worker

    if (
        worker is None
        or not worker.ready
        or request.app.state.api_token is None
    ):
        return error_response(
            503,
            "Service unavailable",
            request_id,
        )

    # --------------------------------------------------------
    # 10.2. Rate limiting
    # --------------------------------------------------------

    # Лимит проверяем до аутентификации,
    # чтобы учитывать неправильные токены.
    if not check_rate_limit(request):
        return error_response(
            429,
            "Rate limit exceeded",
            request_id,
        )

    # --------------------------------------------------------
    # 10.3. Проверка API-токена
    # --------------------------------------------------------

    if not check_auth(request):
        return error_response(
            401,
            "Unauthorized",
            request_id,
        )

    # --------------------------------------------------------
    # 10.4. Проверка Content-Type
    # --------------------------------------------------------

    content_type = (
        request.headers.get("content-type", "")
        .split(";")[0]
        .strip()
        .lower()
    )

    if content_type != "application/json":
        return error_response(
            415,
            "Unsupported media type",
            request_id,
        )

    # --------------------------------------------------------
    # 10.5. Потоковое ограничение размера тела
    # --------------------------------------------------------

    body = bytearray()

    try:
        async for chunk in request.stream():

            if len(body) + len(chunk) > MAX_BODY_BYTES:
                return error_response(
                    413,
                    "Request body too large",
                    request_id,
                )

            body.extend(chunk)

    except Exception:  # noqa: BLE001
        # Не раскрываем клиенту детали ошибок чтения.
        return error_response(
            400,
            "Invalid request body",
            request_id,
        )

    # --------------------------------------------------------
    # 10.6. Разбор JSON
    # --------------------------------------------------------

    try:
        payload = json.loads(
            body.decode("utf-8"),
            parse_constant=reject_json_constant,
        )

    except (ValueError, UnicodeError):
        return error_response(
            400,
            "Malformed JSON",
            request_id,
        )

    # --------------------------------------------------------
    # 10.7. Проверка структуры JSON
    # --------------------------------------------------------

    if not isinstance(payload, dict):
        return error_response(
            422,
            "Expected JSON object",
            request_id,
        )

    if set(payload) != {"text"}:
        return error_response(
            422,
            "Expected only text field",
            request_id,
        )

    text = payload["text"]

    # --------------------------------------------------------
    # 10.8. Проверка типа текста
    # --------------------------------------------------------

    if not isinstance(text, str):
        return error_response(
            422,
            "Text must be a string",
            request_id,
        )

    # --------------------------------------------------------
    # 10.9. Проверка пустого текста
    # --------------------------------------------------------

    if not text.strip():
        return error_response(
            422,
            "Text cannot be empty",
            request_id,
        )

    # --------------------------------------------------------
    # 10.10. Ограничение длины текста
    # --------------------------------------------------------

    if len(text) > MAX_TEXT_LENGTH:
        return error_response(
            422,
            "Text exceeds length limit",
            request_id,
        )

    # --------------------------------------------------------
    # 10.11. Запрет нулевых байтов
    # --------------------------------------------------------

    if "\x00" in text:
        return error_response(
            422,
            "Null bytes are not allowed",
            request_id,
        )

    # --------------------------------------------------------
    # 10.12. Предсказание через отдельный ML-процесс
    # --------------------------------------------------------

    try:
        result = await asyncio.to_thread(
            worker.predict,
            text,
        )

    except WorkerBusy:
        return error_response(
            503,
            "Inference worker busy",
            request_id,
        )

    except WorkerTimeout:
        logger.warning(
            "Inference worker timed out"
        )

        return error_response(
            504,
            "Prediction timed out",
            request_id,
        )

    except WorkerUnavailable:
        logger.error(
            "Inference worker unavailable"
        )

        return error_response(
            503,
            "Prediction unavailable",
            request_id,
        )

    except Exception:  # noqa: BLE001
        logger.error(
            "Unexpected inference failure"
        )

        return error_response(
            503,
            "Prediction unavailable",
            request_id,
        )

    # --------------------------------------------------------
    # 10.13. Успешный результат
    # --------------------------------------------------------

    return {
        "prediction": result["class_name"],
        "model_version": MODEL_VERSION,
        "request_id": request_id,
    }


# ============================================================
# 11. GET /metrics
# ============================================================

@app.get("/metrics", include_in_schema=False)
def metrics_endpoint(request: Request):

    # Отдельный секрет мониторинга.
    expected = os.environ.get(
        "ML_METRICS_TOKEN",
        "",
    )

    authorization = request.headers.get(
        "authorization",
        "",
    )

    scheme, separator, token = (
        authorization.partition(" ")
    )

    authenticated = (
        len(expected) >= 24
        and separator == " "
        and scheme.lower() == "bearer"
        and secrets.compare_digest(
            token,
            expected,
        )
    )

    if not authenticated:
        return JSONResponse(
            status_code=401,
            content={
                "error": "Unauthorized",
            },
            headers={
                "WWW-Authenticate": "Bearer",
            },
        )

    return Response(
        content=generate_latest(),
        media_type=CONTENT_TYPE_LATEST,
        headers={
            "Cache-Control": "no-store",
        },
    )


# ============================================================
# 12. Веб-интерфейс
# ============================================================

@app.get("/", include_in_schema=False)
def index():

    return FileResponse(
        WEB_DIR / "index.html",
        headers={
            "Cache-Control": "no-store",
            "X-Content-Type-Options": "nosniff",
            "Referrer-Policy": "no-referrer",
            "Content-Security-Policy": (
                "default-src 'none'; "
                "script-src 'self'; "
                "style-src 'self'; "
                "connect-src 'self'; "
                "base-uri 'none'; "
                "frame-ancestors 'none'; "
                "form-action 'self'"
            ),
        },
    )


# ============================================================
# 13. Статические файлы
# ============================================================

app.mount(
    "/static",
    StaticFiles(directory=WEB_DIR),
    name="static",
)

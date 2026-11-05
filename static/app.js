
"use strict";

const form = document.getElementById("predict-form");
const tokenInput = document.getElementById("token");
const promptInput = document.getElementById("prompt");
const submitButton = document.getElementById("submit");

const counter = document.getElementById("counter");
const health = document.getElementById("health");

const panel = document.getElementById("result-panel");
const title = document.getElementById("result-title");
const message = document.getElementById("result-message");
const httpStatus = document.getElementById("result-http");
const version = document.getElementById("result-version");
const requestId = document.getElementById("result-id");

function showResult(kind, heading, description, status, data = {}) {
    panel.hidden = false;
    panel.dataset.kind = kind;

    // textContent защищает от интерпретации
    // недоверенных строк как HTML.
    title.textContent = heading;
    message.textContent = description;
    httpStatus.textContent = String(status);
    version.textContent = String(data.model_version ?? "-");
    requestId.textContent = String(data.request_id ?? "-");
}

function errorMessage(status) {
    const messages = {
        400: "Некорректное тело запроса.",
        401: "Неверный или отсутствующий API-токен.",
        413: "Превышен допустимый размер запроса.",
        415: "Неподдерживаемый формат данных.",
        422: "Проверьте текст и структуру запроса.",
        429: "Слишком много запросов. Повторите позднее.",
        503: "Сервис временно недоступен."
    };

    return messages[status] ?? "Не удалось выполнить проверку.";
}

promptInput.addEventListener("input", () => {
    counter.textContent = `${promptInput.value.length} / 2000`;
});

async function checkHealth() {
    try {
        const response = await fetch("/health", {
            cache: "no-store"
        });

        const data = await response.json();

        if (response.ok && data.status === "healthy") {
            health.textContent = "● API HEALTHY";
            health.className = "health healthy";
        } else {
            health.textContent = "● API UNAVAILABLE";
            health.className = "health unavailable";
        }
    } catch {
        health.textContent = "● API OFFLINE";
        health.className = "health unavailable";
    }
}

form.addEventListener("submit", async (event) => {
    event.preventDefault();

    const text = promptInput.value;
    const token = tokenInput.value;

    if (!text.trim()) {
        showResult(
            "error", "Ошибка ввода",
            "Текст не может быть пустым.", 422
        );
        return;
    }

    submitButton.disabled = true;
    submitButton.textContent = "Проверка...";
    panel.hidden = true;

    try {
        const response = await fetch("/predict", {
            method: "POST",
            cache: "no-store",
            headers: {
                "Content-Type": "application/json",
                "Authorization": `Bearer ${token}`
            },
            body: JSON.stringify({ text })
        });

        const data = await response.json();

        if (!response.ok) {
            showResult(
                "error",
                `Ошибка HTTP ${response.status}`,
                errorMessage(response.status),
                response.status,
                data
            );
            return;
        }

        if (data.prediction === "BENIGN") {
            showResult(
                "benign",
                "BENIGN — безопасный запрос",
                "Модель не обнаружила признаков prompt injection.",
                response.status,
                data
            );
        } else if (data.prediction === "INJECTION") {
            showResult(
                "injection",
                "INJECTION — подозрительный запрос",
                "Модель обнаружила признаки prompt injection.",
                response.status,
                data
            );
        } else {
            showResult(
                "error",
                "Неизвестный ответ",
                "Сервер вернул неожиданный класс.",
                response.status,
                data
            );
        }
    } catch {
        showResult(
            "error",
            "Ошибка соединения",
            "Не удалось связаться с API.",
            "-"
        );
    } finally {
        submitButton.disabled = false;
        submitButton.textContent = "Проверить запрос";
    }
});

checkHealth();

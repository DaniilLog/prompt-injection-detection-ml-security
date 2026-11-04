
import hashlib
from functools import lru_cache
from pathlib import Path

import joblib

ROOT = Path(__file__).resolve().parent.parent
MODEL_PATH = ROOT / "models" / "baseline_tfidf_logreg.joblib"
HASH_PATH = ROOT / "security" / "model.sha256"

MAX_TEXT_LENGTH = 2000

CLASS_NAMES = {
    0: "BENIGN",
    1: "INJECTION",
}


class InputValidationError(ValueError):
    """Ошибка проверки входных данных."""


def validate_input(payload):
    if not isinstance(payload, dict):
        raise InputValidationError(
            "Input must be a dictionary"
        )

    if set(payload.keys()) != {"text"}:
        raise InputValidationError(
            "Exactly one field is required: text"
        )

    text = payload["text"]

    if not isinstance(text, str):
        raise InputValidationError(
            "Text must be a string"
        )

    if not text.strip():
        raise InputValidationError(
            "Text cannot be empty"
        )

    if len(text) > MAX_TEXT_LENGTH:
        raise InputValidationError(
            f"Text exceeds {MAX_TEXT_LENGTH} characters"
        )

    if "\x00" in text:
        raise InputValidationError(
            "Null bytes are not allowed"
        )

    return text.strip()


@lru_cache(maxsize=1)
def load_model():
    # Проверяем локальный доверенный артефакт до загрузки.
    expected, filename = HASH_PATH.read_text().split(maxsplit=1)

    if filename.strip() != "models/baseline_tfidf_logreg.joblib":
        raise RuntimeError("Unexpected model artifact")

    with MODEL_PATH.open("rb") as file:
        actual = hashlib.file_digest(file, "sha256").hexdigest()

    if actual != expected:
        raise RuntimeError("Model SHA256 mismatch")

    return joblib.load(MODEL_PATH)


def predict(payload, model=None):
    # Валидация всегда выполняется до вызова модели.
    text = validate_input(payload)

    if model is None:
        model = load_model()

    label = int(model.predict([text])[0])

    if label not in CLASS_NAMES:
        raise RuntimeError("Unexpected prediction label")

    return {
        "label": label,
        "class_name": CLASS_NAMES[label],
    }

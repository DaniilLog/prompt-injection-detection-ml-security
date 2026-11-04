
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from src.predict import load_model, predict

ROOT = Path(__file__).resolve().parent.parent

FIXTURE = ROOT / "ci" / "fixtures" / "validation_200.csv"
MANIFEST = ROOT / "ci" / "fixture_manifest.json"
BASELINE_PATH = ROOT / "ci" / "baseline.json"

MODEL_PATH = ROOT / "models" / "baseline_tfidf_logreg.joblib"

# Эталон создается один раз.
# Запрещаем случайное перезаписывание baseline.
if BASELINE_PATH.exists():
    raise SystemExit(
        "CI baseline already exists. "
        "Do not overwrite it automatically."
    )


def file_sha256(path):
    digest = sha256()

    with path.open("rb") as f:
        for chunk in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


# 1. Проверка целостности контрольной выборки

manifest = json.loads(
    MANIFEST.read_text(encoding="utf-8")
)

actual_hash = file_sha256(FIXTURE)
expected_hash = manifest["fixture_sha256"]

if actual_hash != expected_hash:
    raise ValueError("CI fixture SHA256 mismatch")

print("CI fixture SHA256: OK")


# 2. Загрузка контрольных данных

df = pd.read_csv(FIXTURE)

if list(df.columns) != ["text", "label"]:
    raise ValueError("Invalid fixture schema")

if len(df) != 200:
    raise ValueError("Unexpected fixture size")

if df.isna().any().any():
    raise ValueError("Missing values in fixture")

if not df["label"].isin([0, 1]).all():
    raise ValueError("Invalid labels")

counts = df["label"].value_counts().to_dict()

if counts.get(0) != 100 or counts.get(1) != 100:
    raise ValueError("Invalid class distribution")


# 3. Загрузка локальной модели из ЛР2
# load_model() проверяет SHA256 перед загрузкой.

model = load_model()

# 4. Предсказания через общую функцию ЛР2

predictions = [
    predict({"text": text}, model=model)["label"]
    for text in df["text"]
]

y_true = df["label"].tolist()

# 5. Эталонные метрики

f1 = float(
    f1_score(
        y_true,
        predictions,
        pos_label=1,
        zero_division=0
    )
)

accuracy = float(
    accuracy_score(y_true, predictions)
)

print("\nCI BASELINE RESULTS")
print("Samples:", len(df))
print(f"Accuracy: {accuracy:.4f}")
print(f"F1 INJECTION: {f1:.4f}")

# 6. Сохранение неизменяемого эталона

baseline = {
    "model": "TF-IDF + Logistic Regression",
    "metric": "f1_injection",
    "metric_value": f1,
    "accuracy": accuracy,
    "positive_class": 1,
    "sample_size": len(df),
    "fixture_sha256": actual_hash,
    "model_sha256": file_sha256(MODEL_PATH),
    "seed": 42
}

with BASELINE_PATH.open("x", encoding="utf-8") as f:
    json.dump(
        baseline,
        f,
        indent=4,
        ensure_ascii=False
    )

print("\nBaseline saved:", BASELINE_PATH)
print("Baseline creation completed successfully!")

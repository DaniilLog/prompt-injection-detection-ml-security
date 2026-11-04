
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd
from sklearn.metrics import accuracy_score, f1_score

from src.predict import load_model, predict

ROOT = Path(__file__).resolve().parent.parent

FIXTURE = ROOT / "ci" / "fixtures" / "validation_200.csv"
MANIFEST = ROOT / "ci" / "fixture_manifest.json"
MODEL_PATH = ROOT / "models" / "baseline_tfidf_logreg.joblib"
OUTPUT = ROOT / "metrics" / "ci_candidate.json"


def calculate_sha256(path):
    digest = sha256()

    with path.open("rb") as file:
        for block in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            digest.update(block)

    return digest.hexdigest()


# 1. Проверка версии контрольных данных
manifest = json.loads(
    MANIFEST.read_text(encoding="utf-8")
)

actual_hash = calculate_sha256(FIXTURE)

if actual_hash != manifest["fixture_sha256"]:
    raise ValueError("CI fixture SHA256 mismatch")

print("CI fixture SHA256: OK")


# 2. Загрузка данных
df = pd.read_csv(FIXTURE)

if list(df.columns) != ["text", "label"]:
    raise ValueError("Invalid fixture schema")

if len(df) != 200:
    raise ValueError("Invalid fixture size")

if df.isna().any().any():
    raise ValueError("Missing values")

if not df["label"].isin([0, 1]).all():
    raise ValueError("Invalid labels")


# 3. Загрузка модели с проверкой SHA256
model = load_model()

# 4. Предсказания
predictions = [
    predict({"text": text}, model=model)["label"]
    for text in df["text"]
]

# 5. Вычисление метрик
f1 = float(
    f1_score(
        df["label"],
        predictions,
        pos_label=1,
        zero_division=0
    )
)

accuracy = float(
    accuracy_score(df["label"], predictions)
)

# 6. Сохранение результата кандидата
candidate = {
    "model": "TF-IDF + Logistic Regression",
    "evaluation": "real_model_evaluation",
    "metric": "f1_injection",
    "metric_value": f1,
    "accuracy": accuracy,
    "positive_class": 1,
    "sample_size": len(df),
    "fixture_sha256": actual_hash,
    "source_revision": manifest["source_revision"],
    "model_sha256": calculate_sha256(MODEL_PATH)
}

OUTPUT.parent.mkdir(exist_ok=True)

OUTPUT.write_text(
    json.dumps(
        candidate,
        indent=4,
        ensure_ascii=False
    ),
    encoding="utf-8"
)

print("\nCI CANDIDATE RESULTS")
print("Samples:", len(df))
print(f"Accuracy: {accuracy:.4f}")
print(f"F1 INJECTION: {f1:.4f}")
print("Model SHA256:", candidate["model_sha256"])
print("\nSaved:", OUTPUT)
print("Candidate evaluation completed!")

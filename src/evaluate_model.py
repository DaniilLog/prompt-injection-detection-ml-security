
import json
from hashlib import sha256
from pathlib import Path

import joblib
import matplotlib.pyplot as plt
import pandas as pd
from sklearn.dummy import DummyClassifier
from sklearn.metrics import (
    ConfusionMatrixDisplay,
    accuracy_score,
    classification_report,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
)

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
METRICS_DIR = ROOT / "metrics"
SECURITY_DIR = ROOT / "security"
MODEL_PATH = ROOT / "models" / "baseline_tfidf_logreg.joblib"

METRICS_DIR.mkdir(exist_ok=True)

# 1. Загрузка подготовленных данных
train = pd.read_csv(DATA_DIR / "train.csv")
test = pd.read_csv(DATA_DIR / "test.csv")

X_train = train["text"]
y_train = train["label"]

X_test = test["text"]
y_test = test["label"]

print("Test size:", len(test))

# 2. Загрузка локальной доверенной модели
model = joblib.load(MODEL_PATH)
predictions = model.predict(X_test)

# 3. Расчет метрик
metrics = {
    "accuracy": float(accuracy_score(y_test, predictions)),
    "precision": float(precision_score(
        y_test, predictions, pos_label=1, zero_division=0
    )),
    "recall": float(recall_score(
        y_test, predictions, pos_label=1, zero_division=0
    )),
    "f1": float(f1_score(
        y_test, predictions, pos_label=1, zero_division=0
    )),
}

print("\nTEST METRICS:")
print(json.dumps(metrics, indent=4))

print("\nCLASSIFICATION REPORT:")
report = classification_report(
    y_test,
    predictions,
    labels=[0, 1],
    target_names=["BENIGN", "INJECTION"],
    output_dict=True,
    zero_division=0
)

print(pd.DataFrame(report).transpose().round(4))

# 4. Сравнение с DummyClassifier
dummy = DummyClassifier(strategy="most_frequent")
dummy.fit(X_train.to_frame(), y_train)

dummy_predictions = dummy.predict(X_test.to_frame())

dummy_metrics = {
    "accuracy": float(accuracy_score(y_test, dummy_predictions)),
    "f1": float(f1_score(
        y_test, dummy_predictions, pos_label=1, zero_division=0
    )),
}

print("\nDUMMY CLASSIFIER:")
print(json.dumps(dummy_metrics, indent=4))

# 5. Матрица ошибок
cm = confusion_matrix(y_test, predictions, labels=[0, 1])

print("\nCONFUSION MATRIX:")
print(cm)

disp = ConfusionMatrixDisplay(
    confusion_matrix=cm,
    display_labels=["BENIGN", "INJECTION"]
)

disp.plot(cmap="Blues", values_format="d")
plt.title("Baseline Model - Confusion Matrix")
plt.tight_layout()

figure_path = METRICS_DIR / "confusion_matrix.png"
plt.savefig(figure_path, dpi=180)
plt.close()

# 6. Анализ ошибочных предсказаний
errors = test.loc[y_test != predictions].copy()
errors["prediction"] = predictions[y_test != predictions]

print("\nTOTAL ERRORS:", len(errors))

print("\nFALSE POSITIVES:",
      int(((y_test == 0) & (predictions == 1)).sum()))

print("FALSE NEGATIVES:",
      int(((y_test == 1) & (predictions == 0)).sum()))

print("\nEXAMPLES OF ERRORS:")

for _, row in errors.head(5).iterrows():
    preview = row["text"].replace("\n", " ")[:120]
    print(
        f"True={row['label']}, "
        f"Predicted={row['prediction']}, "
        f"Text={preview!r}"
    )

# 7. Идентификаторы данных и модели
def file_hash(path):
    digest = sha256()
    with open(path, "rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()

revision_lines = (
    SECURITY_DIR / "dataset_revision.txt"
).read_text(encoding="utf-8").splitlines()

dataset_revision = next(
    line.split(":", 1)[1].strip()
    for line in revision_lines
    if line.startswith("Revision:")
)

# 8. Сохранение baseline
results = {
    "model": "TF-IDF + Logistic Regression",
    "primary_metric": "f1_injection",
    "primary_metric_value": metrics["f1"],
    "test_size": len(test),
    "dataset_revision": dataset_revision,
    "processed_test_sha256": file_hash(DATA_DIR / "test.csv"),
    "model_sha256": file_hash(MODEL_PATH),
    "test_metrics": metrics,
    "per_class_metrics": report,
    "dummy_metrics": dummy_metrics,
    "confusion_matrix": cm.tolist(),
    "false_positives": int(cm[0, 1]),
    "false_negatives": int(cm[1, 0]),
}

with open(
    METRICS_DIR / "baseline.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

print("\nSaved:", figure_path)
print("Saved:", METRICS_DIR / "baseline.json")
print("\nEvaluation completed successfully!")

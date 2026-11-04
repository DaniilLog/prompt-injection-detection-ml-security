
import json
from pathlib import Path
from time import perf_counter

import joblib
import pandas as pd
import sklearn
from sklearn.dummy import DummyClassifier
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    f1_score,
    precision_score,
    recall_score,
)
from sklearn.pipeline import Pipeline

ROOT = Path(__file__).resolve().parent.parent

DATA_DIR = ROOT / "data" / "processed"
MODEL_DIR = ROOT / "models"
METRICS_DIR = ROOT / "metrics"

MODEL_DIR.mkdir(exist_ok=True)
METRICS_DIR.mkdir(exist_ok=True)

SEED = 42

# 1. Загрузка подготовленных данных

train = pd.read_csv(DATA_DIR / "train.csv")
validation = pd.read_csv(DATA_DIR / "validation.csv")

X_train = train["text"]
y_train = train["label"]

X_val = validation["text"]
y_val = validation["label"]

print("Train:", len(train))
print("Validation:", len(validation))

# 2. Создание ML-конвейера

model = Pipeline([
    (
        "tfidf",
        TfidfVectorizer(
            max_features=30000,
            ngram_range=(1, 2),
            min_df=2,
            sublinear_tf=True,
        ),
    ),
    (
        "classifier",
        LogisticRegression(
            C=1.0,
            max_iter=1000,
            class_weight="balanced",
            random_state=SEED,
        ),
    ),
])

# 3. Обучение модели

print("\nTraining model...")

start = perf_counter()
model.fit(X_train, y_train)
training_time = perf_counter() - start

print(f"Training time: {training_time:.2f} seconds")

# 4. Предсказания на Validation

predictions = model.predict(X_val)

def calculate_metrics(y_true, y_pred):
    return {
        "accuracy": float(
            accuracy_score(y_true, y_pred)
        ),
        "precision": float(
            precision_score(
                y_true, y_pred, pos_label=1,
                zero_division=0
            )
        ),
        "recall": float(
            recall_score(
                y_true, y_pred, pos_label=1,
                zero_division=0
            )
        ),
        "f1": float(
            f1_score(
                y_true, y_pred, pos_label=1,
                zero_division=0
            )
        ),
    }

model_metrics = calculate_metrics(
    y_val, predictions
)

# 5. Простейшая модель для сравнения

dummy = DummyClassifier(
    strategy="most_frequent"
)

dummy.fit(train[["text"]], y_train)

dummy_predictions = dummy.predict(
    validation[["text"]]
)

dummy_metrics = calculate_metrics(
    y_val, dummy_predictions
)

# 6. Вывод результатов

print("\nLogistic Regression:")
print(json.dumps(model_metrics, indent=4))

print("\nDummyClassifier:")
print(json.dumps(dummy_metrics, indent=4))

# 7. Сохранение модели

model_path = (
    MODEL_DIR / "baseline_tfidf_logreg.joblib"
)

joblib.dump(model, model_path)

print(f"\nModel saved: {model_path}")

# 8. Сохранение параметров и метрик

results = {
    "model": "TF-IDF + Logistic Regression",
    "baseline": "DummyClassifier",
    "seed": SEED,
    "train_size": len(train),
    "validation_size": len(validation),
    "training_time_seconds": round(
        training_time, 4
    ),
    "sklearn_version": sklearn.__version__,
    "parameters": model.get_params(),
    "validation_metrics": model_metrics,
    "dummy_metrics": dummy_metrics,
}

# Удаляем параметры-объекты из словаря:
# сохраняем только конфигурацию компонентов
results["parameters"] = {
    "tfidf_max_features": 30000,
    "tfidf_ngram_range": [1, 2],
    "tfidf_min_df": 2,
    "tfidf_sublinear_tf": True,
    "classifier_C": 1.0,
    "classifier_max_iter": 1000,
    "classifier_class_weight": "balanced",
}

metrics_path = METRICS_DIR / "validation.json"

with open(
    metrics_path,
    "w",
    encoding="utf-8"
) as file:
    json.dump(
        results,
        file,
        indent=4,
        ensure_ascii=False,
    )

print(f"Metrics saved: {metrics_path}")
print("\nTraining completed successfully!")

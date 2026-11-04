
import json
import re
from pathlib import Path

import matplotlib.pyplot as plt
import pandas as pd
from sklearn.metrics import accuracy_score, f1_score, recall_score

from src.predict import MAX_TEXT_LENGTH, predict

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data" / "processed"
METRICS_DIR = ROOT / "metrics"

METRICS_DIR.mkdir(exist_ok=True)

SEED = 42

# 1. Загружаем тестовую выборку
test = pd.read_csv(DATA_DIR / "test.csv")

# Выбираем 10 объектов каждого класса
samples = pd.concat([
    test[test["label"] == label].sample(
        n=10,
        random_state=SEED + label
    )
    for label in [0, 1]
]).sort_index()

print("Selected samples:", len(samples))
print("Class distribution:")
print(samples["label"].value_counts().sort_index())


# 2. Функции изменения текста

def change_case(text):
    return text.swapcase()


def add_spaces(text):
    if " " in text:
        return text.replace(" ", "  ")
    return text + " ."


def add_typo(text):
    # Меняем местами две разные соседние буквы
    for match in re.finditer(r"[A-Za-z]{5,}", text):
        word = list(match.group())

        for i in range(len(word) - 1):
            if word[i].lower() != word[i + 1].lower():
                word[i], word[i + 1] = word[i + 1], word[i]

                return (
                    text[:match.start()]
                    + "".join(word)
                    + text[match.end():]
                )

    return text


transformations = {
    "case_change": change_case,
    "extra_spaces": add_spaces,
    "typo": add_typo,
}


# 3. Эксперимент
records = []

for index, row in samples.iterrows():
    original_text = row["text"]
    true_label = int(row["label"])

    original_prediction = predict({
        "text": original_text
    })["label"]

    for name, transform in transformations.items():
        modified_text = transform(original_text)

        if len(modified_text) > MAX_TEXT_LENGTH:
            raise ValueError("Modified text exceeds limit")

        modified_prediction = predict({
            "text": modified_text
        })["label"]

        records.append({
            "sample_index": int(index),
            "true_label": true_label,
            "transformation": name,
            "text_changed": modified_text != original_text,
            "original_prediction": original_prediction,
            "modified_prediction": modified_prediction,
            "prediction_changed": (
                original_prediction != modified_prediction
            ),
        })

results_df = pd.DataFrame(records)


# 4. Рассчитываем результаты
summary = {
    "seed": SEED,
    "sample_size": len(samples),
    "classes": {
        "BENIGN": 10,
        "INJECTION": 10,
    },
    "transformations": {},
}

print("\nROBUSTNESS RESULTS")

for name in transformations:
    subset = results_df[
        results_df["transformation"] == name
    ]

    y_true = subset["true_label"]
    y_original = subset["original_prediction"]
    y_modified = subset["modified_prediction"]

    flips = int(subset["prediction_changed"].sum())
    total = len(subset)

    data = {
        "total": total,
        "modified_texts": int(subset["text_changed"].sum()),
        "changed_predictions": flips,
        "flip_rate": float(flips / total),
        "original_accuracy": float(
            accuracy_score(y_true, y_original)
        ),
        "modified_accuracy": float(
            accuracy_score(y_true, y_modified)
        ),
        "original_recall_injection": float(
            recall_score(y_true, y_original, zero_division=0)
        ),
        "modified_recall_injection": float(
            recall_score(y_true, y_modified, zero_division=0)
        ),
        "modified_f1_injection": float(
            f1_score(y_true, y_modified, zero_division=0)
        ),
    }

    summary["transformations"][name] = data

    print(f"\n{name}")
    print(f"Changed predictions: {flips}/{total}")
    print(f"Flip rate: {data['flip_rate']:.2%}")
    print(f"Original accuracy: {data['original_accuracy']:.2%}")
    print(f"Modified accuracy: {data['modified_accuracy']:.2%}")
    print(f"Modified recall: {data['modified_recall_injection']:.2%}")


# 5. Нетипичный вход
train = pd.read_csv(DATA_DIR / "train.csv")
max_train_length = int(train["text"].str.len().max())

unusual_text = ("hello " * 180).strip()

unusual_result = predict({
    "text": unusual_text
})

summary["unusual_input"] = {
    "description": "Unusually long repetitive input",
    "length": len(unusual_text),
    "max_train_length": max_train_length,
    "prediction": unusual_result,
}

print("\nUNUSUAL INPUT")
print("Input length:", len(unusual_text))
print("Maximum train length:", max_train_length)
print("Prediction:", unusual_result)


# 6. Сохраняем результаты
with open(
    METRICS_DIR / "robustness.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(summary, f, indent=4, ensure_ascii=False)

# Сохраняем метки и результаты без исходных текстов
results_df.to_csv(
    METRICS_DIR / "robustness_predictions.csv",
    index=False
)


# 7. Строим график
names = list(summary["transformations"])

rates = [
    summary["transformations"][name]["flip_rate"] * 100
    for name in names
]

plt.figure(figsize=(8, 5))
bars = plt.bar(names, rates)

plt.title("Prediction Changes After Text Modifications")
plt.xlabel("Modification type")
plt.ylabel("Changed predictions (%)")
plt.ylim(0, 100)

for bar in bars:
    plt.text(
        bar.get_x() + bar.get_width() / 2,
        bar.get_height() + 1,
        f"{bar.get_height():.1f}%",
        ha="center"
    )

plt.tight_layout()
plt.savefig(
    METRICS_DIR / "robustness_plot.png",
    dpi=180
)
plt.close()

print("\nRobustness experiment completed!")


from pathlib import Path
import pandas as pd
import json

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
OUTPUT_DIR = DATA_DIR / "processed"
METRICS_DIR = ROOT / "metrics"

OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
METRICS_DIR.mkdir(parents=True, exist_ok=True)

RANDOM_STATE = 42


def load_and_validate(name):
    df = pd.read_csv(DATA_DIR / f"{name}.csv")

    if set(df.columns) != {"text", "label"}:
        raise ValueError(f"{name}: Invalid columns")

    if df[["text", "label"]].isna().any().any():
        raise ValueError(f"{name}: Missing values")

    if not df["text"].map(
        lambda x: isinstance(x, str) and bool(x.strip())
    ).all():
        raise ValueError(f"{name}: Invalid text")

    if not pd.api.types.is_integer_dtype(df["label"]):
        raise ValueError(f"{name}: Invalid label type")

    if not df["label"].isin([0, 1]).all():
        raise ValueError(f"{name}: Invalid labels")

    return df


def clean_duplicates(df):
    # Исключаем тексты с противоречивыми метками
    conflicts = df.groupby("text")["label"].nunique()
    conflicting_texts = set(conflicts[conflicts > 1].index)

    df = df[~df["text"].isin(conflicting_texts)].copy()

    # Оставляем по одной записи на текст
    df = df.drop_duplicates(subset=["text"])

    return df.reset_index(drop=True)


train = load_and_validate("train")
validation = load_and_validate("validation")
test = load_and_validate("test")

original_sizes = {
    "train": len(train),
    "validation": len(validation),
    "test": len(test)
}

# Тестовая выборка остается неизменной
if test["text"].duplicated().any():
    raise ValueError("Test contains duplicate texts")

# Удаляем дубликаты и противоречивые записи
train = clean_duplicates(train)
validation = clean_duplicates(validation)

# Исключаем пересечения с тестовой выборкой
test_texts = set(test["text"])

train = train[~train["text"].isin(test_texts)].copy()
validation = validation[
    ~validation["text"].isin(test_texts)
].copy()

# Исключаем пересечения Train и Validation
train_texts = set(train["text"])

validation = validation[
    ~validation["text"].isin(train_texts)
].copy()

train = train.reset_index(drop=True)
validation = validation.reset_index(drop=True)

# Проверяем независимость выборок
train_texts = set(train["text"])
validation_texts = set(validation["text"])
test_texts = set(test["text"])

if not train_texts.isdisjoint(validation_texts):
    raise ValueError("Data leakage: Train and Validation overlap")

if not train_texts.isdisjoint(test_texts):
    raise ValueError("Data leakage: Train and Test overlap")

if not validation_texts.isdisjoint(test_texts):
    raise ValueError("Data leakage: Validation and Test overlap")

datasets = {
    "train": train,
    "validation": validation,
    "test": test
}

results = {
    "random_state": RANDOM_STATE,
    "split_method": "Original dataset splits",
    "original_sizes": original_sizes,
    "processed_sizes": {},
    "removed_rows": {},
    "class_distribution": {}
}

for name, df in datasets.items():
    if set(df["label"]) != {0, 1}:
        raise ValueError(f"{name}: Missing class")

    path = OUTPUT_DIR / f"{name}.csv"
    df.to_csv(path, index=False)

    results["processed_sizes"][name] = len(df)
    results["removed_rows"][name] = (
        original_sizes[name] - len(df)
    )

    counts = df["label"].value_counts().sort_index()
    results["class_distribution"][name] = {
        str(k): int(v) for k, v in counts.items()
    }

    print(f"\n{name.upper()}")
    print("Original:", original_sizes[name])
    print("Processed:", len(df))
    print("Removed:", results["removed_rows"][name])
    print("Classes:", results["class_distribution"][name])

with open(
    METRICS_DIR / "data_preparation.json",
    "w",
    encoding="utf-8"
) as f:
    json.dump(results, f, indent=4, ensure_ascii=False)

print("\nData preparation completed successfully!")
print("No overlaps between datasets.")

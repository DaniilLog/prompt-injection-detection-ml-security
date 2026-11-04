
import json
from hashlib import sha256
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "data" / "processed" / "validation.csv"
OUTPUT = ROOT / "ci" / "fixtures" / "validation_200.csv"
MANIFEST = ROOT / "ci" / "fixture_manifest.json"
REVISION_FILE = ROOT / "security" / "dataset_revision.txt"

SEED = 42
SAMPLES_PER_CLASS = 100

OUTPUT.parent.mkdir(parents=True, exist_ok=True)

# 1. Проверка исходной выборки
df = pd.read_csv(SOURCE)

if list(df.columns) != ["text", "label"]:
    raise ValueError("Invalid source schema")

if df.isna().any().any():
    raise ValueError("Missing values in source")

if not df["label"].isin([0, 1]).all():
    raise ValueError("Invalid class labels")

if df["text"].duplicated().any():
    raise ValueError("Duplicate texts in source")

# 2. Фиксированный отбор 100 объектов каждого класса
parts = []

for label in [0, 1]:
    subset = df[df["label"] == label]

    if len(subset) < SAMPLES_PER_CLASS:
        raise ValueError(f"Not enough samples for class {label}")

    sampled = subset.sample(
        n=SAMPLES_PER_CLASS,
        random_state=SEED + label
    )

    parts.append(sampled)

ci_data = (
    pd.concat(parts)
    .sort_index()
    .reset_index(drop=True)
)

# 3. Сохранение в CSV
ci_data.to_csv(OUTPUT, index=False, lineterminator="\n")

# 4. SHA256 контрольной выборки
def calculate_sha256(path):
    digest = sha256()

    with path.open("rb") as file:
        for chunk in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(chunk)

    return digest.hexdigest()


revision_lines = REVISION_FILE.read_text(
    encoding="utf-8"
).splitlines()

revision = next(
    (
        line.split(":", 1)[1].strip()
        for line in revision_lines
        if line.startswith("Revision:")
    ),
    None
)

if not revision:
    raise ValueError("Dataset revision not found")

# 5. Манифест происхождения данных
manifest = {
    "source": "S-Labs/prompt-injection-dataset",
    "license": "MIT",
    "source_split": "processed/validation.csv",
    "source_revision": revision,
    "source_sha256": calculate_sha256(SOURCE),
    "fixture": "ci/fixtures/validation_200.csv",
    "fixture_sha256": calculate_sha256(OUTPUT),
    "seed": SEED,
    "schema": {"text": "string", "label": "integer"},
    "allowed_labels": [0, 1],
    "sample_size": len(ci_data),
    "class_distribution": {
        str(k): int(v)
        for k, v in ci_data["label"].value_counts().items()
    }
}

MANIFEST.write_text(
    json.dumps(manifest, indent=4, ensure_ascii=False),
    encoding="utf-8"
)

print("CI fixture created successfully!")
print("Samples:", len(ci_data))
print("Class distribution:")
print(ci_data["label"].value_counts().sort_index())
print("SHA256:", manifest["fixture_sha256"])
print("Manifest:", MANIFEST)


import shutil
from hashlib import sha256
from pathlib import Path

from huggingface_hub import hf_hub_download

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
SECURITY_DIR = ROOT / "security"

DATASET_REPO = "S-Labs/prompt-injection-dataset"

DATA_DIR.mkdir(parents=True, exist_ok=True)

# Получение зафиксированной ревизии датасета
revision_file = SECURITY_DIR / "dataset_revision.txt"

for line in revision_file.read_text().splitlines():
    if line.startswith("Revision:"):
        REVISION = line.split(":", 1)[1].strip()
        break
else:
    raise ValueError("Dataset revision not found")

# Загрузка контрольных сумм
hashes = {}

for line in (SECURITY_DIR / "datasets.sha256").read_text().splitlines():
    expected_hash, filename = line.split(maxsplit=1)
    hashes[filename.strip()] = expected_hash


def calculate_sha256(filepath):
    digest = sha256()

    with open(filepath, "rb") as file:
        for block in iter(lambda: file.read(1024 * 1024), b""):
            digest.update(block)

    return digest.hexdigest()


for split in ["train", "validation", "test"]:
    filename = f"data/{split}.csv"
    destination = ROOT / filename

    print(f"\nProcessing: {filename}")

    if not destination.exists():
        source = hf_hub_download(
            repo_id=DATASET_REPO,
            repo_type="dataset",
            filename=filename,
            revision=REVISION,
        )

        if calculate_sha256(source) != hashes[filename]:
            raise RuntimeError(f"Hash mismatch: {filename}")

        shutil.copyfile(source, destination)
        print("Downloaded successfully")

    actual_hash = calculate_sha256(destination)
    expected_hash = hashes[filename]

    if actual_hash == expected_hash:
        print("SHA256: OK")
    else:
        raise RuntimeError(
            f"SHA256 mismatch for {filename}"
        )

print("\nAll datasets verified successfully!")

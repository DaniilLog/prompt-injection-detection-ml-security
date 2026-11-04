
import argparse
import csv
import hashlib
import json
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent


class DataGateError(ValueError):
    """Ошибка проверки качества данных."""


def resolve_path(value):
    path = Path(value)
    return path if path.is_absolute() else ROOT / path


def calculate_sha256(path):
    digest = hashlib.sha256()

    with path.open("rb") as file:
        for chunk in iter(
            lambda: file.read(1024 * 1024), b""
        ):
            digest.update(chunk)

    return digest.hexdigest()


def check_data(data_path):
    policy_path = ROOT / "ci" / "data_policy.json"
    manifest_path = ROOT / "ci" / "fixture_manifest.json"

    policy = json.loads(
        policy_path.read_text(encoding="utf-8")
    )

    manifest = json.loads(
        manifest_path.read_text(encoding="utf-8")
    )

    if policy["enforce_sha256"] is not True:
        raise DataGateError("SHA256 verification is required")

    if not data_path.is_file():
        raise DataGateError("Dataset file not found")

    if (
        data_path.stat().st_size
        > policy["maximum_file_size_bytes"]
    ):
        raise DataGateError("Dataset exceeds file size limit")

    counts = Counter()
    seen_texts = set()
    total = 0

    # Проверяем данные построчно, не загружая весь CSV в память.
    with data_path.open(
        "r", encoding="utf-8", newline=""
    ) as file:

        reader = csv.reader(file, strict=True)
        columns = next(reader, None)

        if columns != policy["required_columns"]:
            raise DataGateError(
                f"Invalid schema: {columns}"
            )

        for row in reader:
            total += 1

            if len(row) != 2:
                raise DataGateError(
                    f"Invalid row structure: {total}"
                )

            text, label = row

            if not text.strip():
                raise DataGateError(
                    f"Empty text at row {total}"
                )

            if "\x00" in text:
                raise DataGateError(
                    f"Null byte at row {total}"
                )

            if len(text) > policy["maximum_text_length"]:
                raise DataGateError(
                    f"Text too long at row {total}"
                )

            if label not in {"0", "1"}:
                raise DataGateError(
                    f"Invalid label at row {total}"
                )

            if policy["require_unique_text"]:
                if text in seen_texts:
                    raise DataGateError(
                        f"Duplicate text at row {total}"
                    )

                seen_texts.add(text)

            counts[int(label)] += 1

    # Проверка объема данных
    if not (
        policy["minimum_rows"]
        <= total
        <= policy["maximum_rows"]
    ):
        raise DataGateError(
            f"Invalid dataset size: {total}"
        )

    # Проверка распределения классов
    for label in policy["allowed_labels"]:
        count = counts[label]

        if not (
            policy["minimum_per_class"]
            <= count
            <= policy["maximum_per_class"]
        ):
            raise DataGateError(
                f"Invalid distribution for class {label}: {count}"
            )

    # Контроль целостности выполняется после проверки схемы.
    actual_hash = calculate_sha256(data_path)
    expected_hash = manifest["fixture_sha256"]

    if actual_hash != expected_hash:
        raise DataGateError("Dataset SHA256 mismatch")

    if total != manifest["sample_size"]:
        raise DataGateError("Manifest sample size mismatch")

    return {
        "status": "passed",
        "total_rows": total,
        "class_distribution": {
            str(k): counts[k] for k in sorted(counts)
        },
        "sha256": actual_hash,
        "schema": columns,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--data",
        default="ci/fixtures/validation_200.csv"
    )

    parser.add_argument(
        "--output",
        default="metrics/data_gate_result.json"
    )

    args = parser.parse_args()

    data_path = resolve_path(args.data)
    output_path = resolve_path(args.output)

    try:
        result = check_data(data_path)
    except (
        DataGateError,
        OSError,
        ValueError,
        UnicodeError,
        csv.Error,
        KeyError,
        TypeError,
    ) as error:
        result = {
            "status": "failed",
            "reason": str(error),
        }

    output_path.parent.mkdir(
        parents=True, exist_ok=True
    )

    output_path.write_text(
        json.dumps(
            result,
            indent=4,
            ensure_ascii=False
        ),
        encoding="utf-8"
    )

    print("\nDATA QUALITY GATE")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["status"] == "passed":
        print("\nDATA GATE: PASSED")
        return 0

    print("\nDATA GATE: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

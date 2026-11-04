
import argparse
import json
import math
from hashlib import sha256
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

BASELINE = ROOT / "ci" / "baseline.json"
POLICY = ROOT / "ci" / "model_policy.json"
MANIFEST = ROOT / "ci" / "fixture_manifest.json"
FIXTURE = ROOT / "ci" / "fixtures" / "validation_200.csv"


class GateError(ValueError):
    """Ошибка проверки качества модели."""


def read_json(path):
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, UnicodeError, json.JSONDecodeError) as exc:
        raise GateError(f"Cannot read {path}: {exc}") from exc

    if not isinstance(data, dict):
        raise GateError(f"Invalid JSON structure: {path}")

    return data


def get_field(data, name):
    if name not in data:
        raise GateError(f"Missing field: {name}")

    return data[name]


def get_score(data, name):
    value = get_field(data, "metric_value")

    if (
        isinstance(value, bool)
        or not isinstance(value, (int, float))
        or not math.isfinite(value)
        or not 0 <= value <= 1
    ):
        raise GateError(f"Invalid metric value in {name}")

    return float(value)


def get_integer(data, name):
    value = get_field(data, name)

    if isinstance(value, bool) or not isinstance(value, int):
        raise GateError(f"Invalid integer field: {name}")

    return value


def calculate_sha256(path):
    digest = sha256()

    try:
        with path.open("rb") as file:
            for chunk in iter(
                lambda: file.read(1024 * 1024), b""
            ):
                digest.update(chunk)
    except OSError as exc:
        raise GateError(f"Cannot read artifact: {path}") from exc

    return digest.hexdigest()


def check_gate(candidate_path, allow_simulation=False):
    baseline = read_json(BASELINE)
    policy = read_json(POLICY)
    manifest = read_json(MANIFEST)
    candidate = read_json(candidate_path)

    # Проверка происхождения результата
    evaluation = get_field(candidate, "evaluation")

    if evaluation != "real_model_evaluation" and not (
        allow_simulation
        and evaluation == "simulated_gate_test"
    ):
        raise GateError("Untrusted evaluation type")

    # Проверка названия метрики и класса
    metric_name = get_field(policy, "primary_metric")
    positive_class = get_field(policy, "positive_class")

    for name, data in [
        ("baseline", baseline),
        ("candidate", candidate),
    ]:
        if get_field(data, "metric") != metric_name:
            raise GateError(f"{name}: metric mismatch")

        if get_field(data, "positive_class") != positive_class:
            raise GateError(f"{name}: positive class mismatch")

    # Проверка версии и целостности данных
    fixture_hash = calculate_sha256(FIXTURE)
    expected_hash = get_field(manifest, "fixture_sha256")

    if fixture_hash != expected_hash:
        raise GateError("Fixture SHA256 mismatch")

    if get_field(policy, "require_matching_fixture_sha256") is not True:
        raise GateError("Fixture verification is not enabled")

    for name, data in [
        ("baseline", baseline),
        ("candidate", candidate),
    ]:
        if get_field(data, "fixture_sha256") != fixture_hash:
            raise GateError(f"{name}: data version mismatch")

    if (
        get_field(candidate, "source_revision")
        != get_field(manifest, "source_revision")
    ):
        raise GateError("Source revision mismatch")

    # Проверка количества объектов
    minimum = get_integer(policy, "minimum_samples")
    baseline_size = get_integer(baseline, "sample_size")
    candidate_size = get_integer(candidate, "sample_size")

    if (
        minimum <= 0
        or candidate_size < minimum
        or candidate_size != baseline_size
    ):
        raise GateError("Invalid evaluation sample size")

    # Для реальной оценки проверяем и файл модели
    if evaluation == "real_model_evaluation":
        model_path = (
            ROOT / "models" / "baseline_tfidf_logreg.joblib"
        )

        if (
            calculate_sha256(model_path)
            != get_field(candidate, "model_sha256")
        ):
            raise GateError("Candidate model SHA256 mismatch")

    # Проверка порога
    degradation = get_field(
        policy, "max_relative_degradation"
    )

    if (
        isinstance(degradation, bool)
        or not isinstance(degradation, (int, float))
        or not math.isfinite(degradation)
        or not 0 <= degradation < 1
    ):
        raise GateError("Invalid degradation policy")

    baseline_f1 = get_score(baseline, "baseline")
    candidate_f1 = get_score(candidate, "candidate")

    threshold = baseline_f1 * (1 - degradation)

    if baseline_f1 == 0:
        raise GateError("Zero baseline requires absolute threshold")

    passed = candidate_f1 >= threshold

    return {
        "status": "passed" if passed else "failed",
        "metric": metric_name,
        "baseline": baseline_f1,
        "candidate": candidate_f1,
        "threshold": threshold,
        "max_relative_degradation": degradation,
        "fixture_sha256": fixture_hash,
        "evaluation": evaluation,
    }


def main():
    parser = argparse.ArgumentParser()

    parser.add_argument(
        "--candidate",
        type=Path,
        default=ROOT / "metrics" / "ci_candidate.json",
    )

    parser.add_argument(
        "--output",
        type=Path,
        default=ROOT / "metrics" / "model_gate_result.json",
    )

    parser.add_argument(
        "--allow-simulation",
        action="store_true",
        help="For local gate demonstrations only",
    )

    args = parser.parse_args()

    try:
        result = check_gate(
            args.candidate,
            allow_simulation=args.allow_simulation,
        )
    except GateError as exc:
        result = {
            "status": "failed",
            "reason": str(exc),
        }

    args.output.parent.mkdir(parents=True, exist_ok=True)

    args.output.write_text(
        json.dumps(result, indent=4, ensure_ascii=False),
        encoding="utf-8",
    )

    print("\nMODEL QUALITY GATE")
    print(json.dumps(result, indent=4, ensure_ascii=False))

    if result["status"] == "passed":
        print("\nMODEL GATE: PASSED")
        return 0

    print("\nMODEL GATE: FAILED")
    return 1


if __name__ == "__main__":
    raise SystemExit(main())

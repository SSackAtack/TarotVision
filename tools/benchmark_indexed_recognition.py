"""Offline benchmark for IndexedImageMatcher.

The ``--index`` argument accepts either a path to ``index_manifest.json`` or a
path to a ``recognition_index`` directory containing ``index_manifest.json`` and
the referenced ``features.npz`` file.
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any, Callable


PROJECT_ROOT = Path(__file__).resolve().parents[1]
SRC_DIR = PROJECT_ROOT / "src"
if str(SRC_DIR) not in sys.path:
    sys.path.append(str(SRC_DIR))


SUMMARY_TEMPLATE = {
    "total_cases": 0,
    "processed_cases": 0,
    "error_cases": 0,
    "top1_correct": 0,
    "top1_accuracy": 0.0,
    "top3_correct": 0,
    "top3_accuracy": 0.0,
    "false_reject_count": 0,
    "false_reject_rate": 0.0,
    "recognized_count": 0,
    "ambiguous_count": 0,
    "unrecognized_count": 0,
    "min_correct_top1_score": None,
    "avg_correct_top1_score": None,
    "min_correct_margin": None,
    "avg_correct_margin": None,
}


def _empty_case_record(case: dict[str, Any]) -> dict[str, Any]:
    return {
        "crop_path": case.get("crop_path"),
        "expected_reference_id": case.get("expected_reference_id"),
        "expected_rotation": case.get("expected_rotation"),
        "matcher_method": None,
        "top1_reference_id": None,
        "top1_score": None,
        "top1_rotation": None,
        "top2_reference_id": None,
        "top2_score": None,
        "top3_reference_id": None,
        "top3_score": None,
        "score_margin_top1_top2": None,
        "is_top1_correct": False,
        "is_top3_correct": False,
        "is_rotation_correct": None,
        "recognition_decision": None,
        "decision_thresholds": None,
        "score_breakdown_top1": None,
        "error": None,
    }


def _candidate(candidates: list[dict[str, Any]], index: int) -> dict[str, Any] | None:
    if len(candidates) <= index:
        return None
    return candidates[index] or {}


def evaluate_match_case(case: dict[str, Any], match_result: dict[str, Any]) -> dict[str, Any]:
    """Build one per-case report record from a matcher result."""
    record = _empty_case_record(case)
    candidates = list(match_result.get("candidates") or [])

    top1 = _candidate(candidates, 0)
    top2 = _candidate(candidates, 1)
    top3 = _candidate(candidates, 2)

    expected_reference_id = case.get("expected_reference_id")
    expected_rotation = case.get("expected_rotation")

    top1_reference_id = top1.get("reference_id") if top1 else None
    top1_score = top1.get("score") if top1 else None
    top1_rotation = top1.get("rotation") if top1 else None
    top2_reference_id = top2.get("reference_id") if top2 else None
    top2_score = top2.get("score") if top2 else None

    top3_refs = [candidate.get("reference_id") for candidate in candidates[:3]]
    is_top1_correct = bool(expected_reference_id and top1_reference_id == expected_reference_id)
    is_top3_correct = bool(expected_reference_id and expected_reference_id in top3_refs)
    is_rotation_correct = None
    if expected_rotation is not None and top1_rotation is not None:
        is_rotation_correct = top1_rotation == expected_rotation

    score_margin = None
    if top1_score is not None and top2_score is not None:
        score_margin = round(float(top1_score) - float(top2_score), 4)

    record.update({
        "matcher_method": match_result.get("method"),
        "top1_reference_id": top1_reference_id,
        "top1_score": top1_score,
        "top1_rotation": top1_rotation,
        "top2_reference_id": top2_reference_id,
        "top2_score": top2_score,
        "top3_reference_id": top3.get("reference_id") if top3 else None,
        "top3_score": top3.get("score") if top3 else None,
        "score_margin_top1_top2": score_margin,
        "is_top1_correct": is_top1_correct,
        "is_top3_correct": is_top3_correct,
        "is_rotation_correct": is_rotation_correct,
        "recognition_decision": match_result.get("recognition_decision"),
        "decision_thresholds": match_result.get("decision_thresholds"),
        "score_breakdown_top1": top1.get("score_breakdown") if top1 else None,
    })
    return record


def build_summary(case_records: list[dict[str, Any]]) -> dict[str, Any]:
    summary = dict(SUMMARY_TEMPLATE)
    summary["total_cases"] = len(case_records)

    processed = [record for record in case_records if not record.get("error")]
    errors = [record for record in case_records if record.get("error")]
    summary["processed_cases"] = len(processed)
    summary["error_cases"] = len(errors)

    summary["top1_correct"] = sum(1 for record in processed if record["is_top1_correct"])
    summary["top3_correct"] = sum(1 for record in processed if record["is_top3_correct"])

    decisions = [record.get("recognition_decision") for record in processed]
    summary["recognized_count"] = decisions.count("recognized")
    summary["ambiguous_count"] = decisions.count("ambiguous")
    summary["unrecognized_count"] = decisions.count("unrecognized")

    false_rejects = [
        record for record in processed
        if record["is_top1_correct"] and record.get("recognition_decision") == "unrecognized"
    ]
    summary["false_reject_count"] = len(false_rejects)

    if processed:
        summary["top1_accuracy"] = round(summary["top1_correct"] / len(processed), 4)
        summary["top3_accuracy"] = round(summary["top3_correct"] / len(processed), 4)
        summary["false_reject_rate"] = round(summary["false_reject_count"] / len(processed), 4)

    correct_top1 = [record for record in processed if record["is_top1_correct"]]
    correct_scores = [
        float(record["top1_score"]) for record in correct_top1
        if record.get("top1_score") is not None
    ]
    correct_margins = [
        float(record["score_margin_top1_top2"]) for record in correct_top1
        if record.get("score_margin_top1_top2") is not None
    ]

    if correct_scores:
        summary["min_correct_top1_score"] = round(min(correct_scores), 4)
        summary["avg_correct_top1_score"] = round(sum(correct_scores) / len(correct_scores), 4)
    if correct_margins:
        summary["min_correct_margin"] = round(min(correct_margins), 4)
        summary["avg_correct_margin"] = round(sum(correct_margins) / len(correct_margins), 4)

    return summary


def benchmark_cases(
    cases: list[dict[str, Any]],
    matcher: Any,
    image_loader: Callable[[str], Any],
) -> dict[str, Any]:
    records = []
    for case in cases:
        record = _empty_case_record(case)
        crop_path = case.get("crop_path")
        if not crop_path:
            record["error"] = "missing crop_path"
            records.append(record)
            continue

        image = image_loader(crop_path)
        if image is None:
            record["error"] = f"cannot read crop: {crop_path}"
            records.append(record)
            continue

        try:
            match_result = matcher.match_card(image)
            record = evaluate_match_case(case, match_result)
        except Exception as exc:  # pragma: no cover - defensive for CLI robustness
            record["error"] = f"matcher failed: {exc}"
        records.append(record)

    return {
        "summary": build_summary(records),
        "cases": records,
    }


def load_cases(cases_path: str) -> list[dict[str, Any]]:
    with open(cases_path, "r", encoding="utf-8") as handle:
        data = json.load(handle)
    if not isinstance(data, list):
        raise ValueError("benchmark cases JSON must be a list")
    return data


def load_index_from_path(index_path: str) -> dict[str, Any]:
    import numpy as np

    path = Path(index_path)
    manifest_path = path / "index_manifest.json" if path.is_dir() else path
    index_dir = manifest_path.parent

    with open(manifest_path, "r", encoding="utf-8") as handle:
        manifest = json.load(handle)

    features_file = manifest.get("features_file", "features.npz")
    features_path = index_dir / features_file
    with np.load(features_path, allow_pickle=True) as data:
        features = {
            "reference_ids": data["reference_ids"].tolist(),
            "deck_ids": data["deck_ids"].tolist(),
            "gray_fingerprints": data["gray_fingerprints"],
            "dhashes": data["dhashes"],
            "gray_histograms": data["gray_histograms"],
            "color_histograms": data["color_histograms"],
            "region_fingerprints": data["region_fingerprints"],
        }
    return {"manifest": manifest, "features": features}


def cv2_image_loader(crop_path: str) -> Any:
    import cv2

    path = Path(crop_path)
    if not path.exists():
        return None
    return cv2.imread(str(path))


def write_report(report: dict[str, Any], output_path: str) -> None:
    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    with open(path, "w", encoding="utf-8") as handle:
        json.dump(report, handle, indent=2, ensure_ascii=False)


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Benchmark IndexedImageMatcher on saved crop images.",
    )
    parser.add_argument(
        "--index",
        required=True,
        help="Path to index_manifest.json or a recognition_index directory.",
    )
    parser.add_argument(
        "--cases",
        required=True,
        help="Path to benchmark_cases.json.",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Path where indexed_recognition_report.json should be written.",
    )
    return parser.parse_args()


def main() -> int:
    args = parse_args()

    from tarotvision.recognition.indexed_matcher import IndexedImageMatcher

    index = load_index_from_path(args.index)
    matcher = IndexedImageMatcher(index)
    cases = load_cases(args.cases)
    report = benchmark_cases(cases, matcher, cv2_image_loader)
    write_report(report, args.output)
    print(f"Wrote benchmark report: {args.output}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

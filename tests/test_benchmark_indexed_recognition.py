import tempfile
import unittest
from pathlib import Path

from tools.benchmark_indexed_recognition import benchmark_cases


class FakeMatcher:
    def __init__(self, results):
        self.results = list(results)

    def match_card(self, crop_image):
        if not self.results:
            return {"method": "fake", "candidates": []}
        return self.results.pop(0)


def fake_image_loader(path):
    if Path(path).exists():
        return object()
    return None


class BenchmarkIndexedRecognitionTest(unittest.TestCase):
    def test_top1_correct_increments_top1_correct(self):
        cases = [{
            "crop_path": __file__,
            "expected_reference_id": "Card_A",
            "expected_rotation": 0,
        }]
        matcher = FakeMatcher([{
            "method": "fake_matcher",
            "recognition_decision": "recognized",
            "decision_thresholds": {"min_recognition_score": 0.82},
            "candidates": [
                {"reference_id": "Card_A", "score": 0.91, "rotation": 0, "score_breakdown": {"gray": 0.9}},
                {"reference_id": "Card_B", "score": 0.71, "rotation": 0},
            ],
        }])

        report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertEqual(report["summary"]["top1_correct"], 1)
        self.assertEqual(report["summary"]["top1_accuracy"], 1.0)
        self.assertTrue(report["cases"][0]["is_top1_correct"])
        self.assertTrue(report["cases"][0]["is_rotation_correct"])

    def test_top3_correct_increments_top3_correct(self):
        cases = [{"crop_path": __file__, "expected_reference_id": "Card_C"}]
        matcher = FakeMatcher([{
            "method": "fake_matcher",
            "recognition_decision": "ambiguous",
            "candidates": [
                {"reference_id": "Card_A", "score": 0.91, "rotation": 0},
                {"reference_id": "Card_B", "score": 0.81, "rotation": 0},
                {"reference_id": "Card_C", "score": 0.71, "rotation": 0},
            ],
        }])

        report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertEqual(report["summary"]["top1_correct"], 0)
        self.assertEqual(report["summary"]["top3_correct"], 1)
        self.assertFalse(report["cases"][0]["is_top1_correct"])
        self.assertTrue(report["cases"][0]["is_top3_correct"])

    def test_false_reject_when_top1_correct_but_unrecognized(self):
        cases = [{"crop_path": __file__, "expected_reference_id": "Card_A"}]
        matcher = FakeMatcher([{
            "method": "fake_matcher",
            "recognition_decision": "unrecognized",
            "candidates": [
                {"reference_id": "Card_A", "score": 0.77, "rotation": 0},
                {"reference_id": "Card_B", "score": 0.72, "rotation": 0},
            ],
        }])

        report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertEqual(report["summary"]["false_reject_count"], 1)
        self.assertEqual(report["summary"]["false_reject_rate"], 1.0)

    def test_missing_crop_does_not_abort_benchmark(self):
        cases = [
            {"crop_path": "missing_crop.png", "expected_reference_id": "Card_A"},
            {"crop_path": __file__, "expected_reference_id": "Card_B"},
        ]
        matcher = FakeMatcher([{
            "method": "fake_matcher",
            "recognition_decision": "recognized",
            "candidates": [{"reference_id": "Card_B", "score": 0.9, "rotation": 0}],
        }])

        report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertEqual(report["summary"]["total_cases"], 2)
        self.assertEqual(report["summary"]["processed_cases"], 1)
        self.assertEqual(report["summary"]["error_cases"], 1)
        self.assertIsNotNone(report["cases"][0]["error"])
        self.assertEqual(report["cases"][1]["top1_reference_id"], "Card_B")

    def test_empty_candidates_do_not_raise(self):
        cases = [{"crop_path": __file__, "expected_reference_id": "Card_A"}]
        matcher = FakeMatcher([{
            "method": "fake_matcher",
            "recognition_decision": "unrecognized",
            "decision_thresholds": {"min_recognition_score": 0.82},
            "candidates": [],
        }])

        report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertEqual(report["summary"]["processed_cases"], 1)
        self.assertIsNone(report["cases"][0]["top1_reference_id"])
        self.assertFalse(report["cases"][0]["is_top1_correct"])

    def test_report_contains_summary_and_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            crop_path = Path(tmp_dir) / "crop.png"
            crop_path.write_bytes(b"not-used-by-fake-loader")
            cases = [{"crop_path": str(crop_path), "expected_reference_id": "Card_A"}]
            matcher = FakeMatcher([{
                "method": "fake_matcher",
                "recognition_decision": "recognized",
                "candidates": [{"reference_id": "Card_A", "score": 0.9, "rotation": 0}],
            }])

            report = benchmark_cases(cases, matcher, fake_image_loader)

        self.assertIn("summary", report)
        self.assertIn("cases", report)
        self.assertEqual(len(report["cases"]), 1)


if __name__ == "__main__":
    unittest.main()

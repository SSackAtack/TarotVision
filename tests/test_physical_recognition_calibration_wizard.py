import json
import tempfile
import unittest
from io import StringIO
from pathlib import Path
from unittest.mock import patch

from tools.physical_recognition_calibration_wizard import (
    CalibrationCaptureResult,
    ExistingVisionCapturePipeline,
    PhysicalRecognitionWizard,
    TargetPreflightRunner,
    assess_empty_baseline,
    build_session_dir,
    crop_quality_check,
    expand_plan_cases,
    print_final_result,
    list_references,
    load_plan,
    main,
    write_benchmark_cases,
    write_run_manifest,
)


class FakeCapturePipeline:
    def __init__(self, results):
        self.results = list(results)
        self.captured = []

    def open(self):
        return True

    def close(self):
        pass

    def capture_case(self, case, session_dir, manual_confirm=False, input_func=input, print_func=print):
        self.captured.append({
            "case": case,
            "manual_confirm": manual_confirm,
        })
        result = self.results.pop(0)
        if isinstance(result, Exception):
            raise result
        return result


class FakeBenchmarkRunner:
    def __init__(self):
        self.calls = []

    def __call__(self, index_path, cases_path, output_path):
        self.calls.append((index_path, cases_path, output_path))
        report = {"summary": {"total_cases": 1}, "cases": []}
        Path(output_path).write_text(json.dumps(report), encoding="utf-8")
        return report


class FakeTargetPreflightRunner:
    def __init__(self, reports):
        self.reports = list(reports)
        self.calls = []

    def run(self, session_dir, input_func=input, print_func=print):
        self.calls.append(session_dir)
        report = self.reports.pop(0)
        preflight_dir = Path(session_dir) / "target_preflight"
        preflight_dir.mkdir(parents=True, exist_ok=True)
        (preflight_dir / "target_preflight_report.json").write_text(json.dumps(report), encoding="utf-8")
        return report


class FakeDiffDetector:
    def __init__(self, roi_results):
        self.roi_results = list(roi_results)
        self.calls = 0

    def detect_change_roi_with_debug(self, current_frame, reference_frame):
        self.calls += 1
        roi_rect = self.roi_results.pop(0)
        debug = {
            "accepted": roi_rect is not None,
            "contours_count": 1 if roi_rect is not None else 0,
        }
        return roi_rect, f"mask-{self.calls}", debug


class FakeCamera:
    def __init__(self, frames):
        self.frames = list(frames)
        self.calls = 0

    def get_frame(self):
        self.calls += 1
        return True, self.frames.pop(0)


class IdentityPerspectiveCorrector:
    def get_warped_table(self, frame, crop_to_markers=True):
        return frame, None


class PhysicalRecognitionCalibrationWizardTest(unittest.TestCase):
    def _write_index_manifest(self, tmp_dir, reference_count=5):
        path = Path(tmp_dir) / "index_manifest.json"
        path.write_text(
            json.dumps({
                "references": [
                    {"reference_id": f"Card_{idx:02d}", "display_name": f"Card {idx:02d}"}
                    for idx in range(reference_count)
                ]
            }),
            encoding="utf-8",
        )
        return path

    def test_plan_5_cards_times_rotations_generates_10_cases(self):
        plan = [
            {"display_name": f"Card {idx}", "expected_reference_id": f"Card_{idx}"}
            for idx in range(5)
        ]

        cases = expand_plan_cases(plan, rotations=[0, 180], samples_per_pose=1)

        self.assertEqual(len(cases), 10)
        self.assertEqual(cases[0]["expected_reference_id"], "Card_0")
        self.assertEqual(cases[1]["expected_rotation"], 180)
        self.assertEqual(cases[-1]["sequence_number"], 10)

    def test_wizard_creates_benchmark_cases_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(
                    status="completed",
                    crop_path=str(session_dir / "crops" / "001_RWS_00_Fool_rot0.png"),
                    snapshot_paths=[],
                )
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                samples_per_pose=1,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            cases_path = session_dir / "benchmark_cases.json"
            self.assertTrue(cases_path.exists())
            cases = json.loads(cases_path.read_text(encoding="utf-8"))
            self.assertEqual(cases[0]["expected_reference_id"], "RWS_00_Fool")
            self.assertEqual(cases[0]["expected_rotation"], 0)

    def test_wizard_creates_run_manifest_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "001.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                samples_per_pose=1,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["total_expected_cases"], 1)
            self.assertEqual(manifest["completed_cases"], 1)
            self.assertEqual(manifest["failed_cases"], 0)

    def test_one_case_error_does_not_stop_plan(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([
                    {"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"},
                    {"display_name": "Magician", "expected_reference_id": "RWS_01_Magician"},
                ]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                RuntimeError("crop failed"),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "002.png")),
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                samples_per_pose=1,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "s",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))
            self.assertEqual(manifest["completed_cases"], 1)
            self.assertEqual(manifest["failed_cases"], 1)
            self.assertEqual(len(pipeline.captured), 2)

    def test_manual_confirm_mode_passes_through_cases_with_fake_input(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "001.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                samples_per_pose=1,
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertTrue(pipeline.captured[0]["manual_confirm"])

    def test_benchmark_logic_is_called_after_capture(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            benchmark_runner = FakeBenchmarkRunner()
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "001.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                samples_per_pose=1,
                pipeline=pipeline,
                benchmark_runner=benchmark_runner,
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertEqual(len(benchmark_runner.calls), 1)
            self.assertEqual(benchmark_runner.calls[0][1], str(session_dir / "benchmark_cases.json"))
            self.assertEqual(benchmark_runner.calls[0][2], str(session_dir / "indexed_recognition_report.json"))

    def test_helper_functions_write_expected_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )

            plan = load_plan(str(plan_path))
            session_dir = build_session_dir(tmp_dir, timestamp="2026-06-10_1830")
            cases_path = write_benchmark_cases(
                session_dir,
                [{"crop_path": "crop.png", "expected_reference_id": "RWS_00_Fool", "expected_rotation": 0}],
            )
            manifest_path = write_run_manifest(session_dir, {"completed_cases": 1})

            self.assertEqual(plan[0]["display_name"], "Fool")
            self.assertTrue(cases_path.exists())
            self.assertTrue(manifest_path.exists())

    def test_wizard_runs_without_plan_when_quick_count_is_provided(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = self._write_index_manifest(tmp_dir, reference_count=5)
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / f"{idx:03d}.png"))
                for idx in range(10)
            ])

            wizard = PhysicalRecognitionWizard(
                index_path=str(index_path),
                plan_path=None,
                output_dir=tmp_dir,
                quick_count=5,
                rotations=[0, 180],
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertEqual(len(pipeline.captured), 10)

    def test_quick_count_5_generates_10_cases_for_default_rotations(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = self._write_index_manifest(tmp_dir, reference_count=5)
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / f"{idx:03d}.png"))
                for idx in range(10)
            ])

            wizard = PhysicalRecognitionWizard(
                index_path=str(index_path),
                plan_path=None,
                output_dir=tmp_dir,
                quick_count=5,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            cases = json.loads((session_dir / "benchmark_cases.json").read_text(encoding="utf-8"))

            self.assertEqual(len(cases), 10)
            self.assertEqual(cases[0]["expected_reference_id"], "Card_00")
            self.assertEqual(cases[1]["expected_rotation"], 180)

    def test_run_manifest_records_auto_quick_count_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = self._write_index_manifest(tmp_dir, reference_count=5)
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / f"{idx:03d}.png"))
                for idx in range(10)
            ])

            wizard = PhysicalRecognitionWizard(
                index_path=str(index_path),
                plan_path=None,
                output_dir=tmp_dir,
                quick_count=5,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["plan_source"], "auto_quick_count")
            self.assertEqual(manifest["quick_count"], 5)
            self.assertIsNone(manifest["plan_path"])

    def test_plan_file_still_works_and_records_file_source(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "001.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["plan_source"], "file")
            self.assertIsNone(manifest["quick_count"])
            self.assertEqual(manifest["plan_path"], str(plan_path))

    def test_interactive_mode_can_generate_quick_3_card_plan(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = self._write_index_manifest(tmp_dir, reference_count=5)
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / f"{idx:03d}.png"))
                for idx in range(6)
            ])

            wizard = PhysicalRecognitionWizard(
                index_path=str(index_path),
                plan_path=None,
                output_dir=tmp_dir,
                quick_count=None,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "1",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(len(pipeline.captured), 6)
            self.assertEqual(manifest["plan_source"], "interactive")
            self.assertEqual(manifest["quick_count"], 3)

    def test_list_references_prints_reference_ids_without_physical_capture(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            index_path = self._write_index_manifest(tmp_dir, reference_count=3)
            printed = []

            refs = list_references(str(index_path), print_func=printed.append)

            self.assertEqual(refs, ["Card_00", "Card_01", "Card_02"])
            self.assertEqual(printed, ["Card_00", "Card_01", "Card_02"])

    def test_accepted_crop_goes_to_benchmark_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt1.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "a",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            cases = json.loads((session_dir / "benchmark_cases.json").read_text(encoding="utf-8"))

            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["crop_path"], str(session_dir / "crops" / "attempt1.png"))

    def test_retaken_crop_does_not_go_to_benchmark_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt1.png")),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt2.png")),
            ])
            decisions = iter(["r", "a"])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": next(decisions),
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            cases = json.loads((session_dir / "benchmark_cases.json").read_text(encoding="utf-8"))

            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["crop_path"], str(session_dir / "crops" / "attempt2.png"))

    def test_after_retake_wizard_repeats_same_case(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt1.png")),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt2.png")),
            ])
            decisions = iter(["r", "a"])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": next(decisions),
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertEqual(len(pipeline.captured), 2)
            self.assertEqual(pipeline.captured[0]["case"]["sequence_number"], pipeline.captured[1]["case"]["sequence_number"])

    def test_skipped_case_does_not_go_to_benchmark_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt1.png"))
            ])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": "s",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            cases = json.loads((session_dir / "benchmark_cases.json").read_text(encoding="utf-8"))

            self.assertEqual(cases, [])

    def test_manifest_counts_accepted_retaken_and_skipped_cases(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([
                    {"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"},
                    {"display_name": "Magician", "expected_reference_id": "RWS_01_Magician"},
                ]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt1.png")),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt2.png")),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "attempt3.png")),
            ])
            decisions = iter(["r", "a", "s"])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=FakeBenchmarkRunner(),
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": next(decisions),
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            manifest = json.loads((session_dir / "run_manifest.json").read_text(encoding="utf-8"))

            self.assertEqual(manifest["accepted_cases"], 1)
            self.assertEqual(manifest["retaken_cases"], 1)
            self.assertEqual(manifest["skipped_cases"], 1)
            self.assertEqual(len(manifest["case_events"]), 3)

    def test_crop_quality_check_detects_nearly_uniform_image(self):
        uniform_crop = [[[120, 120, 120] for _ in range(32)] for _ in range(32)]

        quality = crop_quality_check(uniform_crop)

        self.assertFalse(quality["is_valid"])
        self.assertIn("empty_or_uniform_crop", quality["reasons"])
        self.assertIn("low_content_density", quality["reasons"])

    def test_crop_quality_check_returns_metrics_and_reasons(self):
        uniform_crop = [[[120, 120, 120] for _ in range(32)] for _ in range(32)]

        quality = crop_quality_check(uniform_crop)

        self.assertIn("metrics", quality)
        self.assertIn("reasons", quality)
        self.assertIn("brightness_mean", quality["metrics"])

    def test_baseline_guard_rejects_large_rectangular_object(self):
        frame = [[[70, 55, 40] for _ in range(120)] for _ in range(80)]
        for y in range(12, 68):
            for x in range(42, 78):
                frame[y][x] = [230, 230, 230]

        guard = assess_empty_baseline(frame)

        self.assertFalse(guard["is_valid"])
        self.assertIn("large_rectangular_object", guard["reasons"])

    def test_baseline_guard_rejects_detected_calibration_target(self):
        frame = [[[90, 70, 50] for _ in range(120)] for _ in range(80)]

        with patch.object(
            TargetPreflightRunner,
            "_extract_target_roi",
            return_value={
                "target_detected": True,
                "target_roi": [35, 18, 40, 58],
                "detection_method": "white_page_component",
            },
        ):
            guard = assess_empty_baseline(frame)

        self.assertFalse(guard["is_valid"])
        self.assertIn("calibration_target_present", guard["reasons"])
        self.assertEqual([35, 18, 40, 58], guard["metrics"]["target_roi"])

    def test_baseline_guard_passes_neutral_empty_image(self):
        frame = [[[70, 55, 40] for _ in range(120)] for _ in range(80)]

        guard = assess_empty_baseline(frame)

        self.assertTrue(guard["is_valid"])
        self.assertEqual([], guard["reasons"])

    def test_plain_accept_is_blocked_for_empty_or_low_content_crop(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output = StringIO()
            wizard = PhysicalRecognitionWizard(
                index_path=str(Path(tmp_dir) / "index_manifest.json"),
                plan_path=None,
                output_dir=tmp_dir,
                manual_confirm=True,
                input_func=lambda prompt="": "a",
                print_func=lambda *args, **kwargs: print(*args, **kwargs, file=output),
            )
            quality = {
                "is_valid": False,
                "reasons": ["low_content_density", "low_edge_density", "empty_or_uniform_crop"],
                "metrics": {},
            }

            decision = wizard._resolve_crop_decision(str(Path(tmp_dir) / "crop.png"), quality)

            self.assertEqual("retaken", decision)
            self.assertIn("Akceptacja A jest zablokowana", output.getvalue())

    def test_valid_crop_can_still_be_accepted(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            wizard = PhysicalRecognitionWizard(
                index_path=str(Path(tmp_dir) / "index_manifest.json"),
                plan_path=None,
                output_dir=tmp_dir,
                manual_confirm=True,
                input_func=lambda prompt="": "a",
                print_func=lambda *args, **kwargs: None,
            )
            quality = {"is_valid": True, "reasons": [], "metrics": {}}

            decision = wizard._resolve_crop_decision(str(Path(tmp_dir) / "crop.png"), quality)

            self.assertEqual("accepted", decision)

    def test_manual_card_step_retries_when_snapshot_still_looks_empty(self):
        pipeline = object.__new__(ExistingVisionCapturePipeline)
        pipeline.diff_detector = FakeDiffDetector([
            None,
            ((10.0, 20.0), (100.0, 180.0), 0.0),
        ])
        frames = iter(["empty-after-frame", "card-after-frame"])
        inputs = iter(["", "", ""])
        messages = []
        pipeline._read_warped_frame = lambda **_kwargs: next(frames)

        frame = pipeline._wait_for_card_snapshot(
            "baseline-frame",
            manual_confirm=True,
            input_func=lambda prompt="": next(inputs),
            print_func=lambda *args, **kwargs: messages.append(" ".join(str(arg) for arg in args)),
        )

        self.assertEqual("card-after-frame", frame)
        self.assertEqual(2, pipeline.diff_detector.calls)
        self.assertTrue(pipeline._last_after_guard["is_valid"])
        self.assertIn(
            "snapshot z kartą nadal wygląda jak pusty stół",
            "\n".join(messages),
        )

    def test_fresh_manual_snapshot_discards_buffered_camera_frames(self):
        pipeline = object.__new__(ExistingVisionCapturePipeline)
        pipeline.camera = FakeCamera(["stale-target-frame", "stale-empty-frame", "fresh-card-frame"])
        pipeline.corrector = IdentityPerspectiveCorrector()
        pipeline.fresh_frame_reads = 3

        frame = pipeline._read_warped_frame(fresh=True)

        self.assertEqual("fresh-card-frame", frame)
        self.assertEqual(3, pipeline.camera.calls)

    def test_benchmark_runs_only_on_accepted_crops(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([
                    {"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"},
                    {"display_name": "Magician", "expected_reference_id": "RWS_01_Magician"},
                ]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            benchmark_runner = FakeBenchmarkRunner()
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "accepted.png")),
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "skipped.png")),
            ])
            decisions = iter(["a", "s"])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                pipeline=pipeline,
                benchmark_runner=benchmark_runner,
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": next(decisions),
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()
            cases = json.loads(Path(benchmark_runner.calls[0][1]).read_text(encoding="utf-8"))

            self.assertEqual(len(cases), 1)
            self.assertEqual(cases[0]["crop_path"], str(session_dir / "crops" / "accepted.png"))

    def test_target_preflight_writes_report_json(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = FakeTargetPreflightRunner([{
                "quality_status": "good",
                "recommendation": "ok_to_continue",
            }])
            session_dir = Path(tmp_dir) / "session"

            report = runner.run(session_dir, input_func=lambda _prompt="": "", print_func=lambda *_args, **_kwargs: None)

            self.assertEqual(report["quality_status"], "good")
            self.assertTrue((session_dir / "target_preflight" / "target_preflight_report.json").exists())

    def test_target_preflight_only_does_not_run_recognition_benchmark(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            benchmark_runner = FakeBenchmarkRunner()
            runner = FakeTargetPreflightRunner([{
                "quality_status": "good",
                "recommendation": "ok_to_continue",
            }])
            wizard = PhysicalRecognitionWizard(
                index_path=None,
                plan_path=None,
                output_dir=tmp_dir,
                calibration_target_preflight=True,
                target_preflight_runner=runner,
                benchmark_runner=benchmark_runner,
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertEqual(benchmark_runner.calls, [])
            self.assertEqual(len(runner.calls), 1)

    def test_standalone_preflight_returns_report_path_without_benchmark_path(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            runner = FakeTargetPreflightRunner([{
                "quality_status": "good",
                "recommendation": "ok_to_continue",
            }])
            wizard = PhysicalRecognitionWizard(
                index_path=None,
                plan_path=None,
                output_dir=tmp_dir,
                calibration_target_preflight=True,
                target_preflight_runner=runner,
                benchmark_runner=FakeBenchmarkRunner(),
                input_func=lambda _prompt="": "",
                print_func=lambda *_args, **_kwargs: None,
            )

            result = wizard.run()

            self.assertIn("target_preflight_report_path", result)
            self.assertNotIn("benchmark_report_path", result)

    def test_final_output_for_standalone_preflight_does_not_require_benchmark_path(self):
        output = StringIO()

        print_final_result({
            "session_dir": "output/calibration_runs/session",
            "target_preflight_report_path": "output/calibration_runs/session/target_preflight/target_preflight_report.json",
        }, print_func=lambda text: print(text, file=output))

        text = output.getvalue()
        self.assertIn("Zakończono preflight targetu A4.", text)
        self.assertIn("Raport preflight:", text)
        self.assertNotIn("Raport benchmarku:", text)

    def test_main_standalone_preflight_final_output_has_no_keyerror(self):
        with patch(
            "tools.physical_recognition_calibration_wizard.PhysicalRecognitionWizard.run",
            return_value={
                "session_dir": "output/calibration_runs/session",
                "target_preflight_report_path": "output/calibration_runs/session/target_preflight/target_preflight_report.json",
            },
        ), patch(
            "sys.argv",
            ["physical_recognition_calibration_wizard.py", "--calibration-target-preflight", "--camera-index", "0"],
        ), patch("sys.stdout", new_callable=StringIO) as stdout:
            exit_code = main()

        self.assertEqual(exit_code, 0)
        self.assertIn("Zakończono preflight targetu A4.", stdout.getvalue())

    def test_target_not_detected_keeps_good_image_quality_when_metrics_are_good(self):
        runner = TargetPreflightRunner(camera_index=0)
        roi = [
            [[30, 30, 30] if (x + y) % 2 == 0 else [220, 220, 220] for x in range(32)]
            for y in range(32)
        ]

        report = runner.build_report(
            frame=roi,
            roi=roi,
            target_detected=False,
            target_roi=[0, 0, 32, 32],
            camera_properties={},
            target_detection_status="fallback_center_roi",
            detection_method="fallback_center_roi",
        )

        self.assertEqual(report["recommendation"], "target_not_detected")
        self.assertEqual(report["image_quality_status"], "good")
        self.assertEqual(report["target_detection_status"], "fallback_center_roi")
        self.assertEqual(report["overall_status"], "warning")

    def test_white_a4_page_on_dark_background_detects_white_page_contour(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[45, 45, 45] for _ in range(120)] for _ in range(160)]
        for y in range(18, 142):
            for x in range(16, 104):
                frame[y][x] = [235, 235, 235]

        detection = runner._extract_target_roi(frame)

        self.assertTrue(detection["target_detected"])
        self.assertEqual(detection["detection_method"], "white_page_component")
        self.assertTrue(detection["page_detection_candidates"])

    def test_white_a4_component_ignores_separate_bright_reflection(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[45, 45, 45] for _ in range(180)] for _ in range(220)]
        for y in range(30, 190):
            for x in range(35, 148):
                frame[y][x] = [235, 235, 235]
        for y in range(45, 170):
            for x in range(160, 178):
                frame[y][x] = [220, 220, 220]

        detection = runner._extract_target_roi(frame)

        self.assertTrue(detection["target_detected"])
        self.assertEqual(detection["detection_method"], "white_page_component")
        self.assertLess(detection["target_roi"][0] + detection["target_roi"][2], 160)

    def test_square_bright_area_is_rejected_as_a4_portrait(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[45, 45, 45] for _ in range(160)] for _ in range(160)]
        for y in range(40, 120):
            for x in range(40, 120):
                frame[y][x] = [235, 235, 235]

        detection = runner._extract_target_roi(frame)

        self.assertFalse(detection["target_detected"])
        self.assertEqual(detection["detection_method"], "fallback_center_roi")
        self.assertTrue(any(
            candidate["reject_reason"] == "bad_aspect_ratio"
            for candidate in detection["page_detection_candidates"]
        ))

    def test_off_center_a4_page_inside_tolerance_is_detected(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[45, 45, 45] for _ in range(180)] for _ in range(220)]
        for y in range(34, 194):
            for x in range(58, 171):
                frame[y][x] = [235, 235, 235]

        detection = runner._extract_target_roi(frame)

        self.assertTrue(detection["target_detected"])
        self.assertEqual(detection["detection_method"], "white_page_component")

    def test_black_target_frame_detection_is_used_when_white_page_is_missing(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[180, 180, 180] for _ in range(120)] for _ in range(160)]
        for y in range(24, 136):
            for x in range(34, 86):
                if y in range(24, 30) or y in range(130, 136) or x in range(34, 40) or x in range(80, 86):
                    frame[y][x] = [5, 5, 5]

        detection = runner._extract_target_roi(frame)

        self.assertTrue(detection["target_detected"])
        self.assertEqual(detection["detection_method"], "black_target_frame")

    def test_target_detection_falls_back_when_no_target_shape_exists(self):
        runner = TargetPreflightRunner(camera_index=0)
        frame = [[[80, 80, 80] for _ in range(120)] for _ in range(160)]

        detection = runner._extract_target_roi(frame)

        self.assertFalse(detection["target_detected"])
        self.assertEqual(detection["target_detection_status"], "fallback_center_roi")
        self.assertEqual(detection["detection_method"], "fallback_center_roi")

    def test_report_contains_detection_debug_path(self):
        runner = TargetPreflightRunner(camera_index=0)

        report = runner.build_report(
            frame=[[[80, 80, 80] for _ in range(16)] for _ in range(16)],
            roi=[[[80, 80, 80] for _ in range(16)] for _ in range(16)],
            target_detected=False,
            target_roi=[0, 0, 16, 16],
            camera_properties={},
            target_detection_status="fallback_center_roi",
            detection_method="fallback_center_roi",
            detection_debug_path="target_preflight_detection_debug.png",
            page_detection_candidates=[{"method": "white_page_component", "accepted": False}],
        )

        self.assertEqual(report["detection_debug_path"], "target_preflight_detection_debug.png")
        self.assertEqual(report["page_detection_candidates"][0]["method"], "white_page_component")

    def test_detection_debug_image_is_written_with_candidates(self):
        import numpy as np

        with tempfile.TemporaryDirectory() as tmp_dir:
            debug_path = Path(tmp_dir) / "target_preflight_detection_debug.png"
            frame = np.zeros((80, 120, 3), dtype=np.uint8)
            candidates = [{
                "method": "white_page_component",
                "x": 30,
                "y": 10,
                "width": 40,
                "height": 56,
                "accepted": True,
            }]

            TargetPreflightRunner._write_detection_debug(
                debug_path,
                frame,
                [30, 10, 40, 56],
                "detected",
                "white_page_component",
                candidates,
            )

            self.assertTrue(debug_path.exists())
            self.assertGreater(debug_path.stat().st_size, 0)

    def test_poor_blur_preflight_recommends_improve_focus(self):
        runner = TargetPreflightRunner(camera_index=0)

        report = runner.build_report(
            frame=[[[80, 80, 80] for _ in range(16)] for _ in range(16)],
            roi=[[[80, 80, 80] for _ in range(16)] for _ in range(16)],
            target_detected=True,
            target_roi=[0, 0, 16, 16],
            camera_properties={},
        )

        self.assertEqual(report["recommendation"], "improve_focus")
        self.assertEqual(report["quality_status"], "poor")
        self.assertEqual(report["image_quality_status"], "poor")

    def test_overexposed_preflight_recommends_reduce_glare_or_exposure(self):
        runner = TargetPreflightRunner(camera_index=0)

        report = runner.build_report(
            frame=[[[255, 255, 255] for _ in range(16)] for _ in range(16)],
            roi=[[[255, 255, 255] for _ in range(16)] for _ in range(16)],
            target_detected=True,
            target_roi=[0, 0, 16, 16],
            camera_properties={},
        )

        self.assertIn(report["recommendation"], ["reduce_glare", "reduce_exposure"])
        self.assertEqual(report["quality_status"], "poor")
        self.assertEqual(report["image_quality_status"], "poor")

    def test_preflight_target_before_card_test_allows_retry_and_continue(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            plan_path = Path(tmp_dir) / "plan.json"
            plan_path.write_text(
                json.dumps([{"display_name": "Fool", "expected_reference_id": "RWS_00_Fool"}]),
                encoding="utf-8",
            )
            session_dir = Path(tmp_dir) / "session"
            benchmark_runner = FakeBenchmarkRunner()
            preflight_runner = FakeTargetPreflightRunner([
                {"quality_status": "poor", "recommendation": "improve_focus"},
                {"quality_status": "good", "recommendation": "ok_to_continue"},
            ])
            pipeline = FakeCapturePipeline([
                CalibrationCaptureResult(status="completed", crop_path=str(session_dir / "crops" / "accepted.png")),
            ])
            answers = iter(["r", "a"])

            wizard = PhysicalRecognitionWizard(
                index_path="index.json",
                plan_path=str(plan_path),
                output_dir=tmp_dir,
                rotations=[0],
                manual_confirm=True,
                preflight_target=True,
                target_preflight_runner=preflight_runner,
                pipeline=pipeline,
                benchmark_runner=benchmark_runner,
                session_dir_factory=lambda _output_dir: session_dir,
                input_func=lambda _prompt="": next(answers),
                print_func=lambda *_args, **_kwargs: None,
            )

            wizard.run()

            self.assertEqual(len(preflight_runner.calls), 2)
            self.assertEqual(len(benchmark_runner.calls), 1)


if __name__ == "__main__":
    unittest.main()

import tempfile
import struct
import sys
import unittest
from pathlib import Path
from unittest.mock import patch

from tools.generate_calibration_target_a4 import (
    A4_TARGET_HEIGHT_PX,
    A4_TARGET_WIDTH_PX,
    main,
    generate_calibration_target_png,
)


class GenerateCalibrationTargetA4Test(unittest.TestCase):
    def test_generator_creates_a4_target_file(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "target.png"

            generated_path = generate_calibration_target_png(str(output_path))

            self.assertEqual(generated_path, output_path)
            self.assertTrue(output_path.exists())
            self.assertGreater(output_path.stat().st_size, 1000)

    def test_target_has_expected_a4_dimensions(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "target.png"

            generate_calibration_target_png(str(output_path))

            data = output_path.read_bytes()
            width, height = struct.unpack(">II", data[16:24])
            self.assertEqual(width, A4_TARGET_WIDTH_PX)
            self.assertEqual(height, A4_TARGET_HEIGHT_PX)

    def test_standard_cli_invocation_creates_png_without_exception(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "target.png"

            with patch.object(sys, "argv", [
                "generate_calibration_target_a4.py",
                "--output",
                str(output_path),
            ]):
                result = main()

            self.assertEqual(result, 0)
            self.assertTrue(output_path.exists())

    def test_optional_pdf_path_does_not_break_png_generation(self):
        with tempfile.TemporaryDirectory() as tmp_dir:
            output_path = Path(tmp_dir) / "target.png"
            pdf_path = Path(tmp_dir) / "target.pdf"

            with patch.object(sys, "argv", [
                "generate_calibration_target_a4.py",
                "--output",
                str(output_path),
                "--output-pdf",
                str(pdf_path),
            ]):
                result = main()

            self.assertEqual(result, 0)
            self.assertTrue(output_path.exists())

    def test_actual_assets_png_has_expected_a4_dimensions(self):
        asset_path = Path(__file__).resolve().parents[1] / "assets" / "calibration" / "tarotvision_calibration_target_a4.png"

        data = asset_path.read_bytes()
        width, height = struct.unpack(">II", data[16:24])

        self.assertEqual(width, A4_TARGET_WIDTH_PX)
        self.assertEqual(height, A4_TARGET_HEIGHT_PX)


if __name__ == "__main__":
    unittest.main()

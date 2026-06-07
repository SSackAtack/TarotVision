import json
import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from tarotvision.storage.diagnostics import DetectionDiagnosticsRecorder


class DetectionDiagnosticsRecorderTest(unittest.TestCase):
    def test_records_detection_attempts_and_prunes_old_records(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            recorder = DetectionDiagnosticsRecorder(base_dir=tmpdir, max_records=2)
            image = np.full((10, 12, 3), 50, dtype=np.uint8)
            mask = np.full((10, 12), 255, dtype=np.uint8)

            first = recorder.record_attempt(
                previous=image,
                current=image,
                mask=mask,
                result_image=image,
                metadata=[{"id": "card_001"}],
                status="accepted",
            )
            second = recorder.record_attempt(
                previous=image,
                current=image,
                mask=mask,
                result_image=image,
                metadata=[],
                status="no_roi",
            )
            third = recorder.record_attempt(
                previous=image,
                current=image,
                mask=mask,
                result_image=image,
                metadata=[],
                status="refinery_failed",
            )

            self.assertFalse(first.exists())
            self.assertTrue(second.exists())
            self.assertTrue(third.exists())

            remaining = sorted(p.name for p in Path(tmpdir).glob("detection_*"))
            self.assertEqual(remaining, ["detection_002", "detection_003"])

            self.assertTrue((third / "previous.png").exists())
            self.assertTrue((third / "current.png").exists())
            self.assertTrue((third / "mask.png").exists())
            self.assertTrue((third / "result.png").exists())
            self.assertTrue((third / "metadata.json").exists())

            with open(third / "metadata.json", "r", encoding="utf-8") as handle:
                data = json.load(handle)

            self.assertEqual(data["status"], "refinery_failed")
            self.assertEqual(data["attempt"], 3)
            self.assertIn("timestamp", data)

            saved_mask = cv2.imread(str(third / "mask.png"), cv2.IMREAD_GRAYSCALE)
            self.assertEqual(saved_mask.shape, (10, 12))


if __name__ == "__main__":
    unittest.main()

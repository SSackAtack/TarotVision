import sys
import tempfile
import unittest
from pathlib import Path

import cv2
import numpy as np

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from tarotvision.storage.snapshots import SnapshotManager
from tarotvision.vision.diff import DiffDetector


def make_table_with_cards(card_rects):
    image = np.full((300, 400, 3), 35, dtype=np.uint8)
    for x, y, w, h in card_rects:
        cv2.rectangle(image, (x, y), (x + w, y + h), (220, 220, 220), -1)
    return image


class RollingSnapshotOfflineTest(unittest.TestCase):
    def test_second_detection_uses_previous_accepted_state(self):
        empty_table = make_table_with_cards([])
        one_card = make_table_with_cards([(60, 80, 70, 120)])
        two_cards = make_table_with_cards([(60, 80, 70, 120), (230, 90, 70, 120)])

        detector = DiffDetector(diff_threshold=20, min_area=4000, max_area=20000)

        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(base_dir=tmpdir)
            manager.save_snapshot_0(empty_table)

            manager.save_snapshot_current(one_card)
            first_roi, _ = detector.detect_change_roi(
                manager.get_snapshot_current(),
                manager.get_snapshot_previous(),
            )
            self.assertIsNotNone(first_roi)
            manager.accept_current_as_previous()

            manager.save_snapshot_current(two_cards)
            second_roi, _ = detector.detect_change_roi(
                manager.get_snapshot_current(),
                manager.get_snapshot_previous(),
            )
            self.assertIsNotNone(second_roi)

            (cx, cy), (width, height), _ = second_roi

            self.assertGreater(cx, 220)
            self.assertLess(cx, 320)
            self.assertGreater(cy, 80)
            self.assertLess(cy, 180)
            self.assertLess(width * height, 15000)


if __name__ == "__main__":
    unittest.main()

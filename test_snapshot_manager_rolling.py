import sys
import tempfile
import unittest
from pathlib import Path

import numpy as np

sys.path.append(str(Path(__file__).resolve().parent / "src"))

from tarotvision.storage.snapshots import SnapshotManager


class SnapshotManagerRollingTest(unittest.TestCase):
    def test_current_becomes_previous_only_after_acceptance(self):
        with tempfile.TemporaryDirectory() as tmpdir:
            manager = SnapshotManager(base_dir=tmpdir)

            empty = np.zeros((12, 16, 3), dtype=np.uint8)
            one_card = np.full((12, 16, 3), 40, dtype=np.uint8)
            two_cards = np.full((12, 16, 3), 90, dtype=np.uint8)

            manager.save_snapshot_0(empty)

            self.assertTrue(np.array_equal(manager.get_snapshot_0(), empty))
            self.assertTrue(np.array_equal(manager.get_snapshot_previous(), empty))
            self.assertTrue((Path(tmpdir) / "snapshot_0.png").exists())
            self.assertTrue((Path(tmpdir) / "snapshot_previous.png").exists())

            manager.save_snapshot_current(one_card)

            self.assertTrue(np.array_equal(manager.get_snapshot_current(), one_card))
            self.assertTrue(np.array_equal(manager.get_snapshot_previous(), empty))

            manager.accept_current_as_previous()

            self.assertTrue(np.array_equal(manager.get_snapshot_previous(), one_card))

            manager.save_snapshot_current(two_cards)

            self.assertTrue(np.array_equal(manager.get_snapshot_current(), two_cards))
            self.assertTrue(np.array_equal(manager.get_snapshot_previous(), one_card))

            manager.accept_current_as_previous()

            self.assertTrue(np.array_equal(manager.get_snapshot_previous(), two_cards))


if __name__ == "__main__":
    unittest.main()

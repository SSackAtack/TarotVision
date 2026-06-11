import unittest
import shutil
import json
from pathlib import Path
import numpy as np
import cv2

import sys

# Dodanie src do sys.path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir / "src"))

from tarotvision.recognition.index_builder import ReferenceIndexBuilder

class TestBuildRecognitionIndex(unittest.TestCase):
    def setUp(self):
        # Tworzenie tymczasowej struktury katalogów w output
        self.test_dir = Path("output/test_build_index")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        self.base_decks_dir = self.test_dir / "assets" / "decks"
        
        self.deck_id = "test_deck"
        self.source_subdir = "test_scans"
        self.output_subdir = "test_index"
        
        self.scans_dir = self.base_decks_dir / self.deck_id / self.source_subdir
        self.scans_dir.mkdir(parents=True, exist_ok=True)
        
        # Tworzenie sztucznych obrazów kart
        self.ref_ids = ["Card_A", "Card_B"]
        for ref_id in self.ref_ids:
            img = np.zeros((1032, 600, 3), dtype=np.uint8)
            # Rysujemy coś na obrazie, żeby cechy nie były identyczne
            cv2.rectangle(img, (50, 50), (200, 200), (255, 255, 255), -1)
            cv2.imwrite(str(self.scans_dir / f"{ref_id}.png"), img)

    def tearDown(self):
        # Czyszczenie
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_builder_initialization(self):
        builder = ReferenceIndexBuilder(
            base_decks_dir=str(self.base_decks_dir),
            source_subdir=self.source_subdir,
            output_subdir=self.output_subdir,
            source_domain="camera"
        )
        self.assertEqual(builder.source_subdir, self.source_subdir)
        self.assertEqual(builder.output_subdir, self.output_subdir)
        self.assertEqual(builder.source_domain, "camera")

    def test_build_index_creates_files(self):
        builder = ReferenceIndexBuilder(
            base_decks_dir=str(self.base_decks_dir),
            source_subdir=self.source_subdir,
            output_subdir=self.output_subdir,
            source_domain="camera"
        )
        
        success = builder.build_index(self.deck_id)
        self.assertTrue(success)
        
        index_dir = self.base_decks_dir / self.deck_id / self.output_subdir
        manifest_path = index_dir / "index_manifest.json"
        features_path = index_dir / "features.npz"
        
        self.assertTrue(manifest_path.exists())
        self.assertTrue(features_path.exists())
        
        # Weryfikacja manifestu
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        self.assertEqual(manifest["deck_id"], self.deck_id)
        self.assertEqual(manifest["source_domain"], "camera")
        self.assertEqual(manifest["source_scan_dir"], f"assets/decks/{self.deck_id}/{self.source_subdir}")
        self.assertEqual(manifest["source_scans_count"], 2)
        
        # Weryfikacja npz
        with np.load(features_path, allow_pickle=True) as data:
            ref_ids = data["reference_ids"].tolist()
            self.assertIn("Card_A", ref_ids)
            self.assertIn("Card_B", ref_ids)
            self.assertEqual(data["gray_fingerprints"].shape, (2, 64 * 110))

if __name__ == "__main__":
    unittest.main()

import os
import sys
import unittest
import shutil
import json
from pathlib import Path
import cv2
import numpy as np

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.index_builder import ReferenceIndexBuilder
from tarotvision.recognition.index_loader import ReferenceIndexLoader

class TestReferenceIndexBuilder(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path("output/test_index_builder")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.deck_id = "fake_deck"
        self.scans_dir = self.test_dir / self.deck_id / "reference_scans"
        self.scans_dir.mkdir(parents=True, exist_ok=True)
        
        # Tworzenie 3 syntetycznych obrazów kart (każdy inny wzór, aby cechy się różniły)
        self.create_synthetic_card("Fake_01", (255, 0, 0), draw_shape="circle")
        self.create_synthetic_card("Fake_02", (0, 255, 0), draw_shape="rectangle")
        self.create_synthetic_card("Fake_03", (0, 0, 255), draw_shape="triangle")

    def tearDown(self):
        # Usunięcie katalogu testowego po zakończeniu
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def create_synthetic_card(self, name: str, color: tuple, draw_shape: str):
        # Tworzymy obrazek o proporcjach zbliżonych do karty (np. 600x1032)
        img = np.zeros((1032, 600, 3), dtype=np.uint8)
        # Tło jasnoszare
        img[:] = (220, 220, 220)
        
        # Narysowanie kształtu na środku
        if draw_shape == "circle":
            cv2.circle(img, (300, 516), 150, color, -1)
        elif draw_shape == "rectangle":
            cv2.rectangle(img, (150, 366), (450, 666), color, -1)
        elif draw_shape == "triangle":
            pts = np.array([[300, 316], [150, 666], [450, 666]], np.int32)
            cv2.fillPoly(img, [pts], color)
            
        # Dodanie ramki
        cv2.rectangle(img, (20, 20), (580, 1012), (50, 50, 50), 10)
        
        cv2.imwrite(str(self.scans_dir / f"{name}.png"), img)

    def test_build_and_load_index(self):
        builder = ReferenceIndexBuilder(base_decks_dir=str(self.test_dir))
        
        # Budowanie indeksu
        success = builder.build_index(self.deck_id)
        self.assertTrue(success)
        
        # Sprawdzenie istnienia plików
        index_dir = self.test_dir / self.deck_id / "recognition_index"
        manifest_path = index_dir / "index_manifest.json"
        features_path = index_dir / "features.npz"
        
        self.assertTrue(manifest_path.exists())
        self.assertTrue(features_path.exists())
        
        # Wczytanie i weryfikacja manifestu
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        self.assertEqual(manifest["deck_id"], self.deck_id)
        self.assertEqual(manifest["source_scans_count"], 3)
        self.assertEqual(len(manifest["references"]), 3)
        
        # Sprawdzenie ekstraktorów
        self.assertTrue(manifest["feature_extractors"]["gray_fingerprint"]["enabled"])
        self.assertTrue(manifest["feature_extractors"]["dhash"]["enabled"])
        
        # Wczytanie za pomocą ReferenceIndexLoader
        loader = ReferenceIndexLoader(base_decks_dir=str(self.test_dir))
        index = loader.load_index(self.deck_id)
        
        self.assertIsNotNone(index)
        self.assertEqual(index["manifest"]["deck_id"], self.deck_id)
        
        features = index["features"]
        self.assertEqual(len(features["reference_ids"]), 3)
        self.assertIn("Fake_01", features["reference_ids"])
        self.assertIn("Fake_02", features["reference_ids"])
        self.assertIn("Fake_03", features["reference_ids"])
        
        # Weryfikacja wymiarów macierzy cech
        # gray_fingerprints: (3, 7040)
        self.assertEqual(features["gray_fingerprints"].shape, (3, 7040))
        # dhashes: (3, 64)
        self.assertEqual(features["dhashes"].shape, (3, 64))
        # gray_histograms: (3, 64)
        self.assertEqual(features["gray_histograms"].shape, (3, 64))
        # color_histograms: (3, 512)
        self.assertEqual(features["color_histograms"].shape, (3, 512))
        # region_fingerprints: (3, 9, 256)
        self.assertEqual(features["region_fingerprints"].shape, (3, 9, 256))

if __name__ == "__main__":
    unittest.main()

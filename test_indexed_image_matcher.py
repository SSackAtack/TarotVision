import os
import sys
import unittest
import shutil
from pathlib import Path
import cv2
import numpy as np

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.index_builder import ReferenceIndexBuilder
from tarotvision.recognition.index_loader import ReferenceIndexLoader
from tarotvision.recognition.indexed_matcher import IndexedImageMatcher

class TestIndexedImageMatcher(unittest.TestCase):
    
    def setUp(self):
        self.test_dir = Path("output/test_indexed_matcher")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.deck_id = "test_deck"
        self.scans_dir = self.test_dir / self.deck_id / "reference_scans"
        self.scans_dir.mkdir(parents=True, exist_ok=True)
        
        # Generujemy 3 syntetyczne referencje
        self.create_synthetic_card("Card_A", (50, 50, 200), "circle")
        self.create_synthetic_card("Card_B", (50, 200, 50), "rectangle")
        self.create_synthetic_card("Card_C", (200, 50, 50), "triangle")
        
        # Zbudowanie indeksu
        builder = ReferenceIndexBuilder(base_decks_dir=str(self.test_dir))
        builder.build_index(self.deck_id)
        
        # Załadowanie indeksu
        loader = ReferenceIndexLoader(base_decks_dir=str(self.test_dir))
        self.index = loader.load_index(self.deck_id)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def create_synthetic_card(self, name: str, color: tuple, shape: str):
        img = np.zeros((1032, 600, 3), dtype=np.uint8)
        img[:] = (240, 240, 240)
        
        if shape == "circle":
            cv2.circle(img, (300, 516), 180, color, -1)
            # Dodatkowy asymetryczny element, by obrót o 180° był odróżnialny
            cv2.rectangle(img, (100, 100), (200, 200), (0, 0, 0), -1)
        elif shape == "rectangle":
            cv2.rectangle(img, (150, 300), (450, 732), color, -1)
            cv2.circle(img, (150, 150), 30, (0, 0, 0), -1)
        elif shape == "triangle":
            pts = np.array([[300, 250], [100, 750], [500, 750]], np.int32)
            cv2.fillPoly(img, [pts], color)
            cv2.circle(img, (450, 150), 30, (0, 0, 0), -1)
            
        cv2.rectangle(img, (10, 10), (590, 1022), (0, 0, 0), 10)
        cv2.imwrite(str(self.scans_dir / f"{name}.png"), img)

    def test_matching_card_0_degrees(self):
        matcher = IndexedImageMatcher(self.index)
        
        # Wczytujemy oryginalny obrazek jako crop z kamery (0 stopni)
        crop_path = self.scans_dir / "Card_A.png"
        crop_image = cv2.imread(str(crop_path))
        
        result = matcher.match_card(crop_image)
        
        self.assertEqual(result["recognized_deck"], self.deck_id)
        self.assertIsNone(result["recognized_card"]) # Sprawdzamy czy recognized_card jest None
        self.assertEqual(result["best_reference_id"], "Card_A")
        self.assertEqual(result["best_rotation"], 0)
        self.assertTrue(0.0 <= result["confidence"] <= 1.0)
        
        # Sprawdzamy czy candidates są posortowani i nie są puści
        self.assertTrue(len(result["candidates"]) > 0)
        self.assertEqual(result["candidates"][0]["reference_id"], "Card_A")
        
        # Sprawdzamy score_breakdown
        best_candidate = result["candidates"][0]
        self.assertIn("score_breakdown", best_candidate)
        self.assertIn("gray_fingerprint", best_candidate["score_breakdown"])
        self.assertIn("dhash", best_candidate["score_breakdown"])
        self.assertIn("gray_histogram", best_candidate["score_breakdown"])
        self.assertIn("color_histogram", best_candidate["score_breakdown"])
        self.assertIn("region_fingerprints", best_candidate["score_breakdown"])

    def test_matching_card_180_degrees(self):
        matcher = IndexedImageMatcher(self.index)
        
        # Wczytujemy obrazek Card_B i obracamy o 180 stopni
        crop_path = self.scans_dir / "Card_B.png"
        img = cv2.imread(str(crop_path))
        crop_image_180 = cv2.rotate(img, cv2.ROTATE_180)
        
        result = matcher.match_card(crop_image_180)
        
        self.assertEqual(result["best_reference_id"], "Card_B")
        self.assertEqual(result["best_rotation"], 180)
        self.assertTrue(result["confidence"] > 0.8) # Powinno być bardzo wysokie dopasowanie

    def test_matching_with_session_color_profile(self):
        matcher = IndexedImageMatcher(self.index)
        
        # Stworzenie sztucznego przyciemnionego cropa
        crop_path = self.scans_dir / "Card_C.png"
        img = cv2.imread(str(crop_path))
        dark_crop = (img.astype(np.float32) * 0.5).astype(np.uint8)
        
        # Dopasowanie bez profilu
        res_no_profile = matcher.match_card(dark_crop)
        
        # Tworzymy uproszczony mock profilu kalibracji barwnej (który przywróci jasność)
        # lab_mean dla referencji (oryginalnej Card_C):
        ref_lab = cv2.cvtColor(img, cv2.COLOR_BGR2LAB)
        ref_mean, ref_std = cv2.meanStdDev(ref_lab)
        # lab_mean dla dark_crop:
        dark_lab = cv2.cvtColor(dark_crop, cv2.COLOR_BGR2LAB)
        dark_mean, dark_std = cv2.meanStdDev(dark_lab)
        
        mock_profile = {
            "profile_type": "session_color_calibration",
            "profile_version": "lab_mean_std_v1",
            "deck_id": self.deck_id,
            "calibration_reference_id": "Card_C",
            "camera_lab_mean": dark_mean.flatten().tolist(),
            "camera_lab_std": (dark_std.flatten() + 1e-6).tolist(),
            "reference_lab_mean": ref_mean.flatten().tolist(),
            "reference_lab_std": ref_std.flatten().tolist(),
            "method": "lab_mean_std_v1"
        }
        
        # Dopasowanie z profilem
        res_with_profile = matcher.match_card(dark_crop, session_color_profile=mock_profile)
        
        self.assertEqual(res_with_profile["best_reference_id"], "Card_C")
        self.assertTrue(res_with_profile["session_color_profile_used"])
        # Pewność z profilem powinna być wyższa lub równa niż bez profilu dla przyciemnionej karty
        self.assertGreaterEqual(res_with_profile["confidence"], res_no_profile["confidence"] - 0.05)

if __name__ == "__main__":
    unittest.main()

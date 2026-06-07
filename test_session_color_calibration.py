import unittest
import numpy as np
import cv2
import sys
import os
import json
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.session_color_calibration import SessionColorCalibrator, apply_color_profile

class TestSessionColorCalibration(unittest.TestCase):

    def setUp(self):
        # Znalezienie oryginalnego skanu do testu
        self.ref_path = Path("assets/decks/gilded/reference_scans/Gilded_38.png")
        if not self.ref_path.exists():
            # Fallback dla środowisk testowych bez fizycznego repo
            self.ref_image = np.full((1032, 600, 3), 128, dtype=np.uint8)
            cv2.rectangle(self.ref_image, (100, 100), (500, 932), (50, 180, 70), -1)
            cv2.circle(self.ref_image, (300, 516), 100, (20, 30, 200), -1)
        else:
            self.ref_image = cv2.imread(str(self.ref_path))

        # Przygotowanie konfiguracji testowej
        self.config_path = Path("config/session_color_calibration_test.json")
        test_config = {
            "enabled": True,
            "deck_id": "gilded",
            "calibration_reference_id": "Gilded_38",
            "reference_scan_dir": "assets/decks/gilded/reference_scans",
            "output_profile_path": "output/test/session_color_profile.json",
            "canonical_width_px": 600,
            "canonical_height_px": 1032,
            "method": "lab_mean_std_v1",
            "apply_to_matcher": True,
            "quality_thresholds": {
                "max_brightness_delta_abs": 80,
                "max_channel_gain": 3.0,
                "min_channel_gain": 0.3
            }
        }
        self.config_path.parent.mkdir(parents=True, exist_ok=True)
        with open(self.config_path, "w", encoding="utf-8") as f:
            json.dump(test_config, f, indent=2)

        self.calibrator = SessionColorCalibrator(config_path=str(self.config_path))

    def tearDown(self):
        # Usuwanie pliku testowej konfiguracji
        if self.config_path.exists():
            self.config_path.unlink()

    def test_calibration_recovers_distorted_image(self):
        # 1. Tworzymy sztucznie zniekształcony obraz (symulowany crop z kamery)
        # Przyciemniamy obraz, zmieniamy kontrast i przesuwamy balans barwny (dodajemy czerwień)
        distorted = self.ref_image.astype(np.float32)
        
        # Zniekształcenie kontrastu i jasności
        distorted = distorted * 0.8 - 15.0
        
        # Zniekształcenie balansu kolorów (BGR)
        distorted[:, :, 0] -= 10.0 # Mniej niebieskiego
        distorted[:, :, 2] += 25.0 # Więcej czerwonego
        
        distorted = np.clip(distorted, 0, 255).astype(np.uint8)
        
        # 2. Uruchomienie kalibracji
        profile = self.calibrator.calculate_color_profile(camera_crop=distorted, reference_image=self.ref_image)
        
        # Weryfikacja metryk profilu
        self.assertEqual(profile["profile_type"], "session_color_calibration")
        self.assertEqual(profile["quality_status"], "accepted")
        self.assertGreater(profile["score_after"], 0.90)
        
        print(f"  [DEBUG] Score before: {profile['score_before']:.4f}")
        print(f"  [DEBUG] Score after: {profile['score_after']:.4f}")
        print(f"  [DEBUG] Brightness Delta: {profile['brightness_delta']:.2f}")
        print(f"  [DEBUG] BGR Gains: {profile['bgr_channel_gain']}")
        
        # 3. Zastosowanie korekcji
        corrected = apply_color_profile(distorted, profile)
        
        # 4. Sprawdzenie, czy skorygowany obraz jest bliższy oryginałowi niż zniekształcony
        mae_before = np.mean(cv2.absdiff(distorted, self.ref_image))
        mae_after = np.mean(cv2.absdiff(corrected, self.ref_image))
        
        print(f"  [DEBUG] MAE before: {mae_before:.2f}, MAE after: {mae_after:.2f}")
        self.assertLess(mae_after, mae_before)
        
        # 5. Zapis profilu
        profile_path = self.calibrator.save_profile(profile, distorted, self.ref_image)
        self.assertTrue(profile_path.exists())
        self.assertTrue(Path("output/test/calibration/calibration_crop.png").exists())
        self.assertTrue(Path("output/test/calibration/calibration_corrected.png").exists())

if __name__ == "__main__":
    unittest.main()

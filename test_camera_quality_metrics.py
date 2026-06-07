import unittest
import numpy as np
import cv2
import sys
import os

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.preflight import calculate_quality_metrics, CameraPreflightManager

class TestCameraQualityMetrics(unittest.TestCase):

    def test_black_image_underexposure(self):
        # 1. Czarny obraz
        black_frame = np.zeros((480, 640, 3), dtype=np.uint8)
        metrics = calculate_quality_metrics([black_frame])
        
        self.assertEqual(metrics["brightness_mean"], 0.0)
        self.assertEqual(metrics["underexposed_ratio"], 1.0)
        self.assertEqual(metrics["overexposed_ratio"], 0.0)

    def test_white_image_overexposure(self):
        # 2. Biały obraz
        white_frame = np.full((480, 640, 3), 255, dtype=np.uint8)
        metrics = calculate_quality_metrics([white_frame])
        
        self.assertEqual(metrics["brightness_mean"], 255.0)
        self.assertEqual(metrics["underexposed_ratio"], 0.0)
        self.assertEqual(metrics["overexposed_ratio"], 1.0)

    def test_sharp_vs_blurred_laplacian(self):
        # 3. Tworzymy ostry wzór (szachownica)
        sharp_frame = np.zeros((200, 200), dtype=np.uint8)
        # Rysujemy pasy
        for i in range(0, 200, 20):
            sharp_frame[i:i+10, :] = 255
            
        # Rozmyty wariant
        blurred_frame = cv2.GaussianBlur(sharp_frame, (15, 15), 0)
        
        metrics_sharp = calculate_quality_metrics([sharp_frame])
        metrics_blurred = calculate_quality_metrics([blurred_frame])
        
        # Laplacian variance dla ostrego obrazu musi być znacząco wyższa
        self.assertGreater(metrics_sharp["laplacian_variance"], metrics_blurred["laplacian_variance"])
        logger_msg = f"Sharp Laplacian: {metrics_sharp['laplacian_variance']}, Blurred Laplacian: {metrics_blurred['laplacian_variance']}"
        print(f"  [DEBUG] {logger_msg}")

    def test_stable_vs_moving_delta(self):
        # 4. Sekwencja stabilna (identyczne klatki)
        frame = np.full((100, 100), 128, dtype=np.uint8)
        metrics_stable = calculate_quality_metrics([frame, frame, frame])
        
        self.assertEqual(metrics_stable["frame_delta_mean"], 0.0)
        
        # Sekwencja ruchoma/zmienna
        frame1 = np.full((100, 100), 100, dtype=np.uint8)
        frame2 = np.full((100, 100), 110, dtype=np.uint8)
        frame3 = np.full((100, 100), 125, dtype=np.uint8)
        metrics_moving = calculate_quality_metrics([frame1, frame2, frame3])
        
        # Średnia różnica: (10 + 15) / 2 = 12.5
        self.assertAlmostEqual(metrics_moving["frame_delta_mean"], 12.5, places=1)

    def test_preflight_evaluation_logic(self):
        # 5. Sprawdzenie logiki preflightu (accepted/warning/rejected)
        manager = CameraPreflightManager()
        
        # Dobre parametry
        good_metrics = {
            "brightness_mean": 100.0,
            "brightness_std": 40.0,
            "laplacian_variance": 150.0,
            "overexposed_ratio": 0.005,
            "underexposed_ratio": 0.01,
            "frame_delta_mean": 0.5
        }
        self.assertEqual(manager.evaluate_quality(good_metrics), "accepted")
        
        # Parametry ostrzeżenia (warning)
        warning_metrics = {
            "brightness_mean": 45.0, # lekko poniżej 50
            "brightness_std": 40.0,
            "laplacian_variance": 150.0,
            "overexposed_ratio": 0.005,
            "underexposed_ratio": 0.01,
            "frame_delta_mean": 0.5
        }
        self.assertEqual(manager.evaluate_quality(warning_metrics), "warning")
        
        # Parametry krytyczne (rejected)
        rejected_metrics = {
            "brightness_mean": 20.0, # bardzo ciemno
            "brightness_std": 40.0,
            "laplacian_variance": 40.0, # nieostre
            "overexposed_ratio": 0.005,
            "underexposed_ratio": 0.20,
            "frame_delta_mean": 0.5
        }
        self.assertEqual(manager.evaluate_quality(rejected_metrics), "rejected")

if __name__ == "__main__":
    unittest.main()

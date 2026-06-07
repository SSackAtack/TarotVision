import unittest
import os
import sys
import numpy as np
import json
import cv2

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.vision.diff import DiffDetector

class TestDetectionMetricsDiagnostics(unittest.TestCase):
    def setUp(self):
        # Tło 300x400 (wysokość x szerokość)
        self.bg = np.full((300, 400, 3), 128, dtype=np.uint8)

    def test_accepted_contour_metrics(self):
        # Karta: 50x60 px (pole ok. 3000 px) na pozycji [100, 100]
        current = self.bg.copy()
        current[100:160, 100:150] = 250
        
        # Inicjalizacja detektora (min_area=1000, max_area=10000)
        detector = DiffDetector(diff_threshold=25, min_area=1000, max_area=10000)
        
        roi_rect, debug_mask, diff_debug = detector.detect_change_roi_with_debug(current, self.bg)
        
        self.assertIsNotNone(roi_rect)
        self.assertIsNotNone(debug_mask)
        self.assertTrue(diff_debug["accepted"])
        self.assertGreaterEqual(diff_debug["contours_count"], 1)
        self.assertIsNotNone(diff_debug["accepted_area"])
        self.assertIsNotNone(diff_debug["accepted_rect"])
        
        self.assertEqual(len(diff_debug["accepted_bbox"]), 4)
        x, y, w, h = diff_debug["accepted_bbox"]
        self.assertAlmostEqual(x, 100, delta=5)
        self.assertAlmostEqual(y, 100, delta=5)
        self.assertAlmostEqual(w, 50, delta=10)
        self.assertAlmostEqual(h, 60, delta=10)

    def test_rejected_contour_below_min_area(self):
        # Mały prostokąt: 10x10 px (pole ok. 100 px)
        current = self.bg.copy()
        current[100:110, 100:110] = 250
        
        detector = DiffDetector(diff_threshold=25, min_area=1000, max_area=10000)
        
        roi_rect, debug_mask, diff_debug = detector.detect_change_roi_with_debug(current, self.bg)
        
        self.assertIsNone(roi_rect)
        self.assertFalse(diff_debug["accepted"])
        self.assertGreaterEqual(diff_debug["contours_count"], 1)
        
        # Sprawdzamy czy powód odrzucenia to "area_below_min"
        reasons = [rc["reason"] for rc in diff_debug["rejected_contours"]]
        self.assertIn("area_below_min", reasons)

    def test_rejected_contour_above_max_area(self):
        # Duży prostokąt: 200x150 px (pole ok. 30000 px)
        current = self.bg.copy()
        current[50:200, 50:250] = 250
        
        detector = DiffDetector(diff_threshold=25, min_area=1000, max_area=10000)
        
        roi_rect, debug_mask, diff_debug = detector.detect_change_roi_with_debug(current, self.bg)
        
        self.assertIsNone(roi_rect)
        self.assertFalse(diff_debug["accepted"])
        self.assertGreaterEqual(diff_debug["contours_count"], 1)
        
        # Sprawdzamy czy powód odrzucenia to "area_above_max"
        reasons = [rc["reason"] for rc in diff_debug["rejected_contours"]]
        self.assertIn("area_above_max", reasons)

    def test_json_serializability(self):
        current = self.bg.copy()
        current[100:160, 100:150] = 250
        
        detector = DiffDetector(diff_threshold=25, min_area=1000, max_area=10000)
        _, _, diff_debug = detector.detect_change_roi_with_debug(current, self.bg)
        
        # Sprawdzenie serializacji JSON
        try:
            serialized = json.dumps(diff_debug)
            deserialized = json.loads(serialized)
            self.assertEqual(deserialized["accepted"], diff_debug["accepted"])
        except Exception as e:
            self.fail(f"Błąd podczas serializacji JSON: {e}")

    def test_compatibility_with_old_method(self):
        current = self.bg.copy()
        current[100:160, 100:150] = 250
        
        detector = DiffDetector(diff_threshold=25, min_area=1000, max_area=10000)
        
        # Wywołanie starej metody, która ma zwracać krotkę 2-elementową
        result = detector.detect_change_roi(current, self.bg)
        
        self.assertEqual(len(result), 2)
        self.assertIsNotNone(result[0])
        self.assertIsNotNone(result[1])

if __name__ == "__main__":
    unittest.main()

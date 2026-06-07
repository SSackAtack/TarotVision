import unittest
import shutil
import os
import sys
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.state.table_state import TableState

class TestTableStateCoordinates(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test/table_state_coordinates")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_set_table_size_valid(self):
        state = TableState(session_dir=str(self.test_dir))
        
        # Sprawdzamy początkowy stan
        self.assertIsNone(state.table["image_width"])
        self.assertIsNone(state.table["image_height"])
        self.assertEqual(state.table["coordinate_system"], "corrected_table_image")
        
        # Ustawiamy poprawny rozmiar
        state.set_table_size(1200, 800)
        self.assertEqual(state.table["image_width"], 1200)
        self.assertEqual(state.table["image_height"], 800)
        
        # coordinate_system ma pozostać niezmieniony
        self.assertEqual(state.table["coordinate_system"], "corrected_table_image")

    def test_set_table_size_invalid(self):
        state = TableState(session_dir=str(self.test_dir))
        
        # Test 0
        with self.assertRaises(ValueError):
            state.set_table_size(0, 800)
        with self.assertRaises(ValueError):
            state.set_table_size(1200, 0)
            
        # Test ujemnych
        with self.assertRaises(ValueError):
            state.set_table_size(-1, 800)
        with self.assertRaises(ValueError):
            state.set_table_size(1200, -100)
            
        # Test None
        with self.assertRaises(ValueError):
            state.set_table_size(None, 800)
        with self.assertRaises(ValueError):
            state.set_table_size(1200, None)
            
        # Test typów
        with self.assertRaises(TypeError):
            state.set_table_size("1200", 800)
        with self.assertRaises(TypeError):
            state.set_table_size(1200, 800.5)
        with self.assertRaises(TypeError):
            state.set_table_size(True, 800)  # bool nie jest dozwolony

    def test_normalization_valid_size(self):
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(1200, 800)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        
        position = {
            "bbox_px": [300, 200, 600, 400],
            "center_px": [600, 400]
        }
        
        card = state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )
        
        self.assertIsNotNone(card)
        # center_px=[600, 400] dla stołu 1200x800 daje center_norm=[0.5, 0.5]
        self.assertEqual(card.position["center_norm"], [0.5, 0.5])
        # bbox_px=[300, 200, 600, 400] dla stołu 1200x800 daje bbox_norm=[0.25, 0.25, 0.5, 0.5]
        self.assertEqual(card.position["bbox_norm"], [0.25, 0.25, 0.5, 0.5])

    def test_normalization_missing_size(self):
        state = TableState(session_dir=str(self.test_dir))
        
        # Nie ustawiamy rozmiaru stołu (są None)
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        
        position = {
            "bbox_px": [300, 200, 600, 400],
            "center_px": [600, 400]
        }
        
        card = state.add_card_from_recognition(
            detection_id="det_002",
            recognition_result=recognition_result,
            position=position
        )
        
        self.assertIsNotNone(card)
        self.assertIsNone(card.position["center_norm"])
        self.assertIsNone(card.position["bbox_norm"])

if __name__ == "__main__":
    unittest.main()

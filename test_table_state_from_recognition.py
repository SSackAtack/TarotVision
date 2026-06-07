import os
import sys
import unittest
import shutil
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.state.table_state import TableState

class TestTableStateFromRecognition(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test/table_state_rec")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_from_recognition(self):
        state = TableState(session_dir=str(self.test_dir))
        
        # Przygotowanie sztucznego wyniku rozpoznawania dla karty tarota
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_73",
            "recognized_card": {
                "card_id": "the_sun",
                "display_name": "The Sun",
                "arcana": "major",
                "number": 19,
                "suit": None,
                "rank": None,
            },
            "mapping_status": "mapped",
            "confidence": 0.7792,
            "method": "indexed_visual_similarity_v1",
            "best_rotation": 0,
            "candidates": [
                {
                    "reference_id": "Gilded_73",
                    "score_breakdown": {
                        "gray_fingerprint": 0.8692,
                        "region_fingerprints": 0.8644,
                        "color_histogram": 0.3464,
                        "gray_histogram": 0.7908,
                        "dhash": 0.8438
                    }
                }
            ]
        }
        
        position = {
            "bbox_px": [420, 180, 286, 492],
            "center_px": [563, 426],
            "corners_px": [
                [420, 180],
                [706, 180],
                [706, 672],
                [420, 672]
            ]
        }
        
        files = {
            "crop_path": "output/sessions/current/detections/detection_007/crop.png",
            "metadata_path": "output/sessions/current/detections/detection_007/metadata.json",
            "mask_path": "output/sessions/current/detections/detection_007/mask.png",
            "result_path": "output/sessions/current/detections/detection_007/result.png"
        }
        
        diagnostics = {
            "geometry_ambiguous": False,
            "session_color_profile_used": True
        }
        
        card = state.add_card_from_recognition(
            detection_id="detection_007",
            recognition_result=recognition_result,
            position=position,
            files=files,
            diagnostics=diagnostics
        )
        
        self.assertIsNotNone(card)
        self.assertEqual(card.card_instance_id, "card_001")
        self.assertEqual(card.status, "recognized")
        self.assertEqual(card.recognized_card["card_id"], "the_sun")
        self.assertIsNone(card.recognized_special)
        self.assertEqual(card.confidence, 0.7792)
        
        # Sprawdzenie poprawności zapisu diagnostyki (w tym automatycznego pobrania score_breakdown)
        self.assertTrue(card.diagnostics["session_color_profile_used"])
        self.assertFalse(card.diagnostics["geometry_ambiguous"])
        self.assertEqual(card.diagnostics["score_breakdown"]["gray_fingerprint"], 0.8692)
        
        # Test zapisu i odczytu stanu
        state.save()
        
        state2 = TableState(session_dir=str(self.test_dir))
        state2.load()
        
        self.assertEqual(len(state2.cards), 1)
        loaded_card = state2.get_card_by_instance_id("card_001")
        self.assertEqual(loaded_card.status, "recognized")
        self.assertEqual(loaded_card.position["bbox_px"], [420, 180, 286, 492])

if __name__ == "__main__":
    unittest.main()

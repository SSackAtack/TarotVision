import os
import sys
import unittest
import shutil
import json
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.state.table_state import TableState, TableCard

class TestTableState(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test/table_state")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_table_state_lifecycle(self):
        # 1. Utworzenie pustego TableState
        state = TableState(session_dir=str(self.test_dir))
        self.assertEqual(len(state.cards), 0)
        self.assertEqual(state.session_id, "table_state")
        
        # Ustawienie rozmiaru stołu, by normalizacja przeszła poprawnie
        state.set_table_size(1920, 1080)
        
        # 2. Dodanie pierwszej karty
        recognition_result_1 = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_73",
            "recognized_card": {
                "card_id": "the_sun",
                "display_name": "The Sun",
                "arcana": "major",
                "number": 19,
                "suit": None,
                "rank": None,
                "notes": "Słońce XIX"
            },
            "mapping_status": "mapped",
            "confidence": 0.7792,
            "method": "indexed_visual_similarity_v1",
            "best_rotation": 0
        }
        
        position_1 = {
            "bbox_px": [100, 200, 300, 400],
            "center_px": [250, 400],
            "corners_px": [[100, 200], [400, 200], [400, 600], [100, 600]]
        }
        
        files_1 = {
            "crop_path": "some/crop.png",
            "metadata_path": "some/metadata.json"
        }
        
        diagnostics_1 = {
            "score_breakdown": {"dhash": 0.8},
            "geometry_ambiguous": False
        }
        
        card1 = state.add_card_from_recognition(
            detection_id="detection_001",
            recognition_result=recognition_result_1,
            position=position_1,
            files=files_1,
            diagnostics=diagnostics_1
        )
        
        # 3. Weryfikacja automatycznych identyfikatorów
        self.assertIsNotNone(card1)
        self.assertEqual(card1.card_instance_id, "card_001")
        self.assertEqual(card1.sequence_index, 1)
        self.assertEqual(card1.status, "recognized")
        
        # 10. Poprawne wyliczenie center_norm i bbox_norm (rozmiar stołu domyślny 1920x1080)
        self.assertEqual(card1.position["center_norm"], [round(250/1920, 4), round(400/1080, 4)])
        self.assertEqual(card1.position["bbox_norm"], [round(100/1920, 4), round(200/1080, 4), round(300/1920, 4), round(400/1080, 4)])
        
        # 5. Zapis do table_state.json
        state.save()
        self.assertTrue((self.test_dir / "table_state.json").exists())
        
        # 6. Ponowne wczytanie table_state.json
        state2 = TableState(session_dir=str(self.test_dir))
        state2.load()
        self.assertEqual(len(state2.cards), 1)
        
        loaded_card = state2.get_card_by_instance_id("card_001")
        self.assertIsNotNone(loaded_card)
        self.assertEqual(loaded_card.detection_id, "detection_001")
        self.assertEqual(loaded_card.recognized_card["card_id"], "the_sun")
        
        # 7. Dodanie drugiej karty (rewers)
        recognition_result_2 = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_back",
            "recognized_card": None,
            "recognized_special": {
                "entry_type": "deck_back",
                "display_name": "Gilded Back",
                "is_deck_back": True
            },
            "mapping_status": "deck_back",
            "confidence": 0.99,
            "method": "indexed_visual_similarity_v1",
            "best_rotation": 180
        }
        
        position_2 = {
            "bbox_px": [500, 200, 300, 400],
            "center_px": [650, 400],
            "corners_px": [[500, 200], [800, 200], [800, 600], [500, 600]]
        }
        
        card2 = state2.add_card_from_recognition(
            detection_id="detection_002",
            recognition_result=recognition_result_2,
            position=position_2
        )
        
        # 8. Obsługa rewersu jako deck_back
        self.assertIsNotNone(card2)
        self.assertEqual(card2.card_instance_id, "card_002")
        self.assertEqual(card2.sequence_index, 2)
        self.assertEqual(card2.status, "deck_back")
        self.assertIsNone(card2.recognized_card)
        self.assertEqual(card2.recognized_special["entry_type"], "deck_back")
        
        # 9. Ochrona przed ponownym dodaniem tego samego detection_id
        card_dup_id = state2.add_card_from_recognition(
            detection_id="detection_001",
            recognition_result=recognition_result_2,
            position=position_2
        )
        self.assertIsNone(card_dup_id)
        
        # Ochrona przed dodaniem geometrycznego duplikatu (odległość środków < 30px)
        position_near = {
            "bbox_px": [105, 205, 300, 400],
            "center_px": [255, 405], # odległość od card1 to (5^2 + 5^2)^0.5 = 7.07px < 30px
            "corners_px": []
        }
        card_dup_geom = state2.add_card_from_recognition(
            detection_id="detection_003",
            recognition_result=recognition_result_2,
            position=position_near
        )
        self.assertIsNone(card_dup_geom)

if __name__ == "__main__":
    unittest.main()

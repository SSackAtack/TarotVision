import unittest
import shutil
import os
import sys
import numpy as np
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.state.table_state import TableState
from tarotvision.vision.removal import CardRemovalDetector

class TestCardRemovalDetection(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test/card_removal")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_confirmed_card_removal(self):
        # Setup TableState z jedną aktywną kartą
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(400, 300)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        position = {
            "bbox_px": [100, 100, 100, 150],  # [x, y, w, h]
            "center_px": [150, 175],
            "corners_px": [
                [100, 100],
                [200, 100],
                [200, 250],
                [100, 250]
            ]
        }
        card = state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )
        self.assertIsNotNone(card)
        self.assertEqual(len(state.get_active_cards()), 1)

        # Tworzenie syntetycznych obrazów
        # snapshot_0 = tło (szara matryca)
        snapshot_0 = np.full((300, 400, 3), 128, dtype=np.uint8)
        
        # snapshot_previous = tło + jasna karta na pozycji [100, 100, 100, 150]
        snapshot_previous = snapshot_0.copy()
        snapshot_previous[100:250, 100:200] = 200
        
        # snapshot_current = tło przywrócone (karta zabrana)
        snapshot_current = snapshot_0.copy()
        
        # ROI zmiany pokrywa się z kartą
        changed_roi_rect = [100, 100, 100, 150]
        
        detector = CardRemovalDetector()
        result = detector.detect_card_removal(
            snapshot_0=snapshot_0,
            snapshot_previous=snapshot_previous,
            snapshot_current=snapshot_current,
            changed_roi_rect=changed_roi_rect,
            active_cards=state.get_active_cards()
        )
        
        self.assertEqual(result["decision"], "removed")
        self.assertEqual(result["card_instance_id"], "card_001")
        self.assertTrue(result["current_vs_background"] < result["previous_vs_background"])
        self.assertEqual(result["overlap_ratio"], 1.0)
        self.assertTrue(result["previous_vs_background"] >= 20.0)
        self.assertTrue(result["current_vs_background"] <= 12.0)

    def test_no_overlap_with_card(self):
        # Setup TableState z jedną aktywną kartą
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(400, 300)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        position = {
            "bbox_px": [100, 100, 100, 150],
            "center_px": [150, 175],
            "corners_px": [[100, 100], [200, 100], [200, 250], [100, 250]]
        }
        state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )

        snapshot_0 = np.full((300, 400, 3), 128, dtype=np.uint8)
        snapshot_previous = snapshot_0.copy()
        snapshot_previous[100:250, 100:200] = 200
        snapshot_current = snapshot_0.copy()
        
        # ROI zmiany poza kartą (np. w prawym dolnym rogu)
        changed_roi_rect = [250, 200, 50, 50]
        
        detector = CardRemovalDetector()
        result = detector.detect_card_removal(
            snapshot_0=snapshot_0,
            snapshot_previous=snapshot_previous,
            snapshot_current=snapshot_current,
            changed_roi_rect=changed_roi_rect,
            active_cards=state.get_active_cards()
        )
        
        self.assertEqual(result["decision"], "not_removed")
        self.assertIsNone(result["card_instance_id"])
        self.assertEqual(result["reason"], "no_overlap_with_active_card")

    def test_shadow_or_movement_card_remains(self):
        # Setup TableState z jedną aktywną kartą
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(400, 300)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        position = {
            "bbox_px": [100, 100, 100, 150],
            "center_px": [150, 175],
            "corners_px": [[100, 100], [200, 100], [200, 250], [100, 250]]
        }
        state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )

        snapshot_0 = np.full((300, 400, 3), 128, dtype=np.uint8)
        snapshot_previous = snapshot_0.copy()
        snapshot_previous[100:250, 100:200] = 200
        
        # snapshot_current: karta nadal leży, ale zmieniła jasność ze 200 na 190 (np. cień)
        snapshot_current = snapshot_0.copy()
        snapshot_current[100:250, 100:200] = 190
        
        changed_roi_rect = [100, 100, 100, 150]
        
        detector = CardRemovalDetector()
        result = detector.detect_card_removal(
            snapshot_0=snapshot_0,
            snapshot_previous=snapshot_previous,
            snapshot_current=snapshot_current,
            changed_roi_rect=changed_roi_rect,
            active_cards=state.get_active_cards()
        )
        
        # Decyzja powinna brzmieć "not_removed", bo tło nie zostało przywrócone (current_vs_background jest duże)
        self.assertEqual(result["decision"], "not_removed")
        self.assertEqual(result["card_instance_id"], "card_001")
        self.assertEqual(result["reason"], "background_not_restored")
        self.assertTrue(result["current_vs_background"] > 12.0)

    def test_tablestate_logical_removal(self):
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(400, 300)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.9
        }
        position = {
            "bbox_px": [100, 100, 100, 150],
            "center_px": [150, 175],
            "corners_px": [[100, 100], [200, 100], [200, 250], [100, 250]]
        }
        card = state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )
        
        # Oznaczenie jako usunięta
        updated_card = state.mark_card_removed(
            card_instance_id="card_001",
            detection_id="det_002",
            confidence=0.95
        )
        
        self.assertIsNotNone(updated_card)
        self.assertEqual(updated_card.status, "removed")
        self.assertEqual(updated_card.removal_detection_id, "det_002")
        self.assertEqual(updated_card.removal_confidence, 0.95)
        self.assertIsNotNone(updated_card.removed_at)
        
        # cards_count nie może się zmienić w liście self.cards
        self.assertEqual(len(state.cards), 1)
        self.assertEqual(state.cards[0].status, "removed")
        
        # Aktywne karty powinny być puste
        self.assertEqual(len(state.get_active_cards()), 0)
        
        # Historia musi zawierać event card_removed
        self.assertEqual(len(state.history), 2)  # add + remove
        remove_event = state.history[1]
        self.assertEqual(remove_event["event_type"], "card_removed")
        self.assertEqual(remove_event["card_instance_id"], "card_001")
        self.assertEqual(remove_event["detection_id"], "det_002")
        self.assertEqual(remove_event["removal_confidence"], 0.95)
        
        # Zapis i odczyt stanu
        state.save()
        
        state2 = TableState(session_dir=str(self.test_dir))
        state2.load()
        self.assertEqual(len(state2.cards), 1)
        self.assertEqual(state2.cards[0].status, "removed")
        self.assertEqual(state2.cards[0].removal_confidence, 0.95)

    def test_min_area_rect_to_bbox_conversion(self):
        import cv2
        # Symulacja minAreaRect: środek (150, 175), rozmiar (100, 150), obrót 0 stopni
        rect = ((150.0, 175.0), (100.0, 150.0), 0.0)
        box_pts = cv2.boxPoints(rect)
        changed_bbox = cv2.boundingRect(np.intp(box_pts))
        
        # Oczekiwany bbox to [100, 100, 100, 150] (z dokładnością do zaokrągleń)
        self.assertEqual(len(changed_bbox), 4)
        x, y, w, h = changed_bbox
        self.assertAlmostEqual(x, 100, delta=2)
        self.assertAlmostEqual(y, 100, delta=2)
        self.assertAlmostEqual(w, 100, delta=2)
        self.assertAlmostEqual(h, 150, delta=2)

if __name__ == "__main__":
    unittest.main()

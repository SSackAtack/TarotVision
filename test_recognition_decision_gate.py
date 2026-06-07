import unittest
import os
import sys
import shutil
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.decision import apply_recognition_decision
from tarotvision.state.table_state import TableState

class TestRecognitionDecisionGate(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test/decision_gate")
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)
        self.test_dir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_decision_recognized(self):
        match_result = {
            "candidates": [
                {"reference_id": "A", "score": 0.91},
                {"reference_id": "B", "score": 0.84},
            ],
            "best_reference_id": "A",
            "confidence": 0.91,
        }
        
        result = apply_recognition_decision(match_result)
        self.assertEqual(result["recognition_decision"], "recognized")
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["top1_reference_id"], "A")
        self.assertEqual(result["top2_reference_id"], "B")
        self.assertAlmostEqual(result["score_margin"], 0.07)
        self.assertEqual(result["decision_thresholds"]["min_recognition_score"], 0.82)
        self.assertEqual(result["decision_thresholds"]["min_score_margin"], 0.04)

    def test_decision_ambiguous(self):
        match_result = {
            "candidates": [
                {"reference_id": "A", "score": 0.91},
                {"reference_id": "B", "score": 0.89},
            ],
            "best_reference_id": "A",
            "confidence": 0.91,
        }
        
        result = apply_recognition_decision(match_result)
        self.assertEqual(result["recognition_decision"], "ambiguous")
        self.assertTrue(result["ambiguous"])
        self.assertEqual(result["top1_reference_id"], "A")
        self.assertEqual(result["top2_reference_id"], "B")
        self.assertAlmostEqual(result["score_margin"], 0.02)

    def test_decision_unrecognized_low_score(self):
        match_result = {
            "candidates": [
                {"reference_id": "A", "score": 0.70},
                {"reference_id": "B", "score": 0.68},
            ],
            "best_reference_id": "A",
            "confidence": 0.70,
        }
        
        result = apply_recognition_decision(match_result)
        self.assertEqual(result["recognition_decision"], "unrecognized")
        self.assertFalse(result["ambiguous"])
        self.assertEqual(result["top1_reference_id"], "A")
        self.assertEqual(result["top2_reference_id"], "B")
        self.assertAlmostEqual(result["score_margin"], 0.02)

    def test_decision_no_candidates(self):
        match_result = {
            "candidates": [],
            "best_reference_id": None,
            "confidence": 0.0,
        }
        
        result = apply_recognition_decision(match_result)
        self.assertEqual(result["recognition_decision"], "unrecognized")
        self.assertFalse(result["ambiguous"])
        self.assertIsNone(result["top1_reference_id"])
        self.assertEqual(result["top1_score"], 0.0)
        self.assertIsNone(result["top2_reference_id"])
        self.assertEqual(result["top2_score"], 0.0)
        self.assertEqual(result["score_margin"], 0.0)

    def test_tablestate_respects_ambiguous(self):
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(1920, 1080)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.91,
            "recognition_decision": "ambiguous",
            "ambiguous": True
        }
        position = {
            "bbox_px": [100, 100, 100, 150],
            "center_px": [150, 175]
        }
        card = state.add_card_from_recognition(
            detection_id="det_001",
            recognition_result=recognition_result,
            position=position
        )
        
        self.assertIsNotNone(card)
        self.assertEqual(card.status, "ambiguous")

    def test_tablestate_respects_unrecognized(self):
        state = TableState(session_dir=str(self.test_dir))
        state.set_table_size(1920, 1080)
        
        recognition_result = {
            "recognized_deck": "gilded",
            "best_reference_id": "Gilded_01",
            "mapping_status": "mapped",
            "confidence": 0.70,
            "recognition_decision": "unrecognized",
            "ambiguous": False
        }
        position = {
            "bbox_px": [100, 100, 100, 150],
            "center_px": [150, 175]
        }
        card = state.add_card_from_recognition(
            detection_id="det_002",
            recognition_result=recognition_result,
            position=position
        )
        
        self.assertIsNotNone(card)
        self.assertEqual(card.status, "unrecognized")

if __name__ == "__main__":
    unittest.main()

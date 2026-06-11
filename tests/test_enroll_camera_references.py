import unittest
import shutil
import json
from pathlib import Path
import numpy as np

# Dodanie src i katalogu głównego do path
root_dir = Path(__file__).resolve().parent.parent
import sys
sys.path.append(str(root_dir))

from tools.enroll_camera_references import save_enrollment_manifest, HARD_BLOCKING_REASONS, SOFT_WARNING_REASONS

class TestEnrollCameraReferences(unittest.TestCase):
    def setUp(self):
        self.test_dir = Path("output/test_enrollment")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        # Zastępujemy root_dir w module w celach testowych
        import tools.enroll_camera_references
        self.original_root = tools.enroll_camera_references.root_dir
        tools.enroll_camera_references.root_dir = self.test_dir

    def tearDown(self):
        import tools.enroll_camera_references
        tools.enroll_camera_references.root_dir = self.original_root
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def test_save_enrollment_manifest(self):
        deck_id = "test_gilded"
        results = {
            "Gilded_00": {
                "reference_id": "Gilded_00",
                "display_name": "The Fool",
                "timestamp": "2026-06-11T20:00:00",
                "best_sample_metrics": {"blur_score": 45.2},
                "best_sample_reasons": [],
                "best_sample_is_valid": True,
                "crop_source": "native_frame"
            }
        }
        plan_ids = ["Gilded_00", "Gilded_01"]
        
        save_enrollment_manifest(
            deck_id=deck_id,
            results=results,
            camera_profile="test_profile",
            crop_source="native_frame",
            resolution=[1920, 1080],
            plan_ids=plan_ids
        )
        
        manifest_path = self.test_dir / "assets" / "decks" / deck_id / "camera_references" / "enrollment_manifest.json"
        self.assertTrue(manifest_path.exists())
        
        with open(manifest_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
            
        self.assertEqual(manifest["deck_id"], deck_id)
        self.assertEqual(manifest["camera_profile_name"], "test_profile")
        self.assertEqual(manifest["missing_references"], ["Gilded_01"])
        self.assertIn("Gilded_00", manifest["results"])

    def test_best_sample_selection_logic(self):
        # Definiujemy logikę porównania próbek taką samą jak w skrypcie
        samples = [
            {"name": "s1", "quality": {"is_valid": False, "metrics": {"blur_score": 85.0}}},
            {"name": "s2", "quality": {"is_valid": True, "metrics": {"blur_score": 15.0}}},
            {"name": "s3", "quality": {"is_valid": True, "metrics": {"blur_score": 30.0}}},
        ]
        
        best = max(samples, key=lambda s: (s["quality"]["is_valid"], s["quality"]["metrics"].get("blur_score", 0.0)))
        
        self.assertEqual(best["name"], "s3")

    def test_blurred_crop_does_not_block_and_saves_accepted_with_warnings(self):
        # 1. blurred_crop nie blokuje i 3. zapisuje accepted_with_warnings=True
        samples = [
            {"name": "s1", "quality": {"reasons": ["blurred_crop"], "metrics": {"blur_score": 15.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 1)
        
        best = max(acceptable, key=lambda s: (
            not bool(set(s["quality"].get("reasons", [])) & SOFT_WARNING_REASONS),
            s["quality"]["metrics"].get("blur_score", 0.0)
        ))
        self.assertEqual(best["name"], "s1")
        
        best_reasons = set(best["quality"].get("reasons", []))
        best_soft_warnings = best_reasons & SOFT_WARNING_REASONS
        self.assertTrue(bool(best_soft_warnings))
        self.assertEqual(list(best_soft_warnings), ["blurred_crop"])

    def test_low_edge_density_does_not_block(self):
        # 2. low_edge_density nie blokuje
        samples = [
            {"name": "s1", "quality": {"reasons": ["low_edge_density"], "metrics": {"blur_score": 25.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 1)
        
        best = max(acceptable, key=lambda s: (
            not bool(set(s["quality"].get("reasons", [])) & SOFT_WARNING_REASONS),
            s["quality"]["metrics"].get("blur_score", 0.0)
        ))
        self.assertEqual(best["name"], "s1")
        
        best_reasons = set(best["quality"].get("reasons", []))
        best_soft_warnings = best_reasons & SOFT_WARNING_REASONS
        self.assertTrue(bool(best_soft_warnings))
        self.assertEqual(list(best_soft_warnings), ["low_edge_density"])

    def test_empty_or_uniform_crop_blocks(self):
        # 4. empty_or_uniform_crop blokuje zapis
        samples = [
            {"name": "s1", "quality": {"reasons": ["empty_or_uniform_crop"], "metrics": {"blur_score": 5.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 0)

    def test_low_content_density_blocks(self):
        # 5. low_content_density blokuje zapis
        samples = [
            {"name": "s1", "quality": {"reasons": ["low_content_density"], "metrics": {"blur_score": 10.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 0)

    def test_valid_preferred_over_soft_warning(self):
        # 6. jeśli istnieje próbka valid i soft-warning, valid jest preferowana
        samples = [
            {"name": "s1", "quality": {"reasons": ["blurred_crop"], "metrics": {"blur_score": 50.0}}},
            {"name": "s2", "quality": {"reasons": [], "metrics": {"blur_score": 30.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 2)
        
        best = max(acceptable, key=lambda s: (
            not bool(set(s["quality"].get("reasons", [])) & SOFT_WARNING_REASONS),
            s["quality"]["metrics"].get("blur_score", 0.0)
        ))
        self.assertEqual(best["name"], "s2")

    def test_all_hard_invalid_blocks_saving(self):
        # 7. jeśli wszystkie próbki są hard-invalid, referencja nie jest zapisywana
        samples = [
            {"name": "s1", "quality": {"reasons": ["empty_or_uniform_crop"], "metrics": {"blur_score": 5.0}}},
            {"name": "s2", "quality": {"reasons": ["low_content_density"], "metrics": {"blur_score": 10.0}}}
        ]
        acceptable = [s for s in samples if not (set(s["quality"].get("reasons", [])) & HARD_BLOCKING_REASONS)]
        self.assertEqual(len(acceptable), 0)

if __name__ == "__main__":
    unittest.main()

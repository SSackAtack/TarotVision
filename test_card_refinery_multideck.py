import unittest
import sys
import os
import cv2
import numpy as np
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.decks.profile import DeckProfile
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery

class TestCardRefineryMultiDeck(unittest.TestCase):
    def setUp(self):
        # Przygotowanie danych z sesji (detection_002)
        self.detections_dir = Path("output/sessions/current/detections/detection_002")
        self.output_dir = Path("output/processed")
        self.output_dir.mkdir(parents=True, exist_ok=True)

        if not self.detections_dir.exists():
            self.skipTest("Brak katalogu detekcji detection_002. Uruchom najpierw test z kamerą lub przygotuj dane diagnostyczne.")

        self.prev_img = cv2.imread(str(self.detections_dir / "previous.png"))
        self.curr_img = cv2.imread(str(self.detections_dir / "current.png"))
        
        self.diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
        self.refinery = CardRefinery(margin=20)
        
        # Wyciągamy ROI i maskę
        self.roi_rect, self.debug_mask = self.diff_detector.detect_change_roi(self.curr_img, self.prev_img)
        self.assertIsNotNone(self.roi_rect, "Nie udało się wyznaczyć ROI dla testów")

    def test_single_deck_matching(self):
        """Weryfikuje poprawne dopasowanie pojedynczej talii Gilded."""
        # Wczytujemy profil Gilded z biblioteki
        from tarotvision.decks.library import DeckLibrary
        library = DeckLibrary()
        profiles = library.load_active_profiles(["gilded"])
        self.assertEqual(len(profiles), 1)

        card_data = self.refinery.refine_card(
            self.curr_img,
            self.roi_rect,
            diff_mask=self.debug_mask,
            deck_profiles=profiles
        )
        
        self.assertIsNotNone(card_data)
        self.assertEqual(card_data["selected_geometry_profile"], "gilded")
        self.assertFalse(card_data["geometry_ambiguous"])
        self.assertEqual(card_data["frame_source"], "diff_mask_multi_deck_model_fit")
        self.assertAlmostEqual(max(card_data["size"]) / min(card_data["size"]), 1.720, places=1)

    def test_multi_deck_different_ratio(self):
        """Weryfikuje wybór profilu o optymalnym aspect ratio z zestawu dwóch różnych talii."""
        profile_a = DeckProfile({
            "deck_id": "deck_a",
            "deck_name": "Talia A (Proporcje 1.72)",
            "aspect_ratio_height_to_width": 1.720
        })
        profile_b = DeckProfile({
            "deck_id": "deck_b",
            "deck_name": "Talia B (Proporcje 1.40)",
            "aspect_ratio_height_to_width": 1.400
        })

        profiles = [profile_a, profile_b]

        card_data = self.refinery.refine_card(
            self.curr_img,
            self.roi_rect,
            diff_mask=self.debug_mask,
            deck_profiles=profiles
        )

        self.assertIsNotNone(card_data)
        # Powinien wybrać deck_a, ponieważ jego aspect ratio (1.720) jest bardzo bliskie wykrytemu
        self.assertEqual(card_data["selected_geometry_profile"], "deck_a")
        self.assertFalse(card_data["geometry_ambiguous"])

    def test_multi_deck_similar_ratio_ambiguous(self):
        """Weryfikuje poprawne oznaczenie niejednoznaczności geometrycznej dla podobnych proporcji."""
        profile_a = DeckProfile({
            "deck_id": "deck_a",
            "deck_name": "Talia A (Proporcje 1.72)",
            "aspect_ratio_height_to_width": 1.720
        })
        profile_b = DeckProfile({
            "deck_id": "deck_b",
            "deck_name": "Talia B (Proporcje 1.71)",
            "aspect_ratio_height_to_width": 1.710
        })

        profiles = [profile_a, profile_b]

        card_data = self.refinery.refine_card(
            self.curr_img,
            self.roi_rect,
            diff_mask=self.debug_mask,
            deck_profiles=profiles
        )

        self.assertIsNotNone(card_data)
        # Obie talie mają bardzo podobne aspect ratio (różnica 0.01 <= 0.02)
        # Zatem wynik musi zostać oznaczony jako niejednoznaczny
        self.assertTrue(card_data["geometry_ambiguous"])
        self.assertIn("deck_a", card_data["similar_geometry_profiles"])
        self.assertIn("deck_b", card_data["similar_geometry_profiles"])

if __name__ == "__main__":
    unittest.main()

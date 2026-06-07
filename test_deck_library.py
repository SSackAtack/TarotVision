import unittest
import sys
import os
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.decks.library import DeckLibrary
from tarotvision.decks.profile import DeckProfile

class TestDeckLibrary(unittest.TestCase):
    def setUp(self):
        self.library = DeckLibrary("assets/decks")

    def test_load_all_profiles(self):
        """Weryfikuje, czy biblioteka poprawnie wyszukuje i ładuje wszystkie profile talii."""
        profiles = self.library.load_all_profiles()
        
        # Oczekujemy, że profil 'gilded' istnieje i został załadowany
        self.assertIn("gilded", profiles)
        gilded = profiles["gilded"]
        self.assertEqual(gilded.deck_id, "gilded")
        self.assertEqual(gilded.deck_name, "Gilded")
        self.assertEqual(gilded.aspect_ratio_height_to_width, 1.720)

    def test_load_active_profiles_default(self):
        """Weryfikuje wczytanie aktywnych profili na podstawie active_decks.json."""
        active = self.library.load_active_profiles()
        
        # Oczekujemy na liście profilu gilded (zgodnie z active_decks.json)
        self.assertGreater(len(active), 0)
        active_ids = [p.deck_id for p in active]
        self.assertIn("gilded", active_ids)

    def test_load_active_profiles_custom(self):
        """Weryfikuje wczytanie podanej jawnie listy aktywnych profili."""
        active = self.library.load_active_profiles(["gilded"])
        self.assertEqual(len(active), 1)
        self.assertEqual(active[0].deck_id, "gilded")

if __name__ == "__main__":
    unittest.main()

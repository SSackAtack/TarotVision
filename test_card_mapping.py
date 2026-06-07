import os
import sys
import unittest
import shutil
import json
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.card_mapping import CardMappingLoader, enrich_recognition_with_card_mapping
from validate_card_mapping import validate_mapping

class TestCardMapping(unittest.TestCase):

    def setUp(self):
        self.test_dir = Path("output/test_card_mapping")
        self.test_dir.mkdir(parents=True, exist_ok=True)
        
        self.deck_id = "test_deck"
        self.deck_dir = self.test_dir / self.deck_id
        self.deck_dir.mkdir(parents=True, exist_ok=True)
        
        # Tworzenie poprawnego pliku mapowania
        self.valid_mapping = {
            "deck_id": self.deck_id,
            "mapping_version": "card_mapping_v1",
            "language": "en",
            "created_by": "test",
            "review_status": "needs_human_review",
            "cards": [
                {
                    "reference_id": "Card_01",
                    "entry_type": "tarot_card",
                    "card_id": "the_fool",
                    "display_name": "The Fool",
                    "arcana": "major",
                    "number": 0,
                    "suit": None,
                    "rank": None,
                    "is_deck_back": False,
                    "mapping_confidence": "high",
                    "needs_human_review": True,
                    "notes": ""
                },
                {
                    "reference_id": "Card_02",
                    "entry_type": "tarot_card",
                    "card_id": "ace_of_cups",
                    "display_name": "Ace of Cups",
                    "arcana": "minor",
                    "number": None,
                    "suit": "cups",
                    "rank": "ace",
                    "is_deck_back": False,
                    "mapping_confidence": "high",
                    "needs_human_review": True,
                    "notes": ""
                },
                {
                    "reference_id": "Card_back",
                    "entry_type": "deck_back",
                    "card_id": None,
                    "display_name": "Test Deck Back",
                    "arcana": "extra",
                    "number": None,
                    "suit": None,
                    "rank": None,
                    "is_deck_back": True,
                    "mapping_confidence": "high",
                    "needs_human_review": True,
                    "notes": "Rewers"
                }
            ]
        }
        
        self.write_json(self.deck_dir / "card_mapping.json", self.valid_mapping)

    def tearDown(self):
        if self.test_dir.exists():
            shutil.rmtree(self.test_dir)

    def write_json(self, path: Path, data: dict):
        with open(path, "w", encoding="utf-8") as f:
            json.dump(data, f, indent=2, ensure_ascii=False)

    def test_loader_loads_valid_mapping(self):
        loader = CardMappingLoader(base_decks_dir=str(self.test_dir))
        
        # 1. Sprawdzenie ładowania
        mapping = loader.load_mapping(self.deck_id)
        self.assertIsNotNone(mapping)
        self.assertEqual(mapping["deck_id"], self.deck_id)
        
        # 2. Sprawdzenie pobierania karty
        card1 = loader.get_card_by_reference_id(self.deck_id, "Card_01")
        self.assertIsNotNone(card1)
        self.assertEqual(card1["card_id"], "the_fool")
        
        # 3. Sprawdzenie pobierania rewersu
        back = loader.get_card_by_reference_id(self.deck_id, "Card_back")
        self.assertIsNotNone(back)
        self.assertTrue(back["is_deck_back"])
        self.assertEqual(back["entry_type"], "deck_back")

    def test_enrichment_logic(self):
        # Patching base_decks_dir w loaderze wewnątrz enrich
        # Ponieważ loader w enrich_recognition_with_card_mapping inicjuje się bezargumentowo,
        # tymczasowo zmieniamy domyślne ścieżki w CardMappingLoader
        original_init = CardMappingLoader.__init__
        test_base = str(self.test_dir)
        CardMappingLoader.__init__ = lambda s, base_decks_dir=test_base: original_init(s, base_decks_dir)
        
        try:
            # 1. Wzbogacenie dla standardowej karty
            res_card = {
                "recognized_deck": self.deck_id,
                "best_reference_id": "Card_01",
                "confidence": 0.9
            }
            res_card = enrich_recognition_with_card_mapping(res_card)
            self.assertEqual(res_card["mapping_status"], "mapped")
            self.assertEqual(res_card["recognized_card"]["card_id"], "the_fool")
            self.assertEqual(res_card["recognized_card"]["display_name"], "The Fool")
            
            # 2. Wzbogacenie dla rewersu
            res_back = {
                "recognized_deck": self.deck_id,
                "best_reference_id": "Card_back",
                "confidence": 0.95
            }
            res_back = enrich_recognition_with_card_mapping(res_back)
            self.assertEqual(res_back["mapping_status"], "deck_back")
            self.assertIsNone(res_back["recognized_card"])
            self.assertEqual(res_back["recognized_special"]["entry_type"], "deck_back")
            self.assertEqual(res_back["recognized_special"]["display_name"], "Test Deck Back")
            self.assertTrue(res_back["recognized_special"]["is_deck_back"])
            
            # 3. Wzbogacenie dla nieznanego reference_id
            res_unknown = {
                "recognized_deck": self.deck_id,
                "best_reference_id": "Card_nonexistent",
                "confidence": 0.5
            }
            res_unknown = enrich_recognition_with_card_mapping(res_unknown)
            self.assertEqual(res_unknown["mapping_status"], "unmapped_reference_id")
            self.assertIsNone(res_unknown["recognized_card"])
            
            # 4. Wzbogacenie w przypadku braku pliku mapowania
            res_no_file = {
                "recognized_deck": "nonexistent_deck",
                "best_reference_id": "Card_01",
                "confidence": 0.5
            }
            res_no_file = enrich_recognition_with_card_mapping(res_no_file)
            self.assertEqual(res_no_file["mapping_status"], "missing_mapping")
            self.assertIsNone(res_no_file["recognized_card"])
            
        finally:
            CardMappingLoader.__init__ = original_init

    def test_validator_detects_errors(self):
        # 1. Poprawny plik powinien przejść walidację
        self.assertTrue(validate_mapping(self.deck_id, base_decks_dir=str(self.test_dir)))
        
        # 2. Plik z duplikatem reference_id powinien zgłosić błąd
        invalid_mapping_dup = {
            "deck_id": self.deck_id,
            "cards": [
                {"reference_id": "Card_01", "entry_type": "tarot_card", "card_id": "fool", "display_name": "Fool", "mapping_confidence": "high"},
                {"reference_id": "Card_01", "entry_type": "tarot_card", "card_id": "magician", "display_name": "Magician", "mapping_confidence": "high"}
            ]
        }
        self.write_json(self.deck_dir / "card_mapping.json", invalid_mapping_dup)
        self.assertFalse(validate_mapping(self.deck_id, base_decks_dir=str(self.test_dir)))
        
        # 3. Plik z brakującym polem display_name powinien zgłosić błąd
        invalid_mapping_missing = {
            "deck_id": self.deck_id,
            "cards": [
                {"reference_id": "Card_01", "entry_type": "tarot_card", "card_id": "fool", "mapping_confidence": "high"}
            ]
        }
        self.write_json(self.deck_dir / "card_mapping.json", invalid_mapping_missing)
        self.assertFalse(validate_mapping(self.deck_id, base_decks_dir=str(self.test_dir)))

if __name__ == "__main__":
    unittest.main()

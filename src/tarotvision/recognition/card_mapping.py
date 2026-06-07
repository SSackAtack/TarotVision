import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CardMappingLoader:
    """Klasa odpowiedzialna za wczytywanie i wyszukiwanie mapowania semantycznego kart talii."""

    def __init__(self, base_decks_dir: str = "assets/decks"):
        self.base_decks_dir = Path(base_decks_dir)
        self._cache = {}  # Cache załadowanych mapowań: deck_id -> manifest dict

    def load_mapping(self, deck_id: str) -> dict:
        """
        Wczytuje plik card_mapping.json dla podanej talii.
        
        Args:
            deck_id: Identyfikator talii (np. 'gilded').
            
        Returns:
            Słownik z manifestem mapowania lub None, jeśli plik nie istnieje.
        """
        if deck_id in self._cache:
            return self._cache[deck_id]

        mapping_path = self.base_decks_dir / deck_id / "card_mapping.json"
        if not mapping_path.exists():
            logger.warning(f"Plik mapowania nie istnieje dla talii {deck_id} w: {mapping_path}")
            return None

        try:
            with open(mapping_path, "r", encoding="utf-8") as f:
                mapping = json.load(f)
            self._cache[deck_id] = mapping
            logger.info(f"Pomyślnie załadowano mapowanie dla talii {deck_id}.")
            return mapping
        except Exception as e:
            logger.error(f"Nie udało się załadować mapowania {mapping_path}: {e}")
            return None

    def get_card_by_reference_id(self, deck_id: str, reference_id: str) -> dict:
        """
        Wyszukuje wpis w mapowaniu na podstawie reference_id.
        
        Args:
            deck_id: Identyfikator talii.
            reference_id: Identyfikator techniczny skanu (np. 'Gilded_73').
            
        Returns:
            Słownik z danymi wpisu lub None, jeśli nie znaleziono lub brak mapowania.
        """
        mapping = self.load_mapping(deck_id)
        if not mapping or "cards" not in mapping:
            return None

        # Wyszukiwanie w liście kart
        for card in mapping["cards"]:
            if card.get("reference_id") == reference_id:
                return card

        return None


def enrich_recognition_with_card_mapping(result: dict, deck_id: str = None) -> dict:
    """
    Wzbogaca surowy wynik rozpoznawania o dane semantyczne z pliku mapowania.
    
    Args:
        result: Wynik dopasowania z matchera (ImageMatcher lub IndexedImageMatcher).
        deck_id: Opcjonalny identyfikator talii (jeśli None, brany jest z result['recognized_deck']).
        
    Returns:
        Zaktualizowany słownik result zawierający mapping_status oraz recognized_card/recognized_special.
    """
    active_deck = deck_id or result.get("recognized_deck")
    ref_id = result.get("best_reference_id")

    # Inicjalizacja domyślnych pól wyjściowych
    result["recognized_card"] = None
    if "recognized_special" in result:
        del result["recognized_special"]

    if not active_deck:
        logger.warning("Nie można wzbogacić wyniku - brak deck_id.")
        result["mapping_status"] = "missing_mapping"
        return result

    if not ref_id:
        result["mapping_status"] = "unmapped_reference_id"
        return result

    loader = CardMappingLoader()
    mapping = loader.load_mapping(active_deck)

    if not mapping:
        result["mapping_status"] = "missing_mapping"
        return result

    card_entry = loader.get_card_by_reference_id(active_deck, ref_id)

    if not card_entry:
        result["mapping_status"] = "unmapped_reference_id"
        return result

    entry_type = card_entry.get("entry_type")

    if entry_type == "tarot_card":
        result["recognized_card"] = {
            "card_id": card_entry.get("card_id"),
            "display_name": card_entry.get("display_name"),
            "arcana": card_entry.get("arcana"),
            "number": card_entry.get("number"),
            "suit": card_entry.get("suit"),
            "rank": card_entry.get("rank")
        }
        result["mapping_status"] = "mapped"
        
    elif entry_type == "deck_back":
        result["recognized_special"] = {
            "entry_type": "deck_back",
            "display_name": card_entry.get("display_name", "Deck Back"),
            "is_deck_back": True
        }
        result["mapping_status"] = "deck_back"
        
    else:
        # Dla typów "unknown" lub "extra_card"
        result["mapping_status"] = "unmapped_reference_id"

    return result

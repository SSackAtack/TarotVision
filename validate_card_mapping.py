import argparse
import sys
import json
import logging
from pathlib import Path

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

# Dodanie src do path
import os
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

def validate_mapping(deck_id: str, base_decks_dir: str = "assets/decks") -> bool:
    decks_path = Path(base_decks_dir)
    mapping_path = decks_path / deck_id / "card_mapping.json"
    
    print(f"=== TarotVision: Walidacja Mapowania Talii ({deck_id}) ===")
    
    if not mapping_path.exists():
        logger.error(f"Plik mapowania nie istnieje pod ścieżką: {mapping_path}")
        return False
        
    # 1. Wczytanie JSON
    try:
        with open(mapping_path, "r", encoding="utf-8") as f:
            manifest = json.load(f)
    except Exception as e:
        logger.error(f"Błąd składniowy JSON w pliku {mapping_path}: {e}")
        return False
        
    # 2. Weryfikacja głównych pól
    errors = 0
    warnings = 0
    
    if manifest.get("deck_id") != deck_id:
        logger.error(f"deck_id w pliku ({manifest.get('deck_id')}) nie zgadza się z oczekiwanym ({deck_id}).")
        errors += 1
        
    cards = manifest.get("cards")
    if not isinstance(cards, list):
        logger.error("Pole 'cards' musi być listą.")
        return False
        
    # Dozwolone zestawy wartości
    allowed_entry_types = {"tarot_card", "deck_back", "extra_card", "unknown"}
    allowed_arcana = {"major", "minor", "extra", "unknown"}
    allowed_suits = {"wands", "cups", "swords", "pentacles", None, "unknown"}
    allowed_ranks = {
        "ace", "two", "three", "four", "five", "six", "seven", "eight", "nine", "ten", 
        "page", "knight", "queen", "king", None, "unknown"
    }
    allowed_confidence = {"high", "medium", "low", "unknown"}
    
    # 3. Wczytanie faktycznych referencji dla spójności
    ref_ids_in_deck = set()
    manifest_index_path = decks_path / deck_id / "recognition_index" / "index_manifest.json"
    scans_dir = decks_path / deck_id / "reference_scans"
    
    if manifest_index_path.exists():
        try:
            with open(manifest_index_path, "r", encoding="utf-8") as f:
                index_manifest = json.load(f)
            ref_ids_in_deck = {ref["reference_id"] for ref in index_manifest.get("references", [])}
        except Exception:
            pass
            
    if not ref_ids_in_deck and scans_dir.exists():
        valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
        ref_ids_in_deck = {
            f.stem for f in scans_dir.iterdir() 
            if f.is_file() and f.suffix.lower() in valid_extensions and not f.name.startswith(".")
        }
        
    # 4. Walidacja rekordów po kolei
    seen_ref_ids = set()
    mapped_tarot_cards = 0
    mapped_deck_backs = 0
    mapped_unknowns = 0
    
    for idx, card in enumerate(cards):
        ref_id = card.get("reference_id")
        entry_type = card.get("entry_type")
        
        # Kluczowe pola obecne
        if not ref_id:
            logger.error(f"Wpis #{idx} nie posiada pola 'reference_id'.")
            errors += 1
            continue
            
        if not entry_type:
            logger.error(f"Wpis '{ref_id}' (index #{idx}) nie posiada pola 'entry_type'.")
            errors += 1
            continue
            
        # Duplikaty reference_id
        if ref_id in seen_ref_ids:
            logger.error(f"Zduplikowany wpis dla 'reference_id': {ref_id}.")
            errors += 1
        seen_ref_ids.add(ref_id)
        
        # entry_type poprawny
        if entry_type not in allowed_entry_types:
            logger.error(f"Wpis '{ref_id}': entry_type '{entry_type}' jest niedozwolony.")
            errors += 1
            
        # Spójność z plikami na dysku
        if ref_ids_in_deck and ref_id not in ref_ids_in_deck:
            logger.warning(f"Wpis '{ref_id}' jest zdefiniowany w mapowaniu, ale nie istnieje w skanach/indeksie talii.")
            warnings += 1
            
        # Walidacja szczegółowa w zależności od typu
        if entry_type == "tarot_card":
            mapped_tarot_cards += 1
            card_id = card.get("card_id")
            display_name = card.get("display_name")
            arcana = card.get("arcana")
            suit = card.get("suit")
            rank = card.get("rank")
            conf = card.get("mapping_confidence")
            
            if not card_id:
                logger.error(f"Karta '{ref_id}': 'card_id' nie może być puste.")
                errors += 1
            if not display_name:
                logger.error(f"Karta '{ref_id}': 'display_name' nie może być puste.")
                errors += 1
            if arcana not in allowed_arcana:
                logger.error(f"Karta '{ref_id}': arcana '{arcana}' jest niedozwolona.")
                errors += 1
            if suit not in allowed_suits:
                logger.error(f"Karta '{ref_id}': suit '{suit}' jest niedozwolony.")
                errors += 1
            if rank not in allowed_ranks:
                logger.error(f"Karta '{ref_id}': rank '{rank}' jest niedozwolony.")
                errors += 1
            if conf not in allowed_confidence:
                logger.error(f"Karta '{ref_id}': mapping_confidence '{conf}' jest niedozwolone.")
                errors += 1
                
        elif entry_type == "deck_back":
            mapped_deck_backs += 1
            if card.get("is_deck_back") is not True:
                logger.error(f"Rewers '{ref_id}': pole 'is_deck_back' musi mieć wartość true.")
                errors += 1
            if card.get("card_id") is not None:
                logger.warning(f"Rewers '{ref_id}': rewers nie powinien posiadać wartości 'card_id'.")
                warnings += 1
                
        elif entry_type == "unknown":
            mapped_unknowns += 1
            
        if card.get("needs_human_review") is not True:
            logger.warning(f"Wpis '{ref_id}': pole 'needs_human_review' powinno być ustawione na true do czasu weryfikacji.")
            warnings += 1

    # Podsumowanie
    print(f"\n--- Podsumowanie Walidacji ---")
    print(f"  Łączna liczba wpisów w pliku: {len(cards)}")
    print(f"  Zidentyfikowane karty tarota: {mapped_tarot_cards}")
    print(f"  Rewersy talii: {mapped_deck_backs}")
    print(f"  Wpisy nieznane/niepewne: {mapped_unknowns}")
    print(f"  Wykryte błędy (krytyczne): {errors}")
    print(f"  Wykryte ostrzeżenia: {warnings}")
    
    if errors > 0:
        logger.error("Walidacja zakończona niepowodzeniem z powodu krytycznych błędów.")
        return False
        
    print("[SUKCES] Plik mapowania jest poprawny strukturalnie i semantycznie.")
    return True

def main():
    parser = argparse.ArgumentParser(description="Walidator mapowania semantycznego kart TarotVision.")
    parser.add_argument("--deck", type=str, default="gilded", help="Identyfikator talii (domyślnie 'gilded').")
    args = parser.parse_args()
    
    success = validate_mapping(args.deck)
    sys.exit(0 if success else 1)

if __name__ == "__main__":
    main()

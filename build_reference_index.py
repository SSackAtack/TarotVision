import argparse
import sys
import os
import logging

# Dodanie src do path (na wypadek, gdyby skrypt był uruchamiany bezpośrednio)
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.index_builder import ReferenceIndexBuilder

# Konfiguracja logowania
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def main():
    parser = argparse.ArgumentParser(description="Budowanie indeksu cech talii kart referencyjnych dla TarotVision.")
    parser.add_argument("--deck", type=str, default="gilded", help="Identyfikator talii do indeksowania (domyślnie 'gilded').")
    args = parser.parse_args()
    
    deck_id = args.deck
    print(f"=== TarotVision: Budowanie Indeksu Cech Talii ({deck_id}) ===")
    
    builder = ReferenceIndexBuilder()
    success = builder.build_index(deck_id)
    
    if success:
        print("\n[SUKCES] Indeks został pomyślnie zbudowany i zapisany.")
        sys.exit(0)
    else:
        print("\n[BŁĄD] Wystąpił problem podczas budowania indeksu. Szczegóły w logach.")
        sys.exit(1)

if __name__ == "__main__":
    main()

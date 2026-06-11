import sys
import os
import argparse
import logging
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "..", "src"))

from tarotvision.recognition.index_builder import ReferenceIndexBuilder

# Skonfiguruj prosty logging
logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("build_recognition_index")

def main():
    parser = argparse.ArgumentParser(description="Narzędzie do budowania indeksu cech referencyjnych dla TarotVision.")
    parser.add_argument("--deck", required=True, help="Identyfikator talii (np. 'gilded').")
    parser.add_argument("--source-subdir", default="reference_scans", help="Nazwa podkatalogu z obrazami referencyjnymi.")
    parser.add_argument("--output-subdir", default="recognition_index", help="Nazwa podkatalogu wyjściowego na indeks cech.")
    parser.add_argument("--source-domain", choices=["scan", "camera"], default=None, 
                        help="Domena źródłowa obrazów (scan/camera). Domyślnie automatycznie: 'camera' jeśli podkatalog źródłowy to 'camera_references', inaczej 'scan'.")

    args = parser.parse_args()

    deck_id = args.deck
    source_subdir = args.source_subdir
    output_subdir = args.output_subdir
    
    # Automatyczne wyprowadzenie source_domain jeśli nie podano
    source_domain = args.source_domain
    if source_domain is None:
        source_domain = "camera" if source_subdir == "camera_references" else "scan"

    logger.info(f"Parametry budowania indeksu:")
    logger.info(f" - Talia: {deck_id}")
    logger.info(f" - Katalog źródłowy: {source_subdir}")
    logger.info(f" - Katalog docelowy: {output_subdir}")
    logger.info(f" - Domena źródłowa: {source_domain}")

    builder = ReferenceIndexBuilder(
        source_subdir=source_subdir,
        output_subdir=output_subdir,
        source_domain=source_domain
    )

    success = builder.build_index(deck_id)
    if not success:
        logger.error("Budowanie indeksu zakończyło się niepowodzeniem.")
        sys.exit(1)

    # Wypisanie podsumowania o plikach wynikowych
    index_dir = builder.base_decks_dir / deck_id / output_subdir
    manifest_path = index_dir / "index_manifest.json"
    features_path = index_dir / "features.npz"

    logger.info("Budowanie indeksu zakończone sukcesem!")
    logger.info(f"Pliki wynikowe:")
    logger.info(f" - Manifest: {manifest_path.resolve()}")
    logger.info(f" - Plik cech: {features_path.resolve()}")

if __name__ == "__main__":
    main()

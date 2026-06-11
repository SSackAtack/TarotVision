import os
import cv2
from pathlib import Path
import logging

logger = logging.getLogger(__name__)

class ReferenceLoader:
    """Klasa odpowiedzialna za wczytywanie skanów referencyjnych dla danej talii."""
    
    def __init__(self, base_decks_dir: str = "assets/decks"):
        self.base_decks_dir = Path(base_decks_dir)

    def load_references(self, deck_id: str, source_subdir: str = "reference_scans") -> list:
        """
        Wczytuje wszystkie obrazy referencyjne z wybranego katalogu aktywnej talii.
        Ignoruje pliki pomocnicze (np. ukryte lub .gitkeep).
        
        Args:
            deck_id: Identyfikator talii (np. 'gilded').
            source_subdir: Podkatalog, z którego mają być wczytane obrazy referencyjne.
            
        Returns:
            Lista słowników zawierających metadane i wczytany obraz referencyjny:
            [
                {
                    "reference_id": str,
                    "deck_id": str,
                    "path": Path,
                    "image": np.ndarray
                }
            ]
        """
        scans_dir = self.base_decks_dir / deck_id / source_subdir
        if not scans_dir.exists():
            logger.warning(f"Katalog referencyjny {scans_dir} nie istnieje.")
            return []

        references = []
        valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}

        for entry in sorted(scans_dir.iterdir()):
            if entry.is_file():
                # Ignorujemy pliki zaczynające się od kropki (np. .gitkeep) lub o złym rozszerzeniu
                if entry.name.startswith(".") or entry.suffix.lower() not in valid_extensions:
                    continue

                try:
                    img = cv2.imread(str(entry))
                    if img is None:
                        logger.warning(f"Nie udało się wczytać obrazu referencyjnego: {entry}")
                        continue
                    
                    reference_id = entry.stem
                    references.append({
                        "reference_id": reference_id,
                        "deck_id": deck_id,
                        "path": entry,
                        "image": img
                    })
                    logger.info(f"Pomyślnie załadowano referencję: {reference_id} ({deck_id})")
                except Exception as e:
                    logger.error(f"Błąd podczas wczytywania referencji {entry}: {e}")

        return references

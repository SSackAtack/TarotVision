import json
import logging
from pathlib import Path
import numpy as np

logger = logging.getLogger(__name__)

class ReferenceIndexLoader:
    """Klasa odpowiedzialna za wczytywanie zapisanego indeksu cech talii kart."""

    def __init__(self, base_decks_dir: str = "assets/decks"):
        self.base_decks_dir = Path(base_decks_dir)

    def load_index(self, deck_id: str) -> dict:
        """
        Wczytuje manifest oraz plik cech z katalogu indeksu danej talii.
        
        Args:
            deck_id: Identyfikator talii (np. 'gilded').
            
        Returns:
            Słownik z wczytanym indeksem lub None, jeśli indeks nie istnieje lub jest uszkodzony.
        """
        index_dir = self.base_decks_dir / deck_id / "recognition_index"
        manifest_path = index_dir / "index_manifest.json"
        
        if not manifest_path.exists():
            logger.warning(f"Manifest indeksu nie istnieje dla talii {deck_id} w: {manifest_path}")
            return None
            
        # 1. Wczytanie manifestu JSON
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                manifest = json.load(f)
        except Exception as e:
            logger.error(f"Nie udało się wczytać manifestu indeksu {manifest_path}: {e}")
            return None
            
        # 2. Wczytanie pliku cech (features.npz)
        features_file = manifest.get("features_file", "features.npz")
        features_path = index_dir / features_file
        
        if not features_path.exists():
            logger.warning(f"Plik cech indeksu nie istnieje: {features_path}")
            return None
            
        try:
            # Wczytanie za pomocą numpy
            with np.load(features_path, allow_pickle=True) as data:
                features = {
                    "reference_ids": data["reference_ids"].tolist(),
                    "deck_ids": data["deck_ids"].tolist(),
                    "gray_fingerprints": data["gray_fingerprints"],
                    "dhashes": data["dhashes"],
                    "gray_histograms": data["gray_histograms"],
                    "color_histograms": data["color_histograms"],
                    "region_fingerprints": data["region_fingerprints"]
                }
        except Exception as e:
            logger.error(f"Nie udało się wczytać pliku cech {features_path}: {e}")
            return None
            
        logger.info(f"Pomyślnie wczytano indeks dla talii {deck_id} ({len(features['reference_ids'])} referencji).")
        
        return {
            "manifest": manifest,
            "features": features
        }

import os
import json
import logging
from datetime import datetime
from pathlib import Path
import cv2
import numpy as np

from tarotvision.recognition.reference_loader import ReferenceLoader

logger = logging.getLogger(__name__)

class ReferenceIndexBuilder:
    """Klasa odpowiedzialna za budowanie indeksu cech talii kart referencyjnych."""

    def __init__(self, base_decks_dir: str = "assets/decks", 
                 canonical_width: int = 600, canonical_height: int = 1032):
        self.base_decks_dir = Path(base_decks_dir)
        self.canonical_width = canonical_width
        self.canonical_height = canonical_height
        
        # Konfiguracja ekstraktorów cech
        self.config_features = {
            "gray_fingerprint": {"enabled": True, "size": [64, 110]},
            "dhash": {"enabled": True, "size": [9, 8]},
            "gray_histogram": {"enabled": True, "bins": 64},
            "color_histogram": {"enabled": True, "space": "HSV", "bins": [8, 8, 8]},
            "region_fingerprints": {"enabled": True, "grid": [3, 3]}
        }

    def extract_features(self, img: np.ndarray) -> dict:
        """
        Ekstrahuje zestaw cech z obrazu karty (BGR).
        """
        features = {}

        # 0. Konwersje i preprocesowanie bazowe
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
            bgr = img.copy()
        else:
            gray = img.copy()
            bgr = cv2.cvtColor(img, cv2.COLOR_GRAY2BGR)

        # Dopasowanie do wymiaru kanonicznego
        gray_canon = cv2.resize(gray, (self.canonical_width, self.canonical_height))
        bgr_canon = cv2.resize(bgr, (self.canonical_width, self.canonical_height))
        
        # Wygładzenie Gaussa i normalizacja min-max (identyczna jak w preprocesie ImageMatchera)
        blurred = cv2.GaussianBlur(gray_canon, (5, 5), 0)
        norm_gray = cv2.normalize(blurred, None, 0, 255, cv2.NORM_MINMAX)

        # 1. gray_fingerprint
        size_fg = self.config_features["gray_fingerprint"]["size"]
        resized_fg = cv2.resize(norm_gray, (size_fg[0], size_fg[1]))
        features["gray_fingerprint"] = resized_fg.flatten().astype(np.float32)

        # 2. dhash
        size_dh = self.config_features["dhash"]["size"]
        resized_dh = cv2.resize(norm_gray, (size_dh[0], size_dh[1]))
        diff = resized_dh[:, 1:] > resized_dh[:, :-1]
        features["dhash"] = diff.flatten().astype(np.bool_)

        # 3. gray_histogram
        bins_gray = self.config_features["gray_histogram"]["bins"]
        hist_gray = cv2.calcHist([norm_gray], [0], None, [bins_gray], [0, 256])
        hist_gray = hist_gray / (np.sum(hist_gray) + 1e-6)
        features["gray_histogram"] = hist_gray.flatten().astype(np.float32)

        # 4. color_histogram
        hsv = cv2.cvtColor(bgr_canon, cv2.COLOR_BGR2HSV)
        bins_color = self.config_features["color_histogram"]["bins"]
        hist_color = cv2.calcHist([hsv], [0, 1, 2], None, bins_color, [0, 180, 0, 256, 0, 256])
        hist_color = hist_color / (np.sum(hist_color) + 1e-6)
        features["color_histogram"] = hist_color.flatten().astype(np.float32)

        # 5. region_fingerprints
        grid = self.config_features["region_fingerprints"]["grid"]
        r_cols, r_rows = grid[0], grid[1]
        w_step = self.canonical_width // r_cols
        h_step = self.canonical_height // r_rows
        
        region_fgs = []
        for r in range(r_rows):
            for c in range(r_cols):
                y_start = r * h_step
                y_end = (r + 1) * h_step
                x_start = c * w_step
                x_end = (c + 1) * w_step
                
                region = norm_gray[y_start:y_end, x_start:x_end]
                # Downsample regionu do 16x16 i normalizacja min-max
                reg_resized = cv2.resize(region, (16, 16))
                reg_norm = cv2.normalize(reg_resized, None, 0, 255, cv2.NORM_MINMAX)
                region_fgs.append(reg_norm.flatten())
                
        features["region_fingerprints"] = np.array(region_fgs, dtype=np.float32) # (9, 256)

        return features

    def build_index(self, deck_id: str) -> bool:
        """
        Buduje indeks cech dla danej talii i zapisuje pliki na dysku.
        """
        logger.info(f"Rozpoczynam budowanie indeksu cech dla talii: {deck_id}")
        
        # 1. Wczytanie obrazów referencyjnych przez ReferenceLoader
        loader = ReferenceLoader(base_decks_dir=str(self.base_decks_dir))
        references = loader.load_references(deck_id)
        
        if not references:
            logger.error(f"Nie znaleziono skanów referencyjnych dla talii {deck_id}.")
            return False
            
        logger.info(f"Pomyślnie załadowano {len(references)} referencji. Rozpoczynam ekstrakcję cech...")
        
        # 2. Inicjalizacja list cech
        ref_ids = []
        source_paths = []
        
        gray_fingerprints = []
        dhashes = []
        gray_histograms = []
        color_histograms = []
        region_fingerprints = []
        
        # 3. Ekstrakcja cech w pętli
        for ref in references:
            ref_id = ref["reference_id"]
            img = ref["image"]
            
            try:
                feats = self.extract_features(img)
                
                ref_ids.append(ref_id)
                # Zapisujemy relatywną ścieżkę do skanu referencyjnego
                rel_path = f"reference_scans/{ref_id}{Path(ref['path']).suffix}"
                source_paths.append(rel_path)
                
                gray_fingerprints.append(feats["gray_fingerprint"])
                dhashes.append(feats["dhash"])
                gray_histograms.append(feats["gray_histogram"])
                color_histograms.append(feats["color_histogram"])
                region_fingerprints.append(feats["region_fingerprints"])
                
            except Exception as e:
                logger.error(f"Błąd podczas ekstrakcji cech dla referencji {ref_id}: {e}")
                return False
                
        # 4. Tworzenie katalogu indeksu
        index_dir = self.base_decks_dir / deck_id / "recognition_index"
        index_dir.mkdir(parents=True, exist_ok=True)
        
        # 5. Przygotowanie i zapis features.npz
        features_path = index_dir / "features.npz"
        try:
            np.savez_compressed(
                features_path,
                reference_ids=np.array(ref_ids),
                deck_ids=np.array([deck_id] * len(ref_ids)),
                gray_fingerprints=np.array(gray_fingerprints),
                dhashes=np.array(dhashes),
                gray_histograms=np.array(gray_histograms),
                color_histograms=np.array(color_histograms),
                region_fingerprints=np.array(region_fingerprints)
            )
            logger.info(f"Pomyślnie zapisano cechy w: {features_path}")
        except Exception as e:
            logger.error(f"Nie udało się zapisać pliku cech {features_path}: {e}")
            return False
            
        # 6. Przygotowanie i zapis index_manifest.json
        manifest = {
            "index_type": "reference_deck_recognition_index",
            "index_version": "recognition_index_v1",
            "deck_id": deck_id,
            "created_at": datetime.now().isoformat(),
            "canonical_size": [self.canonical_width, self.canonical_height],
            "source_scan_dir": f"assets/decks/{deck_id}/reference_scans",
            "features_file": "features.npz",
            "feature_extractors": self.config_features,
            "references": [
                {
                    "reference_id": ref_id,
                    "deck_id": deck_id,
                    "source_path": path
                }
                for ref_id, path in zip(ref_ids, source_paths)
            ],
            "source_scans_count": len(ref_ids)
        }
        
        manifest_path = index_dir / "index_manifest.json"
        try:
            with open(manifest_path, "w", encoding="utf-8") as f:
                json.dump(manifest, f, indent=2, ensure_ascii=False)
            logger.info(f"Pomyślnie zapisano manifest indeksu w: {manifest_path}")
        except Exception as e:
            logger.error(f"Nie udało się zapisać manifestu {manifest_path}: {e}")
            return False
            
        logger.info(f"Budowanie indeksu dla {deck_id} zakończone sukcesem.")
        return True

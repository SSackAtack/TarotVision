import logging
import cv2
import numpy as np

from tarotvision.recognition.index_builder import ReferenceIndexBuilder

logger = logging.getLogger(__name__)

class IndexedImageMatcher:
    """Matcher kart porównujący cropa z cechami z zapisanego indeksu referencyjnego."""

    def __init__(self, index: dict, weights: dict = None):
        """
        Inicjalizacja matchera indeksowego.
        
        Args:
            index: Słownik wczytany przez ReferenceIndexLoader zawierający 'manifest' i 'features'.
            weights: Słownik z wagami poszczególnych cech (opcjonalny).
        """
        self.index = index
        self.manifest = index["manifest"]
        self.features = index["features"]
        
        # Pobranie wymiarów kanonicznych z manifestu
        canon_size = self.manifest.get("canonical_size", [600, 1032])
        self.canonical_width = canon_size[0]
        self.canonical_height = canon_size[1]
        
        # Inicjalizacja buildera do wyciągania cech z cropów w locie
        self.builder = ReferenceIndexBuilder(
            canonical_width=self.canonical_width, 
            canonical_height=self.canonical_height
        )
        
        # Domyślne wagi dla scoringu
        self.weights = weights or {
            "gray_fingerprint": 0.40,
            "region_fingerprints": 0.25,
            "color_histogram": 0.15,
            "gray_histogram": 0.10,
            "dhash": 0.10
        }
        
        # Normalizacja wag (na wypadek gdyby suma nie wynosiła 1.0)
        total_w = sum(self.weights.values())
        if abs(total_w - 1.0) > 1e-6:
            for k in self.weights:
                self.weights[k] /= total_w

    def match_card(self, crop_image: np.ndarray, session_color_profile: dict = None) -> dict:
        """
        Dopasowuje crop karty do zapisanego indeksu cech.
        
        Args:
            crop_image: Obraz wyciętej karty (BGR).
            session_color_profile: Profil kalibracji barw (opcjonalny).
            
        Returns:
            Wynik dopasowania w formacie JSON (dict).
        """
        deck_id = self.manifest.get("deck_id", "unknown")
        
        # 1. Opcjonalna aplikacja profilu kalibracji kolorów z TV-013
        if session_color_profile:
            from tarotvision.recognition.session_color_calibration import apply_color_profile
            crop_image = apply_color_profile(crop_image, session_color_profile)
            session_color_profile_used = True
        else:
            session_color_profile_used = False

        # 2. Wyodrębnienie cech dla cropa w orientacji 0 i 180 stopni
        crop_feats_0 = self.builder.extract_features(crop_image)
        
        crop_180 = cv2.rotate(crop_image, cv2.ROTATE_180)
        crop_feats_180 = self.builder.extract_features(crop_180)
        
        # 3. Odczytanie cech referencyjnych z indeksu
        ref_ids = self.features["reference_ids"]
        ref_deck_ids = self.features["deck_ids"]
        
        ref_fgs = self.features["gray_fingerprints"]
        ref_dhashes = self.features["dhashes"]
        ref_ghists = self.features["gray_histograms"]
        ref_chists = self.features["color_histograms"]
        ref_rfgs = self.features["region_fingerprints"]
        
        N = len(ref_ids)
        
        # 4. Obliczenie odległości wektorowo dla obu rotacji
        # --- OBRÓT 0° ---
        # gray_fingerprint (MAE)
        mae_fg_0 = np.mean(np.abs(ref_fgs - crop_feats_0["gray_fingerprint"]), axis=1)
        sim_fg_0 = 1.0 - (mae_fg_0 / 255.0)
        
        # region_fingerprints (Średni MAE po 9 regionach)
        mae_rfg_0 = np.mean(np.abs(ref_rfgs - crop_feats_0["region_fingerprints"]), axis=2)
        mae_rfg_mean_0 = np.mean(mae_rfg_0, axis=1)
        sim_rfg_0 = 1.0 - (mae_rfg_mean_0 / 255.0)
        
        # gray_histogram (L1 distance)
        l1_ghist_0 = np.sum(np.abs(ref_ghists - crop_feats_0["gray_histogram"]), axis=1)
        sim_ghist_0 = 1.0 - (l1_ghist_0 / 2.0)
        
        # color_histogram (L1 distance)
        l1_chist_0 = np.sum(np.abs(ref_chists - crop_feats_0["color_histogram"]), axis=1)
        sim_chist_0 = 1.0 - (l1_chist_0 / 2.0)
        
        # dhash (Hamming distance)
        hamming_0 = np.sum(np.bitwise_xor(ref_dhashes, crop_feats_0["dhash"]), axis=1)
        sim_dh_0 = 1.0 - (hamming_0 / 64.0)
        
        # --- OBRÓT 180° ---
        # gray_fingerprint (MAE)
        mae_fg_180 = np.mean(np.abs(ref_fgs - crop_feats_180["gray_fingerprint"]), axis=1)
        sim_fg_180 = 1.0 - (mae_fg_180 / 255.0)
        
        # region_fingerprints (Średni MAE po 9 regionach)
        mae_rfg_180 = np.mean(np.abs(ref_rfgs - crop_feats_180["region_fingerprints"]), axis=2)
        mae_rfg_mean_180 = np.mean(mae_rfg_180, axis=1)
        sim_rfg_180 = 1.0 - (mae_rfg_mean_180 / 255.0)
        
        # gray_histogram (L1 distance)
        l1_ghist_180 = np.sum(np.abs(ref_ghists - crop_feats_180["gray_histogram"]), axis=1)
        sim_ghist_180 = 1.0 - (l1_ghist_180 / 2.0)
        
        # color_histogram (L1 distance)
        l1_chist_180 = np.sum(np.abs(ref_chists - crop_feats_180["color_histogram"]), axis=1)
        sim_chist_180 = 1.0 - (l1_chist_180 / 2.0)
        
        # dhash (Hamming distance)
        hamming_180 = np.sum(np.bitwise_xor(ref_dhashes, crop_feats_180["dhash"]), axis=1)
        sim_dh_180 = 1.0 - (hamming_180 / 64.0)

        # 5. Wyznaczenie ważonego wyniku końcowego dla każdego kandydata
        candidates = []
        for i in range(N):
            # Suma ważona dla 0°
            score_0 = (
                self.weights["gray_fingerprint"] * sim_fg_0[i] +
                self.weights["region_fingerprints"] * sim_rfg_0[i] +
                self.weights["color_histogram"] * sim_chist_0[i] +
                self.weights["gray_histogram"] * sim_ghist_0[i] +
                self.weights["dhash"] * sim_dh_0[i]
            )
            
            # Suma ważona dla 180°
            score_180 = (
                self.weights["gray_fingerprint"] * sim_fg_180[i] +
                self.weights["region_fingerprints"] * sim_rfg_180[i] +
                self.weights["color_histogram"] * sim_chist_180[i] +
                self.weights["gray_histogram"] * sim_ghist_180[i] +
                self.weights["dhash"] * sim_dh_180[i]
            )
            
            # Wybieramy lepszy obrót
            if score_0 >= score_180:
                best_score = score_0
                best_rot = 0
                breakdown = {
                    "gray_fingerprint": float(sim_fg_0[i]),
                    "region_fingerprints": float(sim_rfg_0[i]),
                    "color_histogram": float(sim_chist_0[i]),
                    "gray_histogram": float(sim_ghist_0[i]),
                    "dhash": float(sim_dh_0[i])
                }
            else:
                best_score = score_180
                best_rot = 180
                breakdown = {
                    "gray_fingerprint": float(sim_fg_180[i]),
                    "region_fingerprints": float(sim_rfg_180[i]),
                    "color_histogram": float(sim_chist_180[i]),
                    "gray_histogram": float(sim_ghist_180[i]),
                    "dhash": float(sim_dh_180[i])
                }
                
            candidates.append({
                "reference_id": ref_ids[i],
                "deck_id": ref_deck_ids[i],
                "score": float(round(best_score, 4)),
                "rotation": best_rot,
                "score_breakdown": {k: float(round(v, 4)) for k, v in breakdown.items()}
            })
            
        # Sortowanie kandydatów według score malejąco
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        best = candidates[0]
        
        result = {
            "recognized_deck": best["deck_id"],
            "recognized_card": None, # Pozostaje null zgodnie z zakresem TV-014
            "best_reference_id": best["reference_id"],
            "confidence": best["score"],
            "method": "indexed_visual_similarity_v1",
            "best_rotation": best["rotation"],
            "candidates": candidates,
            "session_color_profile_used": session_color_profile_used
        }
        
        from tarotvision.recognition.decision import apply_recognition_decision
        return apply_recognition_decision(result)

import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class ImageMatcher:
    """Klasa implementująca algorytm dopasowania wizualnego kart (Visual Similarity)."""
    
    def __init__(self, target_width: int = 600, target_height: int = 1032, session_color_profile: dict = None):
        self.target_width = target_width
        self.target_height = target_height
        self.session_color_profile = session_color_profile

    def _preprocess(self, img: np.ndarray) -> np.ndarray:
        """
        Znormalizowanie obrazu: skala szarości, resize, wygładzenie Gaussa, normalizacja jasności.
        """
        # 1. Konwersja do skali szarości
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
            
        # 2. Zmiana rozmiaru do formatu kanonicznego
        resized = cv2.resize(gray, (self.target_width, self.target_height))
        
        # 3. Wygładzenie Gaussa (filtracja drobnych szumów)
        blurred = cv2.GaussianBlur(resized, (5, 5), 0)
        
        # 4. Normalizacja jasności (min-max normalization do zakresu 0-255)
        normalized = cv2.normalize(blurred, None, 0, 255, cv2.NORM_MINMAX)
        
        return normalized

    def match_card(self, crop_image: np.ndarray, reference_images: list, deck_id: str = None) -> dict:
        """
        Porównuje crop karty ze wszystkimi skanami referencyjnymi.
        Sprawdza orientację 0° i 180° dla każdego skanu.
        
        Args:
            crop_image: Obraz wyciętej karty (numpy array).
            reference_images: Lista wczytanych referencji z ReferenceLoader.
            deck_id: Opcjonalny identyfikator preferowanej talii.
            
        Returns:
            Słownik z wynikami dopasowania w formacie JSON.
        """
        if not reference_images:
            logger.warning("Brak obrazów referencyjnych do porównania.")
            result = {
                "recognized_deck": deck_id,
                "recognized_card": None,
                "best_reference_id": None,
                "confidence": 0.0,
                "method": "visual_similarity_v1",
                "best_rotation": 0,
                "candidates": []
            }
            from tarotvision.recognition.decision import apply_recognition_decision
            return apply_recognition_decision(result)

        # Opcjonalna korekcja koloru z profilu sesyjnego przed dopasowaniem
        if self.session_color_profile:
            from tarotvision.recognition.session_color_calibration import apply_color_profile
            crop_image = apply_color_profile(crop_image, self.session_color_profile)

        # Preprocesowanie cropa wejściowego
        crop_norm = self._preprocess(crop_image)
        crop_norm_180 = cv2.rotate(crop_norm, cv2.ROTATE_180)
        
        candidates = []
        
        for ref in reference_images:
            ref_norm = self._preprocess(ref["image"])
            
            # Wariant 0 stopni (normalny)
            diff_0 = cv2.absdiff(crop_norm, ref_norm)
            mae_0 = np.mean(diff_0) / 255.0
            score_0 = float(1.0 - mae_0)
            
            # Wariant 180 stopni (odwrócony)
            diff_180 = cv2.absdiff(crop_norm_180, ref_norm)
            mae_180 = np.mean(diff_180) / 255.0
            score_180 = float(1.0 - mae_180)
            
            # Wybieramy lepszy obrót
            if score_0 >= score_180:
                best_score = score_0
                best_rot = 0
            else:
                best_score = score_180
                best_rot = 180
                
            candidates.append({
                "reference_id": ref["reference_id"],
                "deck_id": ref["deck_id"],
                "score": round(best_score, 4),
                "rotation": best_rot
            })

        # Sortowanie kandydatów według score malejąco
        candidates.sort(key=lambda x: x["score"], reverse=True)
        
        best = candidates[0]
        
        result = {
            "recognized_deck": best["deck_id"],
            "recognized_card": None,
            "best_reference_id": best["reference_id"],
            "confidence": best["score"],
            "method": "visual_similarity_v1",
            "best_rotation": best["rotation"],
            "candidates": candidates
        }
        
        from tarotvision.recognition.decision import apply_recognition_decision
        return apply_recognition_decision(result)

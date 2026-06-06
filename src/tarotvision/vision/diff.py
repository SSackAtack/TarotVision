import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class DiffDetector:
    """Klasa odpowiedzialna za wykrywanie obszaru zmian (ROI karty) na podstawie różnic obrazów."""

    def __init__(self, diff_threshold: int = 30, min_area: int = 8000, max_area: int = 150000):
        """
        Inicjalizacja detektora różnicowego.

        :param diff_threshold: Próg różnicy jasności pikseli (0-255) do binaryzacji.
        :param min_area: Minimalna powierzchnia zmiany w pikselach, uznawana za kartę.
        :param max_area: Maksymalna powierzchnia zmiany w pikselach.
        """
        self.diff_threshold = diff_threshold
        self.min_area = min_area
        self.max_area = max_area

    def detect_change_roi(self, current_frame, reference_frame) -> tuple[tuple | None, np.ndarray]:
        """
        Porównuje dwie klatki i wyznacza obrócony prostokąt (minAreaRect) obszaru zmiany (karty).

        :param current_frame: Aktualny snapshot BGR (np. Snapshot_N).
        :param reference_frame: Referencyjny snapshot BGR (np. Snapshot_0 lub Snapshot_N-1).
        :return: Krotka (minAreaRect, debug_mask).
                 - minAreaRect: ((cx, cy), (w, h), angle) lub None, jeśli nie wykryto odpowiedniej zmiany.
                 - debug_mask: Maska binarna zmian (po operacjach morfologicznych).
        """
        if current_frame is None or reference_frame is None:
            logger.warning("Jedna z klatek wejściowych do detektora różnicowego jest None.")
            return None, np.zeros((100, 100), dtype=np.uint8)

        # 1. Bezwzględna różnica klatek
        diff = cv2.absdiff(current_frame, reference_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        
        # 2. Rozmycie i progowanie
        blurred = cv2.GaussianBlur(gray_diff, (9, 9), 0)
        _, thresh = cv2.threshold(blurred, self.diff_threshold, 255, cv2.THRESH_BINARY)
        
        # 3. Czyszczenie morfologiczne
        # Otwarcie usuwa drobny szum
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open)
        
        # Domknięcie łączy fragmenty karty w spójny kształt
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close)
        
        # Dylatacja w celu pewnego pokrycia krawędzi karty
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_final = cv2.dilate(closed, kernel_dilate, iterations=1)
        
        # 4. Wyszukiwanie konturów na masce binarnej
        contours, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_rect = None
        max_area = 0
        
        for c in contours:
            area = cv2.contourArea(c)
            
            # Filtrujemy po powierzchni
            if self.min_area <= area <= self.max_area:
                if area > max_area:
                    max_area = area
                    # minAreaRect daje ((cx, cy), (w, h), angle)
                    best_rect = cv2.minAreaRect(c)
                    
        if best_rect is not None:
            (cx, cy), (w, h), angle = best_rect
            logger.info(f"Wykryto obszar różnicy: Center=({cx:.1f}, {cy:.1f}), Dim=({w:.1f}, {h:.1f}), Pole={max_area:.1f}")
        else:
            logger.warning("Nie wykryto żadnego stabilnego obszaru zmian o oczekiwanym polu powierzchni.")
            
        return best_rect, mask_final

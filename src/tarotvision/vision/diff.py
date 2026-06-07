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
        """
        best_rect, mask_final, _ = self.detect_change_roi_with_debug(current_frame, reference_frame)
        return best_rect, mask_final

    def detect_change_roi_with_debug(self, current_frame, reference_frame) -> tuple[tuple | None, np.ndarray, dict]:
        """
        Porównuje dwie klatki, wyznacza ROI zmiany oraz zbiera szczegółowe metryki diagnostyczne.

        :param current_frame: Aktualny snapshot BGR.
        :param reference_frame: Referencyjny snapshot BGR.
        :return: Krotka (best_rect, mask_final, diff_debug).
        """
        diff_debug = {
            "diff_threshold": int(self.diff_threshold),
            "min_area": float(self.min_area),
            "max_area": float(self.max_area),
            "contours_count": 0,
            "accepted": False,
            "accepted_area": None,
            "accepted_rect": None,
            "accepted_bbox": None,
            "rejected_contours": []
        }

        if current_frame is None or reference_frame is None:
            logger.warning("Jedna z klatek wejściowych do detektora różnicowego jest None.")
            return None, np.zeros((100, 100), dtype=np.uint8), diff_debug

        # 1. Bezwzględna różnica klatek
        diff = cv2.absdiff(current_frame, reference_frame)
        gray_diff = cv2.cvtColor(diff, cv2.COLOR_BGR2GRAY)
        
        # 2. Rozmycie i progowanie
        blurred = cv2.GaussianBlur(gray_diff, (9, 9), 0)
        _, thresh = cv2.threshold(blurred, self.diff_threshold, 255, cv2.THRESH_BINARY)
        
        # 3. Czyszczenie morfologiczne
        kernel_open = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        opened = cv2.morphologyEx(thresh, cv2.MORPH_OPEN, kernel_open)
        
        kernel_close = cv2.getStructuringElement(cv2.MORPH_RECT, (15, 15))
        closed = cv2.morphologyEx(opened, cv2.MORPH_CLOSE, kernel_close)
        
        kernel_dilate = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        mask_final = cv2.dilate(closed, kernel_dilate, iterations=1)
        
        # 4. Wyszukiwanie konturów
        contours, _ = cv2.findContours(mask_final, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        contours_data = []
        for c in contours:
            area = float(cv2.contourArea(c))
            contours_data.append((c, area))
            
        # Sortowanie po polu powierzchni malejąco
        contours_data.sort(key=lambda x: x[1], reverse=True)
        
        best_rect = None
        best_area = 0.0
        best_contour = None
        rejected_list = []
        
        for c, area in contours_data:
            if self.min_area <= area <= self.max_area:
                if best_rect is None:
                    best_rect = cv2.minAreaRect(c)
                    best_area = area
                    best_contour = c
                else:
                    rejected_list.append({
                        "area": area,
                        "reason": "valid_but_not_largest"
                    })
            elif area < self.min_area:
                rejected_list.append({
                    "area": area,
                    "reason": "area_below_min"
                })
            else:
                rejected_list.append({
                    "area": area,
                    "reason": "area_above_max"
                })
                
        accepted = best_rect is not None
        accepted_rect_json = None
        accepted_bbox_json = None
        
        if accepted:
            (cx, cy), (w, h), angle = best_rect
            accepted_rect_json = {
                "center": [float(cx), float(cy)],
                "size": [float(w), float(h)],
                "angle": float(angle)
            }
            box_pts = cv2.boxPoints(best_rect)
            bx, by, bw, bh = cv2.boundingRect(np.intp(box_pts))
            accepted_bbox_json = [int(bx), int(by), int(bw), int(bh)]
            
            logger.info(f"Wykryto obszar różnicy: Center=({cx:.1f}, {cy:.1f}), Dim=({w:.1f}, {h:.1f}), Pole={best_area:.1f}")
        else:
            logger.warning("Nie wykryto żadnego stabilnego obszaru zmian o oczekiwanym polu powierzchni.")
            
        diff_debug.update({
            "contours_count": len(contours),
            "accepted": accepted,
            "accepted_area": float(best_area) if accepted else None,
            "accepted_rect": accepted_rect_json,
            "accepted_bbox": accepted_bbox_json,
            "rejected_contours": rejected_list
        })
        
        return best_rect, mask_final, diff_debug

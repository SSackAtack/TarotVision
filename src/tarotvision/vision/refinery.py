import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class CardRefinery:
    """Klasa odpowiedzialna za precyzyjne odnajdywanie krawędzi i rogów karty wewnątrz wyznaczonego ROI."""

    def __init__(self, margin: int = 25):
        """
        Inicjalizacja refinery.

        :param margin: Margines w pikselach dodawany wokół ROI przed precyzyjną analizą.
        """
        self.margin = margin

    def refine_card(self, image, roi_rect) -> dict | None:
        """
        Precyzyjnie lokalizuje kartę wewnątrz ROI i zwraca jej metadane.

        :param image: Pełny wyprostowany obraz stołu BGR (1200x800).
        :param roi_rect: Prostokąt obrócony ((cx, cy), (w, h), angle) z detektora różnicowego.
        :return: Słownik z danymi geometrycznymi karty (corners, center, size, angle) lub None.
        """
        if image is None or roi_rect is None:
            return None

        img_h, img_w = image.shape[:2]

        # 1. Obliczenie bounding boxu dla prostokąta obróconego
        box_pts = cv2.boxPoints(roi_rect)
        box_pts = np.intp(box_pts)
        
        x, y, w, h = cv2.boundingRect(box_pts)
        
        # 2. Wycięcie ROI z marginesem
        x_start = max(0, x - self.margin)
        y_start = max(0, y - self.margin)
        x_end = min(img_w, x + w + self.margin)
        y_end = min(img_h, y + h + self.margin)
        
        if (x_end - x_start) <= 0 or (y_end - y_start) <= 0:
            return None
            
        roi_img = image[y_start:y_end, x_start:x_end]
        
        # 3. Przetwarzanie wyciętego ROI
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        
        # Rozmycie medianowe doskonale radzi sobie z drobnym szumem karty i tła
        blurred = cv2.medianBlur(gray, 7)
        
        # Progowanie Otsu - szukamy podziału na ciemne tło stołu (wokół karty) i jasną kartę
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        # Jeśli tło jest jaśniejsze niż karta (rzadkie, ale możliwe), sprawdzamy rogi
        # Zakładamy, że rogi wycinka ROI to tło stołu. Jeśli większość pikseli w rogach
        # wycinka ma wartość 255 (białe), to odwracamy maskę.
        corner_pixels = [thresh[0, 0], thresh[0, -1], thresh[-1, 0], thresh[-1, -1]]
        if sum(corner_pixels) > 510: # Więcej niż 2 piksele narożne są białe
            thresh = cv2.bitwise_not(thresh)
            
        # Domknięcie morfologiczne w celu wygładzenia krawędzi karty
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # 4. Wyszukiwanie konturów wewnątrz wycinka ROI
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_contour = None
        max_area = 0
        
        for c in contours:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = area
                best_contour = c
                
        if best_contour is None or max_area < 5000:
            logger.warning("Nie znaleziono odpowiednio dużego konturu karty wewnątrz wyciętego ROI.")
            return None
            
        # 5. Dopasowanie prostokąta obróconego do najlepszego konturu w ROI
        rect = cv2.minAreaRect(best_contour)
        (cx_local, cy_local), (w_card, h_card), angle = rect
        
        # Wierzchołki prostokąta obróconego
        box = cv2.boxPoints(rect)
        
        # 6. Transformacja współrzędnych z lokalnych (ROI) do globalnych (stół)
        cx_global = cx_local + x_start
        cy_global = cy_local + y_start
        
        global_corners = []
        for pt in box:
            global_corners.append([float(pt[0] + x_start), float(pt[1] + y_start)])
            
        # Przygotowanie wyniku
        card_metadata = {
            "center": (int(cx_global), int(cy_global)),
            "size": (int(w_card), int(h_card)),
            "angle": float(angle),
            "corners": global_corners
        }
        
        logger.info(f"Zakończono precyzyjne dopasowanie karty: Center={card_metadata['center']}, Size={card_metadata['size']}, Kąt={card_metadata['angle']:.2f}°")
        return card_metadata

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

    def refine_card(self, image, roi_rect, diff_mask=None, deck_profile=None) -> dict | None:
        """
        Precyzyjnie lokalizuje kartę wewnątrz ROI i zwraca jej metadane.
        Używa maski różnicowej i modelu geometrii talii. W przypadku ich braku lub błędu cofa się do progowania Otsu.

        :param image: Pełny wyprostowany obraz stołu BGR (1200x800).
        :param roi_rect: Prostokąt obrócony ((cx, cy), (w, h), angle) z detektora różnicowego.
        :param diff_mask: Opcjonalna maska binarna różnic ze snapshot-diff.
        :param deck_profile: Opcjonalny profil talii (DeckProfile).
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

        # Spróbuj najpierw dopasowania modelowego na podstawie maski różnicowej
        if diff_mask is not None:
            try:
                roi_mask = diff_mask[y_start:y_end, x_start:x_end]
                
                # Dodatkowe domknięcie morfologiczne na masce ROI dla połączenia drobnych przerw
                kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
                roi_mask_closed = cv2.morphologyEx(roi_mask, cv2.MORPH_CLOSE, kernel)
                
                contours, _ = cv2.findContours(roi_mask_closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
                
                best_contour = None
                max_area = 0
                for c in contours:
                    area = cv2.contourArea(c)
                    if area > max_area:
                        max_area = area
                        best_contour = c
                
                # Oczekujemy, że kontur na masce różnicowej reprezentuje przynajmniej minimalny obszar karty
                if best_contour is not None and max_area > 3000:
                    rect = cv2.minAreaRect(best_contour)
                    (cx_local, cy_local), (w_card, h_card), angle = rect
                    
                    # Pobieramy proporcje z profilu talii (stosunek wysokości do szerokości, np. 1.714)
                    aspect_ratio = 1.714
                    if deck_profile and deck_profile.aspect_ratio_height_to_width:
                        aspect_ratio = deck_profile.aspect_ratio_height_to_width
                    
                    # Korygujemy boki zachowując fizyczną proporcję talii
                    L = max(w_card, h_card)
                    S = L / aspect_ratio
                    
                    # Przypisujemy wymiary zgodnie z orientacją
                    if w_card >= h_card:
                        w_new, h_new = L, S
                    else:
                        w_new, h_new = S, L
                        
                    corrected_rect = ((cx_local, cy_local), (w_new, h_new), angle)
                    box = cv2.boxPoints(corrected_rect)
                    
                    cx_global = cx_local + x_start
                    cy_global = cy_local + y_start
                    
                    global_corners = []
                    for pt in box:
                        global_corners.append([float(pt[0] + x_start), float(pt[1] + y_start)])
                        
                    card_metadata = {
                        "center": (int(cx_global), int(cy_global)),
                        "size": (int(w_new), int(h_new)),
                        "angle": float(angle),
                        "corners": global_corners,
                        "frame_source": "diff_mask_deck_model_fit"
                    }
                    
                    logger.info(f"Modelowe dopasowanie z maski różnicowej zakończone sukcesem: Center={card_metadata['center']}, Size={card_metadata['size']}, Kąt={card_metadata['angle']:.2f}°")
                    return card_metadata
                    
            except Exception as e:
                logger.error(f"Błąd podczas modelowego dopasowania maski: {e}. Uruchamiam fallback na Otsu.")

        # FALLBACK: Klasyczne progowanie Otsu na obrazie BGR
        logger.info("Uruchamiam fallback: Progowanie Otsu na obrazie BGR.")
        roi_img = image[y_start:y_end, x_start:x_end]
        gray = cv2.cvtColor(roi_img, cv2.COLOR_BGR2GRAY)
        blurred = cv2.medianBlur(gray, 7)
        
        _, thresh = cv2.threshold(blurred, 0, 255, cv2.THRESH_BINARY + cv2.THRESH_OTSU)
        
        corner_pixels = [int(thresh[0, 0]), int(thresh[0, -1]), int(thresh[-1, 0]), int(thresh[-1, -1])]
        if sum(corner_pixels) > 510:
            thresh = cv2.bitwise_not(thresh)
            
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        best_contour = None
        max_area = 0
        for c in contours:
            area = cv2.contourArea(c)
            if area > max_area:
                max_area = area
                best_contour = c
                
        if best_contour is None or max_area < 5000:
            logger.warning("Nie znaleziono odpowiednio dużego konturu karty wewnątrz wyciętego ROI (Otsu).")
            return None
            
        rect = cv2.minAreaRect(best_contour)
        (cx_local, cy_local), (w_card, h_card), angle = rect
        box = cv2.boxPoints(rect)
        
        cx_global = cx_local + x_start
        cy_global = cy_local + y_start
        
        global_corners = []
        for pt in box:
            global_corners.append([float(pt[0] + x_start), float(pt[1] + y_start)])
            
        card_metadata = {
            "center": (int(cx_global), int(cy_global)),
            "size": (int(w_card), int(h_card)),
            "angle": float(angle),
            "corners": global_corners,
            "frame_source": "otsu_bgr"
        }
        
        logger.info(f"Klasyczne dopasowanie Otsu zakończone sukcesem: Center={card_metadata['center']}, Size={card_metadata['size']}, Kąt={card_metadata['angle']:.2f}°")
        return card_metadata

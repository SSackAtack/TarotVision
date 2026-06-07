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

    def refine_card(self, image, roi_rect, diff_mask=None, deck_profile=None, deck_profiles=None) -> dict | None:
        """
        Precyzyjnie lokalizuje kartę wewnątrz ROI i zwraca jej metadane.
        Używa maski różnicowej i modeli geometrii talii. W przypadku ich braku lub błędu cofa się do progowania Otsu.

        :param image: Pełny wyprostowany obraz stołu BGR (1200x800).
        :param roi_rect: Prostokąt obrócony ((cx, cy), (w, h), angle) z detektora różnicowego.
        :param diff_mask: Opcjonalna maska binarna różnic ze snapshot-diff.
        :param deck_profile: Opcjonalny pojedynczy profil talii (DeckProfile) - zachowanie kompatybilności.
        :param deck_profiles: Opcjonalna lista profili talii (DeckProfile).
        :return: Słownik z danymi geometrycznymi karty i metadanymi dopasowania lub None.
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

        # 3. Obsługa profilu/profili talii
        if deck_profiles is not None:
            profiles_list = list(deck_profiles)
        elif deck_profile is not None:
            profiles_list = [deck_profile]
        else:
            try:
                from tarotvision.decks.library import DeckLibrary
                library = DeckLibrary()
                profiles_list = library.load_active_profiles()
            except Exception as e:
                logger.warning(f"Nie udało się załadować profili z DeckLibrary: {e}")
                profiles_list = []

        # Spróbuj najpierw dopasowania modelowego na podstawie maski różnicowej
        if diff_mask is not None and profiles_list:
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
                    
                    detected_ratio = max(w_card, h_card) / min(w_card, h_card) if min(w_card, h_card) > 0 else 1.0
                    
                    # Liczymy score dopasowania dla każdej aktywnej talii
                    candidates = []
                    for profile in profiles_list:
                        aspect_ratio = profile.aspect_ratio_height_to_width if profile.aspect_ratio_height_to_width else 1.714
                        ratio_diff = abs(detected_ratio - aspect_ratio)
                        
                        # Geometry score (1.0 dla idealnego ratio, maleje liniowo przy różnicy)
                        geometry_score = max(0.0, 1.0 - 5.0 * ratio_diff)
                        
                        candidates.append({
                            "profile": profile,
                            "deck_id": profile.deck_id,
                            "aspect_ratio": aspect_ratio,
                            "geometry_score": float(geometry_score),
                            "ratio_diff": ratio_diff
                        })
                    
                    # Sortujemy kandydatów po score (najwyższy na początku)
                    candidates = sorted(candidates, key=lambda x: x["geometry_score"], reverse=True)
                    
                    best_candidate = candidates[0]
                    best_profile = best_candidate["profile"]
                    best_score = best_candidate["geometry_score"]
                    best_aspect_ratio = best_candidate["aspect_ratio"]
                    
                    # Wykrywanie niejednoznaczności (ambiguity)
                    is_ambiguous = False
                    similar_profiles = []
                    
                    if len(candidates) > 1:
                        for cand in candidates:
                            if cand == best_candidate:
                                similar_profiles.append(cand["deck_id"])
                            else:
                                score_diff = abs(best_score - cand["geometry_score"])
                                ratio_diff_between = abs(best_aspect_ratio - cand["aspect_ratio"])
                                # Jeśli score_diff <= 0.05 lub różnica aspect_ratio <= 0.02
                                if score_diff <= 0.05 or ratio_diff_between <= 0.02:
                                    is_ambiguous = True
                                    similar_profiles.append(cand["deck_id"])
                    
                    # Korygujemy boki zachowując fizyczną proporcję talii o najwyższym score
                    L = max(w_card, h_card)
                    S = L / best_aspect_ratio
                    
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
                        
                    geometry_candidates = [
                        {
                            "deck_id": c["deck_id"],
                            "aspect_ratio": round(c["aspect_ratio"], 3),
                            "geometry_score": round(c["geometry_score"], 3)
                        } for c in candidates
                    ]
                    
                    card_metadata = {
                        "center": (int(cx_global), int(cy_global)),
                        "size": (int(w_new), int(h_new)),
                        "angle": float(angle),
                        "corners": global_corners,
                        "frame_source": "diff_mask_multi_deck_model_fit",
                        "selected_geometry_profile": best_profile.deck_id,
                        "geometry_confidence": round(best_score, 3),
                        "geometry_ambiguous": is_ambiguous,
                        "similar_geometry_profiles": similar_profiles if is_ambiguous else [],
                        "geometry_candidates": geometry_candidates,
                        "recognized_deck": None,
                        "recognized_card": None
                    }
                    
                    logger.info(f"Modelowe dopasowanie z maski różnicowej zakończone sukcesem. Wybrana talia: '{best_profile.deck_id}' (Score: {best_score:.3f}, Niejednoznaczność: {is_ambiguous})")
                    return card_metadata
                    
            except Exception as e:
                logger.error(f"Błąd podczas modelowego dopasowania maski pod wiele talii: {e}. Uruchamiam fallback na Otsu.")

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
            "frame_source": "otsu_bgr",
            "selected_geometry_profile": profiles_list[0].deck_id if profiles_list else "unknown",
            "geometry_confidence": 0.5,
            "geometry_ambiguous": False,
            "similar_geometry_profiles": [],
            "geometry_candidates": [],
            "recognized_deck": None,
            "recognized_card": None
        }
        
        logger.info(f"Klasyczne dopasowanie Otsu zakończone sukcesem: Center={card_metadata['center']}, Size={card_metadata['size']}, Kąt={card_metadata['angle']:.2f}°")
        return card_metadata

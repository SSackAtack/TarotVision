import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CardDetector:
    """Klasa odpowiedzialna za wykrywanie prostokątów kart na wyprostowanym obrazie stołu."""

    def __init__(self, min_area: int = 10000, max_area: int = 120000, 
                 min_aspect_ratio: float = 1.3, max_aspect_ratio: float = 1.9):
        """
        Inicjalizacja detektora.

        :param min_area: Minimalne pole powierzchni konturu karty w pikselach.
        :param max_area: Maksymalne pole powierzchni konturu karty w pikselach.
        :param min_aspect_ratio: Minimalny stosunek dłuższego boku do krótszego.
        :param max_aspect_ratio: Maksymalny stosunek dłuższego boku do krótszego.
        """
        self.min_area = min_area
        self.max_area = max_area
        self.min_aspect_ratio = min_aspect_ratio
        self.max_aspect_ratio = max_aspect_ratio

    def detect_cards(self, image):
        """
        Analizuje obraz i wyszukuje kontury kart.

        :param image: Wyprostowany obraz stołu BGR (np. 1200x800).
        :return: Krotka (output_image_with_drawings, list_of_cards_metadata).
        """
        # Kopia obrazu do rysowania
        output_image = image.copy()
        
        # 1. Przetwarzanie wstępne
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        blurred = cv2.GaussianBlur(gray, (5, 5), 0)
        
        # 2. Progowanie adaptacyjne i domknięcie (closing)
        thresh = cv2.adaptiveThreshold(blurred, 255, cv2.ADAPTIVE_THRESH_GAUSSIAN_C, cv2.THRESH_BINARY_INV, 31, 2)
        kernel = cv2.getStructuringElement(cv2.MORPH_RECT, (5, 5))
        closed = cv2.morphologyEx(thresh, cv2.MORPH_CLOSE, kernel)
        
        # 3. Wyszukiwanie konturów
        contours, _ = cv2.findContours(closed, cv2.RETR_EXTERNAL, cv2.CHAIN_APPROX_SIMPLE)
        
        raw_cards = []
        
        for idx, c in enumerate(contours):
            area = cv2.contourArea(c)
            
            # Filtrowanie po polu powierzchni
            if not (self.min_area <= area <= self.max_area):
                continue
                
            # Aproksymacja konturu do wielokąta
            peri = cv2.arcLength(c, True)
            approx = cv2.approxPolyDP(c, 0.025 * peri, True)
            
            # Szukamy czworokątów wypukłych
            if len(approx) == 4 and cv2.isContourConvex(approx):
                # Dopasowanie prostokąta obróconego (minAreaRect)
                rect = cv2.minAreaRect(c)
                (cx, cy), (w, h), angle = rect
                
                if w == 0 or h == 0:
                    continue
                    
                # Obliczenie proporcji boków
                aspect_ratio = max(w, h) / min(w, h)
                
                # Filtrowanie po proporcjach karty tarota
                if self.min_aspect_ratio <= aspect_ratio <= self.max_aspect_ratio:
                    box = cv2.boxPoints(rect)
                    box = np.intp(box)
                    
                    raw_cards.append({
                        "id": f"card_candidate_{idx}",
                        "area": area,
                        "center": (int(cx), int(cy)),
                        "size": (int(w), int(h)),
                        "angle": float(angle),
                        "corners": box,
                        "approx": approx.reshape(4, 2)
                    })

        # 4. Eliminacja duplikatów (NMS oparty o odległość środków)
        final_cards = []
        raw_cards = sorted(raw_cards, key=lambda x: x["area"], reverse=True)
        
        for card in raw_cards:
            keep = True
            for f_card in final_cards:
                # Obliczenie odległości Euklidesowej między środkami
                dist = np.linalg.norm(np.array(card["center"]) - np.array(f_card["center"]))
                if dist < 40: # Jeśli środki są bliżej niż 40px, uznajemy za ten sam obiekt
                    keep = False
                    break
            if keep:
                final_cards.append(card)

        # 5. Rysowanie wyników i przygotowanie metadanych JSON
        cards_metadata = []
        for i, card in enumerate(final_cards):
            card_id = f"card_{i+1:03d}"
            
            # Narysowanie zielonego konturu karty
            cv2.drawContours(output_image, [card["corners"]], -1, (0, 255, 0), 3)
            # Narysowanie środka i etykiety
            cv2.circle(output_image, card["center"], 7, (0, 0, 255), -1)
            cv2.putText(output_image, card_id, (card["center"][0] - 25, card["center"][1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            
            # Przygotowanie metadanych zgodnych z formatem JSON projektu
            cards_metadata.append({
                "id": card_id,
                "name": None,
                "confidence": None,
                "position": {
                    "x": card["center"][0],
                    "y": card["center"][1]
                },
                "size": {
                    "width": card["size"][0] if card["size"][0] < card["size"][1] else card["size"][1],
                    "height": card["size"][1] if card["size"][0] < card["size"][1] else card["size"][0]
                },
                "angle": round(card["angle"], 2),
                "reversed": None,
                "corners": card["approx"].tolist()
            })
            
            logger.info(f"Wykryto kartę: {card_id} w środku: {card['center']} pod kątem {card['angle']:.2f}°")

        return output_image, cards_metadata

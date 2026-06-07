import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

def compute_bbox_overlap(bbox1: list[int] | tuple[int, int, int, int], bbox2: list[int] | tuple[int, int, int, int]) -> float:
    """
    Oblicza overlap_ratio jako stosunek pola przecięcia do pola bbox1 (karty).
    
    :param bbox1: [x, y, w, h] karty.
    :param bbox2: [x, y, w, h] ROI zmiany.
    :return: Współczynnik pokrycia z przedziału [0.0, 1.0].
    """
    x1, y1, w1, h1 = bbox1
    x2, y2, w2, h2 = bbox2
    
    x_left = max(x1, x2)
    y_top = max(y1, y2)
    x_right = min(x1 + w1, x2 + w2)
    y_bottom = min(y1 + h1, y2 + h2)
    
    if x_right <= x_left or y_bottom <= y_top:
        return 0.0
        
    intersection_area = (x_right - x_left) * (y_bottom - y_top)
    card_area = w1 * h1
    if card_area <= 0:
        return 0.0
    return float(intersection_area / card_area)

def get_card_mask(image_shape: tuple, position: dict) -> np.ndarray:
    """
    Tworzy maskę binarną obszaru karty na podstawie corners_px (polygon) lub bbox_px (prostokąt).
    
    :param image_shape: Kształt obrazu (wysokość, szerokość, ...).
    :param position: Słownik pozycji z corners_px i bbox_px.
    :return: Maska binarna np.ndarray typu uint8 o wymiarach obrazu.
    """
    mask = np.zeros(image_shape[:2], dtype=np.uint8)
    corners = position.get("corners_px")
    
    if corners and len(corners) >= 3:
        try:
            pts = np.array(corners, dtype=np.int32)
            cv2.fillPoly(mask, [pts], 255)
            return mask
        except Exception as e:
            logger.warning(f"Błąd przy tworzeniu maski z corners_px: {e}. Użycie fallbacku na bbox_px.")
            
    bbox = position.get("bbox_px")
    if bbox and len(bbox) == 4:
        x, y, w, h = bbox
        cv2.rectangle(mask, (int(x), int(y)), (int(x + w), int(y + h)), 255, -1)
    return mask

def get_mean_abs_diff(img1: np.ndarray, img2: np.ndarray, mask: np.ndarray) -> float:
    """
    Oblicza średnią różnicę bezwzględną (MAE) w skali szarości dla obszaru zdefiniowanego przez maskę.
    
    :param img1: Pierwszy obraz (BGR lub Grayscale).
    :param img2: Drugi obraz (BGR lub Grayscale).
    :param mask: Maska binarna.
    :return: Wartość MAE w pikselach.
    """
    if len(img1.shape) == 3:
        gray1 = cv2.cvtColor(img1, cv2.COLOR_BGR2GRAY)
    else:
        gray1 = img1
        
    if len(img2.shape) == 3:
        gray2 = cv2.cvtColor(img2, cv2.COLOR_BGR2GRAY)
    else:
        gray2 = img2
        
    diff = cv2.absdiff(gray1, gray2)
    mean_val = cv2.mean(diff, mask=mask)[0]
    return float(mean_val)

class CardRemovalDetector:
    def __init__(
        self,
        min_overlap: float = 0.60,
        min_prev_vs_bg: float = 20.0,
        max_curr_vs_bg: float = 12.0,
        min_restoration_delta: float = 10.0
    ):
        self.min_overlap = min_overlap
        self.min_prev_vs_bg = min_prev_vs_bg
        self.max_curr_vs_bg = max_curr_vs_bg
        self.min_restoration_delta = min_restoration_delta

    def detect_card_removal(
        self,
        snapshot_0: np.ndarray,
        snapshot_previous: np.ndarray,
        snapshot_current: np.ndarray,
        changed_roi_rect: list[int] | tuple[int, int, int, int],
        active_cards: list
    ) -> dict:
        """
        Analizuje czy podane ROI zmiany odpowiada usunięciu jednej z aktywnych kart.
        
        :param snapshot_0: Tło referencyjne (pusta mata).
        :param snapshot_previous: Poprzedni stan stołu.
        :param snapshot_current: Aktualny stan stołu.
        :param changed_roi_rect: ROI zmiany [x, y, w, h].
        :param active_cards: Lista aktywnych obiektów TableCard ze stanu stołu.
        :return: Słownik z wynikiem decyzji i metrykami.
        """
        best_card = None
        max_overlap = 0.0
        
        for card in active_cards:
            card_bbox = card.position.get("bbox_px")
            if not card_bbox or len(card_bbox) != 4:
                continue
            overlap = compute_bbox_overlap(card_bbox, changed_roi_rect)
            if overlap > max_overlap:
                max_overlap = overlap
                best_card = card
                
        if not best_card or max_overlap < self.min_overlap:
            return {
                "decision": "not_removed",
                "card_instance_id": None,
                "reason": "no_overlap_with_active_card"
            }
            
        # Generowanie maski dla najlepszej pasującej karty
        mask = get_card_mask(snapshot_0.shape, best_card.position)
        
        # Obliczenie metryk porównawczych
        previous_vs_background = get_mean_abs_diff(snapshot_previous, snapshot_0, mask)
        current_vs_background = get_mean_abs_diff(snapshot_current, snapshot_0, mask)
        restoration_delta = previous_vs_background - current_vs_background
        
        # Obliczenie pewności usunięcia
        if previous_vs_background > 0:
            restoration_ratio = restoration_delta / previous_vs_background
        else:
            restoration_ratio = 0.0
            
        removal_confidence = float(np.clip(max_overlap * max(0.0, restoration_ratio), 0.0, 1.0))
        
        # Decyzja
        if (max_overlap >= self.min_overlap and
            previous_vs_background >= self.min_prev_vs_bg and
            current_vs_background <= self.max_curr_vs_bg and
            restoration_delta >= self.min_restoration_delta):
            
            decision = "removed"
            reason = None
        else:
            decision = "not_removed"
            reason = "background_not_restored"
            
        result = {
            "decision": decision,
            "card_instance_id": best_card.card_instance_id,
            "overlap_ratio": round(max_overlap, 4),
            "previous_vs_background": round(previous_vs_background, 2),
            "current_vs_background": round(current_vs_background, 2),
            "restoration_delta": round(restoration_delta, 2),
            "removal_confidence": round(removal_confidence, 4)
        }
        if reason:
            result["reason"] = reason
            
        return result

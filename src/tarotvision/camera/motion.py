import cv2
import numpy as np
import time
import logging

logger = logging.getLogger(__name__)

class MotionDetector:
    """Moduł odpowiedzialny za detekcję ruchu i wykrywanie stabilizacji obrazu."""

    def __init__(self, threshold: float = 1.5, stabilization_time: float = 0.5, resize_width: int = 320):
        """
        Inicjalizacja detektora ruchu.

        :param threshold: Próg średniej różnicy pikseli (powyżej to ruch).
        :param stabilization_time: Wymagany czas bezruchu (w sekundach) do uznania obrazu za stabilny.
        :param resize_width: Szerokość, do której skalujemy obraz na potrzeby szybkiej analizy.
        """
        self.threshold = threshold
        self.stabilization_time = stabilization_time
        self.resize_width = resize_width
        
        self.prev_frame = None
        self.is_moving = False
        self.last_move_time = 0.0
        self.motion_detected_active = False # Czy aktualnie trwa sekwencja ruchu

    def reset(self):
        """Resetuje stan wewnętrzny detektora."""
        self.prev_frame = None
        self.is_moving = False
        self.last_move_time = 0.0
        self.motion_detected_active = False

    def update(self, frame) -> tuple[bool, bool]:
        """
        Analizuje nową klatkę i sprawdza stan ruchu.

        :param frame: Obraz wejściowy BGR.
        :return: Krotka (is_moving, is_stabilized).
                 - is_moving: True, jeśli w tej klatce wykryto ruch.
                 - is_stabilized: True tylko w momencie, gdy ruch ustał i minął czas stabilization_time.
        """
        if frame is None:
            return False, False

        # 1. Przygotowanie klatki (skala szarości, zmniejszenie, rozmycie)
        h, w = frame.shape[:2]
        aspect = h / w
        resize_height = int(self.resize_width * aspect)
        
        small = cv2.resize(frame, (self.resize_width, resize_height))
        gray = cv2.cvtColor(small, cv2.COLOR_BGR2GRAY)
        gray = cv2.GaussianBlur(gray, (21, 21), 0) # Silne rozmycie, aby zignorować drobny szum kamery

        if self.prev_frame is None:
            self.prev_frame = gray
            return False, False

        # 2. Obliczenie różnicy klatek
        diff = cv2.absdiff(self.prev_frame, gray)
        mean_diff = float(np.mean(diff))
        
        self.prev_frame = gray
        current_time = time.time()
        
        # 3. Klasyfikacja ruchu
        currently_moving = mean_diff > self.threshold
        is_stabilized = False

        if currently_moving:
            if not self.motion_detected_active:
                logger.info("Wykryto początek ruchu na stole.")
                self.motion_detected_active = True
            self.is_moving = True
            self.last_move_time = current_time
        else:
            # Brak ruchu w tej klatce
            if self.is_moving:
                # Sprawdzamy, czy ruch ustał na wystarczająco długo
                time_since_last_move = current_time - self.last_move_time
                if time_since_last_move >= self.stabilization_time:
                    logger.info(f"Obraz ustabilizował się po {time_since_last_move:.2f}s bezruchu.")
                    self.is_moving = False
                    self.motion_detected_active = False
                    is_stabilized = True
            else:
                # Obraz był już wcześniej stabilny, nic się nie dzieje
                pass

        return currently_moving, is_stabilized

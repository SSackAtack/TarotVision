import cv2
import logging
import time
from datetime import datetime

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class CameraCapture:
    """Klasa obsługująca pobieranie obrazu z kamery przy użyciu OpenCV."""

    def __init__(self, camera_index: int = 0, width: int = None, height: int = None, api_preference: int = cv2.CAP_DSHOW):
        """
        Inicjalizacja modułu kamery.

        :param camera_index: Indeks urządzenia kamery (np. 0 dla wbudowanej, 1 dla zewnętrznej).
        :param width: Opcjonalna szerokość obrazu.
        :param height: Opcjonalna wysokość obrazu.
        :param api_preference: Preferowane API OpenCV (domyślnie cv2.CAP_DSHOW dla stabilności na Windowsie).
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.api_preference = api_preference
        self.cap = None

    def open(self) -> bool:
        """
        Otwiera połączenie z kamerą.

        :return: True, jeśli połączenie powiodło się, w przeciwnym razie False.
        """
        logger.info(f"Próba otwarcia kamery o indeksie: {self.camera_index} przy użyciu API: {self.api_preference}")
        self.cap = cv2.VideoCapture(self.camera_index, self.api_preference)

        if not self.cap.isOpened():
            logger.error(f"Nie udało się otworzyć kamery o indeksie: {self.camera_index}")
            return False

        # Ustawienie formatu MJPEG (niezbędne dla HD na większości kamer USB)
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        # Konfiguracja rozdzielczości, jeśli podano
        if self.width is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        # Pobranie rzeczywistych parametrów
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        logger.info(f"Kamera otwarta pomyślnie. Rzeczywista rozdzielczość: {actual_width}x{actual_height}")
        
        # Czas na inicjalizację sprzętową sensora kamery
        logger.info("Oczekiwanie 2.0s na stabilizację sensora kamery...")
        time.sleep(2.0)
        
        # Warm-up kamery: odrzucenie pierwszych 15 klatek w celu kalibracji ekspozycji
        logger.info("Warm-up kamery (autokalibracja ekspozycji)...")
        for i in range(15):
            success, _ = self.cap.read()
            if not success:
                logger.warning(f"Nie udało się odczytać klatki warm-up ({i}/15). Przerywam.")
                break
            
        return True

    def get_frame(self):
        """
        Pobiera pojedynczą klatkę z kamery.

        :return: Krotka (success, frame), gdzie success to bool, a frame to obraz NumPy (BGR) lub None.
        """
        if self.cap is None or not self.cap.isOpened():
            logger.error("Kamera nie jest otwarta.")
            return False, None

        success, frame = self.cap.read()
        if not success or frame is None:
            logger.warning("Nie udało się pobrać klatki z kamery.")
            return False, None

        return True, frame

    def release(self):
        """Zwalnia zasoby kamery."""
        if self.cap is not None:
            logger.info("Zwalnianie zasobów kamery.")
            self.cap.release()
            self.cap = None

    def __enter__(self):
        self.open()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        self.release()

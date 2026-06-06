import cv2
import logging
from datetime import datetime
from pathlib import Path

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class ImageWriter:
    """Klasa odpowiedzialna za zapisywanie obrazów na dysk."""

    def __init__(self, base_output_dir: str = "output/captures"):
        """
        Inicjalizacja modułu zapisu.

        :param base_output_dir: Domyślny katalog, w którym będą zapisywane obrazy.
        """
        self.base_output_dir = Path(base_output_dir)

    def save_image(self, image, prefix: str = "capture", extension: str = "png") -> Path:
        """
        Zapisuje obraz na dysku z unikalną nazwą opartą o timestamp.

        :param image: Obraz w formacie NumPy array (BGR).
        :param prefix: Prefiks nazwy pliku (np. 'capture', 'processed').
        :param extension: Rozszerzenie pliku ('png', 'jpg').
        :return: Obiekt Path do zapisanego pliku.
        :raises ValueError: Jeśli obraz jest niepoprawny.
        """
        if image is None or not hasattr(image, "shape"):
            raise ValueError("Przekazany obiekt nie jest poprawnym obrazem NumPy array.")

        # Upewnienie się, że katalog docelowy istnieje
        self.base_output_dir.mkdir(parents=True, exist_ok=True)

        # Generowanie unikalnej nazwy pliku
        timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
        filename = f"{prefix}_{timestamp}.{extension}"
        file_path = self.base_output_dir / filename

        # Zapis obrazu przy użyciu OpenCV
        logger.info(f"Próba zapisu pliku: {file_path}")
        success = cv2.imwrite(str(file_path), image)

        if not success:
            logger.error(f"Nie udało się zapisać pliku: {file_path}")
            raise IOError(f"Błąd podczas zapisu pliku: {file_path}")

        logger.info(f"Plik zapisany pomyślnie: {file_path}")
        return file_path

import cv2
import numpy as np
import logging

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

class TablePerspectiveCorrector:
    """Klasa odpowiedzialna za korekcję perspektywy stołu na podstawie markerów ArUco."""

    def __init__(self, marker_dict_id: int = cv2.aruco.DICT_4X4_50):
        """
        Inicjalizacja korektora.

        :param marker_dict_id: ID słownika ArUco (domyślnie DICT_4X4_50).
        """
        self.marker_dict_id = marker_dict_id
        
        # Inicjalizacja detektora w zależności od wersji OpenCV
        try:
            self.aruco_dict = cv2.aruco.getPredefinedDictionary(self.marker_dict_id)
            self.parameters = cv2.aruco.DetectorParameters()
            self.detector = cv2.aruco.ArucoDetector(self.aruco_dict, self.parameters)
            self.use_new_api = True
        except AttributeError:
            self.aruco_dict = cv2.aruco.Dictionary_get(self.marker_dict_id)
            self.parameters = cv2.aruco.DetectorParameters_create()
            self.use_new_api = False

        # Wymagane ID markerów narożnych
        self.required_ids = {
            10: "Top-Left",
            11: "Top-Right",
            12: "Bottom-Right",
            13: "Bottom-Left"
        }

    def detect_marker_centers(self, image):
        """
        Wykrywa markery ArUco na obrazie i zwraca słownik z ich środkami.

        :param image: Obraz wejściowy BGR.
        :return: Słownik {id: (x, y)} dla wykrytych wymaganych markerów.
        """
        gray = cv2.cvtColor(image, cv2.COLOR_BGR2GRAY)
        
        if self.use_new_api:
            corners, ids, rejected = self.detector.detectMarkers(gray)
        else:
            corners, ids, rejected = cv2.aruco.detectMarkers(gray, self.aruco_dict, parameters=self.parameters)

        detected_centers = {}

        if ids is not None and len(ids) > 0:
            flat_ids = ids.flatten()
            for i, marker_id in enumerate(flat_ids):
                if marker_id in self.required_ids:
                    # Obliczenie środka markera jako średniej z 4 narożników
                    marker_corners = corners[i][0]
                    center_x = int(np.mean(marker_corners[:, 0]))
                    center_y = int(np.mean(marker_corners[:, 1]))
                    detected_centers[marker_id] = (center_x, center_y)
                    logger.debug(f"Wykryto marker {marker_id} ({self.required_ids[marker_id]}) w punkcie: ({center_x}, {center_y})")

        return detected_centers

    def get_warped_table(self, image, crop_to_markers: bool = True, output_width: int = 1200, output_height: int = 800):
        """
        Wykrywa markery i prostuje perspektywę obrazu stołu.

        :param image: Obraz wejściowy BGR.
        :param crop_to_markers: Jeśli True, przycina obraz dokładnie do wnętrza markerów.
                                Jeśli False, zachowuje pełne wideo z marginesem 15% naokoło markerów.
        :param output_width: Szerokość wyjściowego obrazu.
        :param output_height: Wysokość wyjściowego obrazu.
        :return: Krotka (warped_image, transform_matrix). warped_image to NumPy array, lub None w przypadku braku markerów.
        """
        # 1. Detekcja środków markerów
        centers = self.detect_marker_centers(image)

        # Sprawdzenie czy wykryto wszystkie 4 wymagane markery
        missing_ids = [m_id for m_id in self.required_ids if m_id not in centers]
        if missing_ids:
            logger.warning(f"Nie można wyprostować perspektywy. Brakujące markery: {missing_ids}")
            return None, None

        # 2. Punkty źródłowe (kolejność: TL, TR, BR, BL)
        src_pts = np.array([
            centers[10],  # Top-Left
            centers[11],  # Top-Right
            centers[12],  # Bottom-Right
            centers[13]   # Bottom-Left
        ], dtype=np.float32)

        # 3. Punkty docelowe w zależności od trybu przycięcia
        if crop_to_markers:
            # Cały obraz wynikowy to obszar wewnątrz markerów
            dst_pts = np.array([
                [0, 0],
                [output_width, 0],
                [output_width, output_height],
                [0, output_height]
            ], dtype=np.float32)
        else:
            # Wprowadzamy 15% marginesu wokół markerów
            margin_x = output_width * 0.15
            margin_y = output_height * 0.15
            dst_pts = np.array([
                [margin_x, margin_y],
                [output_width - margin_x, margin_y],
                [output_width - margin_x, output_height - margin_y],
                [margin_x, output_height - margin_y]
            ], dtype=np.float32)

        # 4. Obliczenie macierzy i rzutowanie perspektywiczne
        matrix = cv2.getPerspectiveTransform(src_pts, dst_pts)
        warped = cv2.warpPerspective(image, matrix, (output_width, output_height))

        logger.debug(f"Perspektywa wyprostowana pomyślnie. Tryb przycinania: {crop_to_markers}")
        return warped, matrix

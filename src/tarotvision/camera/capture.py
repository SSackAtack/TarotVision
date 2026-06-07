import cv2
import logging
import time
import numpy as np

logger = logging.getLogger(__name__)

class CameraCapture:
    """Klasa obsługująca pobieranie obrazu z kamery z automatyczną autodetekcją aktywnego urządzenia."""

    def __init__(self, 
                 camera_index: int = None, 
                 width: int = None, 
                 height: int = None, 
                 api_preference: int = cv2.CAP_DSHOW,
                 enable_preflight: bool = False,
                 camera_settings_path: str = "config/camera_settings.json"):
        """
        Inicjalizacja modułu kamery.

        :param camera_index: Żądany indeks kamery. Jeśli None lub 0, system automatycznie wyszuka aktywną kamerę.
        :param width: Opcjonalna szerokość obrazu.
        :param height: Opcjonalna wysokość obrazu.
        :param api_preference: Preferowane API OpenCV (domyślnie cv2.CAP_DSHOW dla systemu Windows).
        :param enable_preflight: Jeśli True, uruchamia ocenę jakości obrazu i aplikację parametrów po otwarciu.
        :param camera_settings_path: Ścieżka do pliku konfiguracji parametrów kamery.
        """
        self.camera_index = camera_index
        self.width = width
        self.height = height
        self.api_preference = api_preference
        self.enable_preflight = enable_preflight
        self.camera_settings_path = camera_settings_path
        self.cap = None
        self.preflight_data = None

    def _find_active_camera(self) -> int:
        """Skanuje urządzenia wideo i zwraca indeks kamery dającej nie-czarny obraz."""
        logger.info("Rozpoczynam autodetekcję aktywnej kamery fizycznej...")
        
        # 1. Próba wykrycia po nazwach urządzeń (pygrabber)
        try:
            from pygrabber.dshow_graph import FilterGraph
            graph = FilterGraph()
            devices = graph.get_input_devices()
            
            # Najpierw szukamy dedykowanych urządzeń
            for index, name in enumerate(devices):
                if "NVIDIA Broadcast" in name or "AnkerWork" in name:
                    cap = cv2.VideoCapture(index, self.api_preference)
                    if cap.isOpened():
                        success, frame = cap.read()
                        if success and frame is not None and float(np.mean(frame)) > 5.0:
                            cap.release()
                            logger.info(f"Dopasowano dedykowaną kamerę po nazwie: '{name}' na indeksie {index}.")
                            return index
                        cap.release()
            
            # Następnie szukamy jakiejkolwiek innej kamery fizycznej
            for index, name in enumerate(devices):
                if "NDI" not in name and "OBS" not in name:
                    cap = cv2.VideoCapture(index, self.api_preference)
                    if cap.isOpened():
                        success, frame = cap.read()
                        if success and frame is not None and float(np.mean(frame)) > 5.0:
                            cap.release()
                            logger.info(f"Dopasowano sprawną kamerę po nazwie: '{name}' na indeksie {index}.")
                            return index
                        cap.release()
        except Exception as e:
            logger.debug(f"Brak lub błąd pygrabber podczas autodetekcji ({e}). Przechodzę do skanowania sprzętowego.")
 
        # 2. Skanowanie sprzętowe portów 0-6
        for index in range(7):
            cap = cv2.VideoCapture(index, self.api_preference)
            if cap.isOpened():
                cap.read()  # Pierwsza klatka na rozruch
                success, frame = cap.read()
                if success and frame is not None:
                    brightness = float(np.mean(frame))
                    if brightness > 5.0:
                        cap.release()
                        logger.info(f"Wykryto sprawną kamerę sprzętową: Indeks {index} (jasność: {brightness:.2f}).")
                        return index
                cap.release()
                
        logger.warning("Nie znaleziono żadnej kamery dającej aktywny obraz. Używam domyślnego indeksu 0.")
        return 0

    def open(self) -> bool:
        """
        Otwiera połączenie z kamerą (z automatyczną weryfikacją i wyszukiwaniem w razie potrzeby).

        :return: True, jeśli połączenie powiodło się, w przeciwnym razie False.
        """
        # Jeśli indeks nie jest podany lub wynosi 0, lub podany indeks nie działa, wykonujemy autodetekcję
        if self.camera_index is None or self.camera_index == 0:
            self.camera_index = self._find_active_camera()
        
        logger.info(f"Otwieranie kamery o indeksie: {self.camera_index} przy użyciu API: {self.api_preference}")
        self.cap = cv2.VideoCapture(self.camera_index, self.api_preference)

        # Weryfikujemy czy port się otworzył i nie zwraca czerni
        if not self.cap.isOpened():
            logger.warning(f"Nie udało się otworzyć kamery na indeksie: {self.camera_index}. Uruchamiam autodetekcję awaryjną...")
            self.camera_index = self._find_active_camera()
            self.cap = cv2.VideoCapture(self.camera_index, self.api_preference)
            if not self.cap.isOpened():
                logger.error("Błąd krytyczny: Awaryjna autodetekcja kamery nie powiodła się.")
                return False

        # Ustawienie formatu MJPEG
        self.cap.set(cv2.CAP_PROP_FOURCC, cv2.VideoWriter_fourcc(*'MJPG'))

        # Konfiguracja rozdzielczości, jeśli podano
        if self.width is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_WIDTH, self.width)
        if self.height is not None:
            self.cap.set(cv2.CAP_PROP_FRAME_HEIGHT, self.height)

        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        logger.info(f"Kamera otwarta pomyślnie. Rzeczywista rozdzielczość: {actual_width}x{actual_height}")
        
        # Czas na inicjalizację sprzętową sensora kamery
        logger.info("Oczekiwanie 2.0s na stabilizację sensora kamery...")
        time.sleep(2.0)
        
        # Warm-up kamery
        logger.info("Warm-up kamery (autokalibracja ekspozycji)...")
        for i in range(15):
            success, _ = self.cap.read()
            if not success:
                logger.warning(f"Nie udało się odczytać klatki warm-up ({i}/15).")
                break
            
        # Preflight kamery, jeśli włączony
        if self.enable_preflight:
            self.run_preflight()

        return True

    def run_preflight(self) -> dict:
        """
        Uruchamia procedurę preflightu kamery:
        1. Aplikuje blokady parametrów z konfiguracji.
        2. Pobiera serię klatek (5 klatek) do analizy jakości.
        3. Oblicza metryki jakości obrazu.
        4. Zapisuje profil kamery camera_profile.json.
        """
        logger.info("Uruchamiam procedurę Camera Preflight...")
        from tarotvision.camera.settings import CameraSettingsManager
        from tarotvision.camera.preflight import CameraPreflightManager, calculate_quality_metrics
        
        settings_manager = CameraSettingsManager(config_path=self.camera_settings_path)
        preflight_manager = CameraPreflightManager(config_path=self.camera_settings_path)
        
        # 1. Aplikowanie ustawień i readback
        requested, readback, status = settings_manager.apply_settings(self.cap)
        
        # 2. Pobranie serii klatek do oceny jakości
        frames = []
        for _ in range(5):
            success, frame = self.get_frame()
            if success and frame is not None:
                frames.append(frame)
            time.sleep(0.05)
            
        if not frames:
            logger.error("Preflight: Nie udało się pobrać żadnej klatki do analizy jakości.")
            self.preflight_data = {
                "quality_status": "rejected",
                "notes": ["Brak klatek do analizy jakości"]
            }
            return self.preflight_data
            
        # 3. Obliczenie metryk i ocena statusu
        metrics = calculate_quality_metrics(frames)
        quality_status = preflight_manager.evaluate_quality(metrics)
        
        # 4. Zapis profilu
        actual_width = self.cap.get(cv2.CAP_PROP_FRAME_WIDTH)
        actual_height = self.cap.get(cv2.CAP_PROP_FRAME_HEIGHT)
        
        profile_path = preflight_manager.write_camera_profile(
            camera_index=self.camera_index,
            resolution=[int(actual_width), int(actual_height)],
            requested=requested,
            readback=readback,
            status=status,
            metrics=metrics,
            quality_status=quality_status
        )
        
        self.preflight_data = {
            "requested": requested,
            "readback": readback,
            "status": status,
            "metrics": metrics,
            "quality_status": quality_status,
            "profile_path": profile_path
        }
        
        logger.info(f"Preflight zakończony ze statusem jakości: {quality_status.upper()}")
        return self.preflight_data

    def get_frame(self) -> tuple[bool, np.ndarray | None]:
        """
        Pobiera pojedynczą klatkę z kamery.

        :return: Krotka (success, frame).
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

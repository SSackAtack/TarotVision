import os
import json
import logging
import cv2

logger = logging.getLogger(__name__)

class DeckProfile:
    """Klasa odpowiedzialna za zarządzanie profilem i geometrią talii kart."""

    def __init__(self, data: dict, file_path: str = None):
        self.file_path = file_path
        self.deck_id = data.get("deck_id", "unknown")
        self.deck_name = data.get("deck_name", "Unknown")
        self.geometry_source = data.get("geometry_source", "none")
        self.reference_scan_dir = data.get("reference_scan_dir", "")
        self.card_width_px = data.get("card_width_px")
        self.card_height_px = data.get("card_height_px")
        self.aspect_ratio_height_to_width = data.get("aspect_ratio_height_to_width")
        self.canonical_width_px = data.get("canonical_width_px")
        self.canonical_height_px = data.get("canonical_height_px")

    @classmethod
    def load(cls, profile_path: str) -> "DeckProfile":
        """
        Wczytuje profil talii z pliku JSON.
        Jeśli wartości geometryczne są nieokreślone, próbuje je wyznaczyć automatycznie na podstawie skanów.
        
        :param profile_path: Ścieżka do pliku deck_profile.json
        :return: Instancja DeckProfile
        """
        if not os.path.exists(profile_path):
            raise FileNotFoundError(f"Nie znaleziono pliku profilu talii pod adresem: {profile_path}")

        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                data = json.load(f)
        except Exception as e:
            logger.error(f"Błąd podczas wczytywania JSON z {profile_path}: {e}")
            raise e

        profile = cls(data, profile_path)
        
        # Jeśli geometria nie jest określona lub bazuje na fallbacku, spróbuj zainicjalizować ze skanów
        if (profile.aspect_ratio_height_to_width is None or 
                profile.card_width_px is None or 
                profile.card_height_px is None or
                profile.geometry_source.startswith("fallback")):
            profile._initialize_geometry()

        return profile

    def _initialize_geometry(self):
        """Przeszukuje katalog skanów referencyjnych i wyznacza geometrię z pierwszego napotkanego pliku."""
        # Względna ścieżka do katalogu skanów (może wymagać dopasowania względem pliku profilu)
        base_dir = os.path.dirname(self.file_path) if self.file_path else ""
        scan_dir = self.reference_scan_dir
        
        if not os.path.isabs(scan_dir) and base_dir:
            # Spróbuj najpierw połączyć relatywnie do lokalizacji profilu
            full_scan_dir = os.path.normpath(os.path.join(base_dir, "..", "..", "..", scan_dir))
            if not os.path.exists(full_scan_dir):
                # Fallback do bezpośredniego łączenia
                full_scan_dir = os.path.normpath(os.path.join(base_dir, scan_dir))
        else:
            full_scan_dir = scan_dir

        if not os.path.exists(full_scan_dir):
            logger.warning(f"Katalog skanów referencyjnych nie istnieje: {full_scan_dir}")
            self._apply_fallback_geometry("Katalog skanów nie istnieje")
            return

        # Znajdź pierwszy plik graficzny
        valid_extensions = (".png", ".jpg", ".jpeg", ".bmp", ".tiff")
        image_files = [f for f in os.listdir(full_scan_dir) if f.lower().endswith(valid_extensions)]

        if not image_files:
            logger.warning(f"Brak skanów referencyjnych w katalogu: {full_scan_dir}")
            self._apply_fallback_geometry("Brak plików graficznych w katalogu skanów")
            return

        first_scan_path = os.path.join(full_scan_dir, image_files[0])
        logger.info(f"Wykryto skan referencyjny do analizy geometrii: {first_scan_path}")

        try:
            img = cv2.imread(first_scan_path)
            if img is None:
                raise ValueError("Błąd odczytu obrazu przez OpenCV")

            h, w = img.shape[:2]
            self.card_width_px = w
            self.card_height_px = h
            self.aspect_ratio_height_to_width = float(h) / float(w)
            
            # Ustawienie kanonicznych wymiarów (na tym etapie takie same jak oryginalny skan)
            self.canonical_width_px = w
            self.canonical_height_px = h
            self.geometry_source = f"auto_detected_from_{image_files[0]}"

            # Zapisz zaktualizowany profil na dysku
            self.save()
            logger.info(f"Automatycznie uzupełniono geometrię talii: {w}x{h} px (stosunek boczny: {self.aspect_ratio_height_to_width:.3f})")

        except Exception as e:
            logger.error(f"Nie udało się odczytać geometrii ze skanu {first_scan_path}: {e}")
            self._apply_fallback_geometry(f"Błąd analizy skanu: {str(e)}")

    def _apply_fallback_geometry(self, reason: str):
        """Stosuje domyślne proporcje karty w przypadku braku rzeczywistego skanu."""
        logger.warning(f"Używam domyślnej geometrii talii (powód: {reason}).")
        # Standardowe proporcje karty tarota (np. 70mm x 120mm -> stosunek ~1.714)
        self.card_width_px = 700
        self.card_height_px = 1200
        self.aspect_ratio_height_to_width = 1.714
        self.canonical_width_px = 700
        self.canonical_height_px = 1200
        self.geometry_source = f"fallback_default_due_to_{reason.replace(' ', '_').lower()}"
        
        # Zapisz zaktualizowany profil na dysku
        self.save()

    def save(self):
        """Zapisuje bieżący stan profilu do pliku JSON."""
        if not self.file_path:
            return

        data = {
            "deck_id": self.deck_id,
            "deck_name": self.deck_name,
            "geometry_source": self.geometry_source,
            "reference_scan_dir": self.reference_scan_dir,
            "card_width_px": self.card_width_px,
            "card_height_px": self.card_height_px,
            "aspect_ratio_height_to_width": self.aspect_ratio_height_to_width,
            "canonical_width_px": self.canonical_width_px,
            "canonical_height_px": self.canonical_height_px,
            "scan_filename_semantics": "ignored_for_now",
            "notes": "Card names are not trusted at this stage. The first scan is used only for geometry and frame fitting."
        }

        try:
            with open(self.file_path, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
            logger.info(f"Zapisano profil talii do {self.file_path}")
        except Exception as e:
            logger.error(f"Nie udało się zapisać profilu do {self.file_path}: {e}")

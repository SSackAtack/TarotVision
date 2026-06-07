import cv2
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class CameraSettingsManager:
    """Klasa odpowiedzialna za zarządzanie i aplikowanie konfiguracji parametrów kamery."""

    def __init__(self, config_path: str = "config/camera_settings.json"):
        self.config_path = Path(config_path)
        self.settings = self._load_config()

    def _load_config(self) -> dict:
        """Wczytuje ustawienia kamery z pliku JSON."""
        if not self.config_path.exists():
            logger.warning(f"Brak pliku konfiguracji: {self.config_path}. Tworzenie pustego profilu.")
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Nie można wczytać pliku konfiguracji: {e}")
            return {}

    def apply_settings(self, cap: cv2.VideoCapture) -> tuple[dict, dict, dict]:
        """
        Podejmuje próbę zaaplikowania parametrów do urządzenia cv2.VideoCapture.
        Wykonuje readback i zwraca statusy: requested, readback, status.
        
        Returns:
            Krotka (requested, readback, status)
        """
        if not cap or not cap.isOpened():
            logger.error("Kamera nie jest otwarta. Pomijam aplikowanie ustawień.")
            return {}, {}, {}

        lock_settings = self.settings.get("lock_settings", {})
        manual_values = self.settings.get("manual_values", {})

        requested = {}
        readback = {}
        status = {}

        # 1. Definiowanie mapowania właściwości OpenCV i oczekiwanych wartości
        # auto_exposure: false -> wyłączamy (1.0 oznacza zwykle manual w DirectShow)
        # auto_focus: false -> wyłączamy (0.0 manual)
        # auto_white_balance: false -> wyłączamy (0.0 manual)
        prop_mapping = {
            "auto_exposure": (cv2.CAP_PROP_AUTO_EXPOSURE, 1.0 if not lock_settings.get("auto_exposure", True) else 0.25),
            "auto_focus": (cv2.CAP_PROP_AUTOFOCUS, 0.0 if not lock_settings.get("auto_focus", True) else 1.0),
            "auto_white_balance": (cv2.CAP_PROP_AUTO_WB, 0.0 if not lock_settings.get("auto_white_balance", True) else 1.0),
        }

        # Obsługa właściwości blokad
        for name, (prop, exp_val) in prop_mapping.items():
            requested[name] = exp_val
            try:
                # Najpierw sprawdzamy czy właściwość jest wspierana
                initial = cap.get(prop)
                if initial == -1.0:
                    status[name] = "unsupported"
                    readback[name] = "unsupported"
                    continue

                # Próba ustawienia
                set_success = cap.set(prop, exp_val)
                actual = cap.get(prop)

                if actual == -1.0:
                    status[name] = "unsupported"
                    readback[name] = "unsupported"
                elif abs(actual - exp_val) < 1e-4 or set_success:
                    status[name] = "applied"
                    readback[name] = actual
                else:
                    status[name] = "not_applied"
                    readback[name] = actual
            except Exception as e:
                logger.debug(f"Błąd przy ustawianiu {name}: {e}")
                status[name] = "unknown"
                readback[name] = "unknown"

        # 2. Obsługa manualnych wartości, jeśli są podane
        manual_mapping = {
            "exposure": cv2.CAP_PROP_EXPOSURE,
            "focus": cv2.CAP_PROP_FOCUS,
            "white_balance_temperature": cv2.CAP_PROP_WB_TEMPERATURE,
            "brightness": cv2.CAP_PROP_BRIGHTNESS,
            "contrast": cv2.CAP_PROP_CONTRAST,
            "gain": cv2.CAP_PROP_GAIN
        }

        for name, prop in manual_mapping.items():
            val = manual_values.get(name)
            if val is not None:
                requested[name] = val
                try:
                    set_success = cap.set(prop, val)
                    actual = cap.get(prop)
                    if actual == -1.0:
                        status[name] = "unsupported"
                        readback[name] = "unsupported"
                    elif abs(actual - val) < 1e-4 or set_success:
                        status[name] = "applied"
                        readback[name] = actual
                    else:
                        status[name] = "not_applied"
                        readback[name] = actual
                except Exception as e:
                    logger.debug(f"Błąd przy ustawianiu manualnej wartości {name}: {e}")
                    status[name] = "unknown"
                    readback[name] = "unknown"
            else:
                # Jeśli nie ma wartości manualnej w configu, robimy tylko readback stanu kamery
                requested[name] = None
                try:
                    actual = cap.get(prop)
                    if actual == -1.0:
                        status[name] = "unsupported"
                        readback[name] = "unsupported"
                    else:
                        status[name] = "unknown" # nie próbowano ustawić
                        readback[name] = actual
                except Exception:
                    status[name] = "unknown"
                    readback[name] = "unknown"

        return requested, readback, status

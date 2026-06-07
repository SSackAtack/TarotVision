import cv2
import numpy as np
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def calculate_quality_metrics(frames: list[np.ndarray]) -> dict:
    """
    Oblicza 6 metryk jakości na podstawie sekwencji klatek (grayscale).
    
    Args:
        frames: Lista klatek BGR lub Grayscale (zalecana sekwencja min. 3 klatek).
        
    Returns:
        Słownik z metrykami.
    """
    if not frames:
        return {}

    # Konwersja do grayscale
    gray_frames = []
    for f in frames:
        if len(f.shape) == 3:
            gray_frames.append(cv2.cvtColor(f, cv2.COLOR_BGR2GRAY))
        else:
            gray_frames.append(f.copy())

    # Obliczenia na ostatniej klatce
    target = gray_frames[-1]
    
    brightness_mean = float(np.mean(target))
    brightness_std = float(np.std(target))
    
    # Ostrość za pomocą wariancji Laplasjana
    laplacian_variance = float(cv2.Laplacian(target, cv2.CV_64F).var())
    
    # Prześwietlenia (piksele >= 250) i niedoświetlenia (piksele <= 5)
    total_pixels = target.size
    overexposed_ratio = float(np.sum(target >= 250) / total_pixels)
    underexposed_ratio = float(np.sum(target <= 5) / total_pixels)
    
    # Stabilność strumienia wideo (frame_delta_mean)
    if len(gray_frames) > 1:
        deltas = []
        for i in range(1, len(gray_frames)):
            diff = cv2.absdiff(gray_frames[i], gray_frames[i-1])
            deltas.append(np.mean(diff))
        frame_delta_mean = float(np.mean(deltas))
    else:
        frame_delta_mean = 0.0

    return {
        "brightness_mean": round(brightness_mean, 2),
        "brightness_std": round(brightness_std, 2),
        "laplacian_variance": round(laplacian_variance, 2),
        "overexposed_ratio": round(overexposed_ratio, 4),
        "underexposed_ratio": round(underexposed_ratio, 4),
        "frame_delta_mean": round(frame_delta_mean, 2)
    }

class CameraPreflightManager:
    """Klasa obsługująca ocenę jakości obrazu z kamery oraz generowanie raportów sesji."""

    def __init__(self, config_path: str = "config/camera_settings.json", base_session_dir: str = "output/sessions/current"):
        self.config_path = Path(config_path)
        self.session_dir = Path(base_session_dir)
        self.thresholds = self._load_thresholds()

    def _load_thresholds(self) -> dict:
        """Wczytuje progi jakości z pliku konfiguracyjnego."""
        if not self.config_path.exists():
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("quality_thresholds", {})
        except Exception:
            return {}

    def evaluate_quality(self, metrics: dict) -> str:
        """
        Ocenia jakość obrazu na podstawie metryk i progów.
        Zwraca: 'accepted', 'warning' lub 'rejected'.
        """
        # Domyślne wartości progów jeśli brak w pliku konfiguracji
        b_min = self.thresholds.get("brightness_mean_min", 50)
        b_max = self.thresholds.get("brightness_mean_max", 190)
        lap_min = self.thresholds.get("laplacian_variance_min", 80)
        over_max = self.thresholds.get("overexposed_ratio_max", 0.02)
        under_max = self.thresholds.get("underexposed_ratio_max", 0.05)
        delta_max = self.thresholds.get("frame_delta_mean_max", 3.0)

        # Pobieranie metryk
        b_mean = metrics.get("brightness_mean", 0.0)
        lap_var = metrics.get("laplacian_variance", 0.0)
        over = metrics.get("overexposed_ratio", 0.0)
        under = metrics.get("underexposed_ratio", 0.0)
        delta = metrics.get("frame_delta_mean", 0.0)

        # Sprawdzamy krytyczne progi (odrzucenie)
        if (b_mean < 40 or b_mean > 210 or 
            lap_var < 50 or 
            over > 0.08 or 
            under > 0.12 or 
            delta > 8.0):
            return "rejected"

        # Sprawdzamy progi ostrzeżenia (warning)
        if (b_mean < b_min or b_mean > b_max or 
            lap_var < lap_min or 
            over > over_max or 
            under > under_max or 
            delta > delta_max):
            return "warning"

        return "accepted"

    def write_camera_profile(self, 
                             camera_index: int, 
                             resolution: list, 
                             requested: dict, 
                             readback: dict, 
                             status: dict, 
                             metrics: dict, 
                             quality_status: str,
                             notes: list = None) -> Path:
        """
        Zapisuje camera_profile.json do folderu sesyjnego.
        """
        self.session_dir.mkdir(parents=True, exist_ok=True)
        
        # Filtrowanie i określenie statusu zaaplikowania
        settings_status = {}
        for name in ["auto_exposure", "auto_focus", "auto_white_balance"]:
            settings_status[name] = status.get(name, "unknown")

        profile_data = {
            "camera_index": camera_index,
            "resolution": resolution,
            "backend": "CAP_DSHOW",
            "camera_profile_name": "ankerwork_c310_default",
            "settings_requested": {
                "auto_exposure": requested.get("auto_exposure"),
                "auto_focus": requested.get("auto_focus"),
                "auto_white_balance": requested.get("auto_white_balance")
            },
            "settings_readback": {
                "auto_exposure": readback.get("auto_exposure"),
                "exposure": readback.get("exposure"),
                "auto_focus": readback.get("auto_focus"),
                "focus": readback.get("focus"),
                "auto_white_balance": readback.get("auto_white_balance"),
                "white_balance_temperature": readback.get("white_balance_temperature")
            },
            "settings_status": settings_status,
            "quality_metrics": metrics,
            "quality_status": quality_status,
            "notes": notes or []
        }

        out_path = self.session_dir / "camera_profile.json"
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(profile_data, f, indent=2, ensure_ascii=False)
            logger.info(f"Zapisano profil kamery dla sesji w: {out_path}")
        except Exception as e:
            logger.error(f"Nie można zapisać profilu kamery: {e}")

        return out_path

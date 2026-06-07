import cv2
import numpy as np
import json
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

def apply_color_profile(image: np.ndarray, profile: dict) -> np.ndarray:
    """
    Aplikuje profil kalibracji barwnej (LAB mean/std transfer) na podanym obrazie BGR.
    
    Args:
        image: Obraz wejściowy BGR.
        profile: Słownik profilu kalibracji.
        
    Returns:
        Skorygowany obraz BGR.
    """
    if not profile or "camera_lab_mean" not in profile:
        return image.copy()
        
    canonical_size = profile.get("canonical_size", [600, 1032])
    target_w, target_h = canonical_size[0], canonical_size[1]
    
    # 1. Resize do rozmiaru kanonicznego
    resized = cv2.resize(image, (target_w, target_h))
    
    # 2. Konwersja BGR -> LAB
    if len(resized.shape) == 2:
        return resized
    lab = cv2.cvtColor(resized, cv2.COLOR_BGR2LAB).astype(np.float32)
    
    # 3. Pobranie parametrów
    cam_mean = np.array(profile["camera_lab_mean"], dtype=np.float32)
    cam_std = np.array(profile["camera_lab_std"], dtype=np.float32)
    ref_mean = np.array(profile["reference_lab_mean"], dtype=np.float32)
    ref_std = np.array(profile["reference_lab_std"], dtype=np.float32)
    
    epsilon = 1e-6
    
    # 4. Korekcja mean/std transfer
    corrected_lab = np.zeros_like(lab)
    for i in range(3):
        corrected_lab[:, :, i] = (lab[:, :, i] - cam_mean[i]) / (cam_std[i] + epsilon) * ref_std[i] + ref_mean[i]
        
    # 5. Przycięcie do przedziału [0, 255]
    corrected_lab = np.clip(corrected_lab, 0, 255).astype(np.uint8)
    
    # 6. Konwersja LAB -> BGR
    corrected_bgr = cv2.cvtColor(corrected_lab, cv2.COLOR_LAB2BGR)
    return corrected_bgr

class SessionColorCalibrator:
    """Klasa obsługująca sesyjną kalibrację barw między obrazem z kamery a skanami referencyjnymi."""

    def __init__(self, config_path: str = "config/session_color_calibration.json"):
        self.config_path = Path(config_path)
        self.config = self._load_config()

    def _load_config(self) -> dict:
        """Wczytuje konfigurację kalibracji z pliku JSON."""
        if not self.config_path.exists():
            logger.warning(f"Brak pliku konfiguracji kalibracji: {self.config_path}.")
            return {}
        try:
            with open(self.config_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Nie można wczytać konfiguracji kalibracji: {e}")
            return {}

    def _get_gray_normalized_for_score(self, img: np.ndarray, target_w: int, target_h: int) -> np.ndarray:
        """Helper realizujący preprocesing identyczny jak w ImageMatcher do wyznaczenia score."""
        if len(img.shape) == 3:
            gray = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        else:
            gray = img.copy()
        resized = cv2.resize(gray, (target_w, target_h))
        blurred = cv2.GaussianBlur(resized, (5, 5), 0)
        normalized = cv2.normalize(blurred, None, 0, 255, cv2.NORM_MINMAX)
        return normalized

    def calculate_color_profile(self, camera_crop: np.ndarray, reference_image: np.ndarray) -> dict:
        """
        Porównuje crop z kamery z oryginalnym skanem referencyjnym, obliczając
        profil barwny sesji (LAB mean/std) oraz metryki diagnostyczne.
        
        Args:
            camera_crop: Obraz karty wycięty z kamery (BGR).
            reference_image: Oryginalny skan referencyjny karty (BGR).
            
        Returns:
            Słownik profilu sesyjnego gotowy do zapisu w JSON.
        """
        target_w = self.config.get("canonical_width_px", 600)
        target_h = self.config.get("canonical_height_px", 1032)
        
        # 1. Resize obu obrazów do wymiarów kanonicznych
        cam_resized = cv2.resize(camera_crop, (target_w, target_h))
        ref_resized = cv2.resize(reference_image, (target_w, target_h))
        
        # 2. Konwersja BGR -> LAB do obliczeń transferu
        cam_lab = cv2.cvtColor(cam_resized, cv2.COLOR_BGR2LAB).astype(np.float32)
        ref_lab = cv2.cvtColor(ref_resized, cv2.COLOR_BGR2LAB).astype(np.float32)
        
        # Średnia i std w przestrzeni LAB
        cam_lab_mean = [float(np.mean(cam_lab[:, :, i])) for i in range(3)]
        cam_lab_std = [float(np.std(cam_lab[:, :, i])) for i in range(3)]
        
        ref_lab_mean = [float(np.mean(ref_lab[:, :, i])) for i in range(3)]
        ref_lab_std = [float(np.std(ref_lab[:, :, i])) for i in range(3)]
        
        # 3. Metryki L (Jasność/Kontrast)
        brightness_delta = ref_lab_mean[0] - cam_lab_mean[0]
        epsilon = 1e-6
        contrast_ratio = ref_lab_std[0] / (cam_lab_std[0] + epsilon)
        
        # 4. Metryki BGR (Gains)
        cam_bgr_mean = [float(np.mean(cam_resized[:, :, i])) for i in range(3)]
        ref_bgr_mean = [float(np.mean(ref_resized[:, :, i])) for i in range(3)]
        bgr_channel_gain = [ref_bgr_mean[i] / (cam_bgr_mean[i] + epsilon) for i in range(3)]
        
        # 5. Metryki HSV (Nasycenie)
        cam_hsv = cv2.cvtColor(cam_resized, cv2.COLOR_BGR2HSV)
        ref_hsv = cv2.cvtColor(ref_resized, cv2.COLOR_BGR2HSV)
        cam_sat_mean = float(np.mean(cam_hsv[:, :, 1]))
        ref_sat_mean = float(np.mean(ref_hsv[:, :, 1]))
        hsv_saturation_ratio = ref_sat_mean / (cam_sat_mean + epsilon)
        
        # 6. Profil do aplikacji
        profile = {
            "profile_type": "session_color_calibration",
            "profile_version": "lab_mean_std_v1",
            "deck_id": self.config.get("deck_id", "gilded"),
            "calibration_reference_id": self.config.get("calibration_reference_id", "Gilded_38"),
            "canonical_size": [target_w, target_h],
            "method": self.config.get("method", "lab_mean_std_v1"),
            "camera_lab_mean": [round(x, 4) for x in cam_lab_mean],
            "camera_lab_std": [round(x, 4) for x in cam_lab_std],
            "reference_lab_mean": [round(x, 4) for x in ref_lab_mean],
            "reference_lab_std": [round(x, 4) for x in ref_lab_std],
            "brightness_delta": round(brightness_delta, 2),
            "contrast_ratio": round(contrast_ratio, 4),
            "bgr_channel_gain": [round(x, 4) for x in bgr_channel_gain],
            "hsv_saturation_ratio": round(hsv_saturation_ratio, 4)
        }
        
        # 7. Obliczenie score_before i score_after
        # Przed korekcją
        cam_gray_norm = self._get_gray_normalized_for_score(cam_resized, target_w, target_h)
        ref_gray_norm = self._get_gray_normalized_for_score(ref_resized, target_w, target_h)
        
        diff_before = cv2.absdiff(cam_gray_norm, ref_gray_norm)
        score_before = float(1.0 - np.mean(diff_before) / 255.0)
        
        # Po korekcji
        corrected_bgr = apply_color_profile(camera_crop, profile)
        corrected_gray_norm = self._get_gray_normalized_for_score(corrected_bgr, target_w, target_h)
        
        diff_after = cv2.absdiff(corrected_gray_norm, ref_gray_norm)
        score_after = float(1.0 - np.mean(diff_after) / 255.0)
        
        profile["score_before"] = round(score_before, 4)
        profile["score_after"] = round(score_after, 4)
        
        # 8. Ocena progów jakościowych (quality_status)
        thresholds = self.config.get("quality_thresholds", {})
        max_b_delta = thresholds.get("max_brightness_delta_abs", 80)
        max_gain = thresholds.get("max_channel_gain", 3.0)
        min_gain = thresholds.get("min_channel_gain", 0.3)
        
        quality_status = "accepted"
        warnings = []
        
        # Walidacja
        if abs(brightness_delta) > max_b_delta:
            quality_status = "rejected"
            warnings.append(f"Przekroczona różnica jasności: {brightness_delta:.2f} (max: {max_b_delta})")
            
        for i, channel_name in enumerate(["B", "G", "R"]):
            gain = bgr_channel_gain[i]
            if gain > max_gain or gain < min_gain:
                quality_status = "rejected"
                warnings.append(f"Nieprawidłowe wzmocnienie kanału {channel_name}: {gain:.2f} (zakres: {min_gain}-{max_gain})")
                
        profile["quality_status"] = quality_status
        profile["warnings"] = warnings
        
        return profile

    def save_profile(self, profile: dict, camera_crop: np.ndarray, reference_image: np.ndarray) -> Path:
        """
        Zapisuje profil sesyjny do pliku JSON oraz odpowiednie obrazy weryfikacyjne w output.
        """
        out_path = Path(self.config.get("output_profile_path", "output/sessions/current/session_color_profile.json"))
        out_path.parent.mkdir(parents=True, exist_ok=True)
        
        # Ścieżki obrazów weryfikacyjnych
        calib_dir = out_path.parent / "calibration"
        calib_dir.mkdir(parents=True, exist_ok=True)
        
        crop_path = calib_dir / "calibration_crop.png"
        ref_path = calib_dir / "calibration_reference.png"
        corr_path = calib_dir / "calibration_corrected.png"
        
        cv2.imwrite(str(crop_path), camera_crop)
        cv2.imwrite(str(ref_path), reference_image)
        
        corrected = apply_color_profile(camera_crop, profile)
        cv2.imwrite(str(corr_path), corrected)
        
        # Dodanie ścieżek do profilu przed zapisem
        profile["camera_crop_path"] = str(crop_path)
        profile["reference_scan_path"] = str(ref_path)
        
        try:
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(profile, f, indent=2, ensure_ascii=False)
            logger.info(f"Zapisano profil kalibracji barwnej w: {out_path}")
        except Exception as e:
            logger.error(f"Błąd przy zapisie profilu barwnego: {e}")
            
        return out_path

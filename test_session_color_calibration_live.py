import sys
import os
import cv2
import json
import time
from pathlib import Path
import logging

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture
from tarotvision.camera.motion import MotionDetector
from tarotvision.storage.snapshots import SnapshotManager
from tarotvision.vision.perspective import TablePerspectiveCorrector
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery
from tarotvision.vision.cropper import CardCropper
from tarotvision.recognition.session_color_calibration import SessionColorCalibrator

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_live_calibration():
    print("=== TarotVision: Skrypt Kalibracji Barwnej Live ===")
    
    # 1. Wczytanie konfiguracji kalibracji
    config_path = Path("config/session_color_calibration.json")
    if not config_path.exists():
        print(f"[BŁĄD] Plik konfiguracji {config_path} nie istnieje.")
        sys.exit(1)
        
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)
        
    deck_id = config.get("deck_id", "gilded")
    ref_id = config.get("calibration_reference_id", "Gilded_38")
    ref_dir = Path(config.get("reference_scan_dir", "assets/decks/gilded/reference_scans"))
    ref_scan_path = ref_dir / f"{ref_id}.png"
    
    if not ref_scan_path.exists():
        print(f"[BŁĄD] Brak referencyjnego skanu kalibracyjnego w: {ref_scan_path}")
        sys.exit(1)
        
    ref_scan = cv2.imread(str(ref_scan_path))
    if ref_scan is None:
        print(f"[BŁĄD] Nie można wczytać obrazu referencyjnego: {ref_scan_path}")
        sys.exit(1)
        
    # 2. Inicjalizacja komponentów pipeline'u
    corrector = TablePerspectiveCorrector()
    motion_detector = MotionDetector(threshold=1.2, stabilization_time=0.5)
    snapshot_manager = SnapshotManager(base_dir="output/sessions/current")
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    cropper = CardCropper()
    calibrator = SessionColorCalibrator(config_path=str(config_path))
    
    # Inicjalizacja kamery
    print("Inicjalizacja kamery...")
    with CameraCapture(camera_index=None, width=1920, height=1080, enable_preflight=True) as cam:
        if cam.cap is None or not cam.cap.isOpened():
            print("Błąd krytyczny: Nie można otworzyć żadnej sprawnej kamery.")
            sys.exit(1)
            
        print("\n=== Instrukcja Kalibracji Koloru ===")
        print(f"1. Przygotuj pusty stół roboczy.")
        print(f"2. Naciśnij SPACJĘ w oknie podglądu, aby zapisać tło (Snapshot_0).")
        print(f"3. Następnie połóż kartę kalibracyjną: '{ref_id}' na stole.")
        print(f"4. Zabierz rękę i poczekaj na zakończenie kalibracji.")
        print("===================================\n")
        
        has_snapshot_0 = snapshot_manager.has_snapshot_0()
        
        # Pętla kalibracji tła (Snapshot_0)
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            display_frame = frame.copy()
            
            if warped is not None:
                cv2.imshow("Wyprostowany Stol (Warped)", warped)
                cv2.putText(display_frame, "Stol wykryty poprawnie", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "BLAD: Nie wykryto markerów ArUco!", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                            
            cv2.putText(display_frame, "SPACJA: Zapisz Snapshot_0 | ESC: Wyjdz", (30, 80), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
            cv2.imshow("Podglad Live (Kamera)", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27: # ESC
                print("Anulowano przez operatora.")
                cv2.destroyAllWindows()
                return
            elif key == 32: # SPACJA
                if warped is not None:
                    snapshot_manager.save_snapshot_0(warped)
                    has_snapshot_0 = True
                    print("-> ZAPISANO SNAPSHOT_0 (PUSTA MATA). Przechodzę do kalibracji koloru.")
                    break
                else:
                    print("Nie można wykonać Snapshot_0 - brak widocznych markerów ArUco!")
            elif has_snapshot_0 and key != 255:
                # Enter lub inny klawisz, jeśli Snapshot_0 już jest na dysku
                print("-> Używam istniejącego Snapshot_0 z dysku.")
                break
                
        # Reset detektora ruchu
        motion_detector.reset()
        
        print(f"\n[AKCJA] Połóż kartę kalibracyjną '{ref_id}' na stole i cofnij rękę...")
        cv2.destroyWindow("Podglad Live (Kamera)")
        
        calibration_success = False
        
        while not calibration_success:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            if warped is None:
                cv2.imshow("Wyprostowany Stol (Warped)", frame)
                cv2.waitKey(1)
                continue
                
            is_moving, is_stabilized = motion_detector.update(warped)
            display_warped = warped.copy()
            
            if is_moving:
                cv2.putText(display_warped, "STATUS: RUCH...", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.putText(display_warped, "STATUS: STABILNIE", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                            
            if is_stabilized:
                print("Wykryto stabilizację. Analizuję kartę kalibracyjną...")
                snapshot_current = warped.copy()
                snapshot_previous = snapshot_manager.get_snapshot_previous()
                
                # Wykrywanie ROI karty
                roi_rect, debug_mask = diff_detector.detect_change_roi(snapshot_current, snapshot_previous)
                
                if roi_rect is not None:
                    # Dopasowanie krawędzi
                    from tarotvision.decks.profile import DeckProfile
                    deck_profile = DeckProfile.load(f"assets/decks/{deck_id}/deck_profile.json")
                    card_data = refinery.refine_card(warped, roi_rect, diff_mask=debug_mask, deck_profile=deck_profile)
                    
                    if card_data is not None:
                        # Wycinanie cropa z kamery
                        crop_res = cropper.crop_card(warped, card_data, deck_profile)
                        if crop_res and crop_res["success"]:
                            camera_crop = crop_res["crop_image"]
                            
                            # OBLICZANIE PROFILU KOLORU
                            profile = calibrator.calculate_color_profile(camera_crop, ref_scan)
                            profile_path = calibrator.save_profile(profile, camera_crop, ref_scan)
                            
                            print(f"\n=== SUKCES KALIBRACJI KOLORU ===")
                            print(f"Jasność Delta: {profile['brightness_delta']:.2f}")
                            print(f"Współczynnik kontrastu: {profile['contrast_ratio']:.4f}")
                            print(f"BGR gains: {profile['bgr_channel_gain']}")
                            print(f"Dopasowanie przed korekcją (Score Before): {profile['score_before']:.4f}")
                            print(f"Dopasowanie po korekcji (Score After): {profile['score_after']:.4f}")
                            print(f"Profil zapisany w: {profile_path}")
                            print("=================================\n")
                            
                            # WAŻNE: NIE wywołujemy accept_current_as_previous(),
                            # aby po kalibracji stół powrócił do pustego stanu roboczego.
                            calibration_success = True
                            
                            # Rysowanie zielonej ramki
                            box = np.intp(card_data["corners"])
                            cv2.drawContours(display_warped, [box], -1, (0, 255, 0), 3)
                            cv2.putText(display_warped, "KALIBRACJA OK", (card_data["center"][0]-60, card_data["center"][1]),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
                        else:
                            print("-> Błąd: Wycięcie karty nie powiodło się.")
                    else:
                        print("-> Błąd: Dopasowanie geometryczne karty nie powiodło się.")
                else:
                    print("-> Błąd: Detektor nie wykrył karty kalibracyjnej na stole.")
                    
            cv2.imshow("Wyprostowany Stol (Warped)", display_warped)
            cv2.waitKey(1)
            
        print("\n[AKCJA] Kalibracja udana! Zdejmij kartę kalibracyjną ze stołu i naciśnij ESC, aby wyjść.")
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            if warped is not None:
                cv2.putText(warped, "ZDEJMIJ KARTE I NACISNIJ ESC", (30, 40),
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 255), 2)
                cv2.imshow("Wyprostowany Stol (Warped)", warped)
            if cv2.waitKey(1) & 0xFF == 27: # ESC
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run_live_calibration()

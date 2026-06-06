import sys
import os
import cv2
import numpy as np
import json
import time
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture
from tarotvision.camera.motion import MotionDetector
from tarotvision.storage.snapshots import SnapshotManager
from tarotvision.vision.perspective import TablePerspectiveCorrector
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery

def run_diff_detection():
    print("--- TarotVision: Test Detekcji Kart za pomocą Różnicy Snapshotów ---")
    
    # 1. Inicjalizacja komponentów
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    corrector = TablePerspectiveCorrector()
    motion_detector = MotionDetector(threshold=1.2, stabilization_time=0.5)
    snapshot_manager = SnapshotManager(base_dir="output/sessions/current")
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    
    # Inicjalizacja kamery (CameraCapture automatycznie wykryje sprawny port nie-czarny)
    print("Inicjalizacja kamery...")
    with CameraCapture(camera_index=None, width=1920, height=1080) as cam:
        if cam.cap is None or not cam.cap.isOpened():
            print("Błąd krytyczny: Nie udało się otworzyć żadnej sprawnej kamery.")
            sys.exit(1)
            
        print("\n=== Instrukcja obsługi ===")
        if snapshot_manager.has_snapshot_0():
            print("-> Wykryto zapisany Snapshot_0 (pusta mata) na dysku.")
            print("-> Wciśnij SPACJĘ w oknie wideo, aby zrobić NOWY Snapshot_0.")
            print("-> Wciśnij DOWOLNY INNY KLAWISZ (np. Enter), aby pominąć i użyć zapisanego.")
        else:
            print("-> Brak Snapshot_0. Uporządkuj stół (pusta mata).")
            print("-> Trwa automatyczny preflight... Jeśli stół będzie pusty i stabilny przez 3 sekundy,")
            print("   system sam wykona Snapshot_0.")
            print("-> Możesz też w każdej chwili wcisnąć SPACJĘ, aby wykonać go ręcznie.")
        print("-> Wciśnij ESC w oknie wideo, aby wyjść z programu.")
        print("==========================\n")
        
        has_snapshot_0 = snapshot_manager.has_snapshot_0()
        
        # Zmienne dla automatycznego preflightu
        preflight_active = not has_snapshot_0
        stable_start_time = None
        preflight_duration = 3.0 # Wymagany czas bezruchu dla autokalibracji
        
        # Pętla kalibracji / oczekiwania na Snapshot_0
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            # Prostujemy obraz na bieżąco
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            
            # Kopia do wyświetlania
            display_frame = frame.copy()
            
            if warped is not None:
                cv2.imshow("Wyprostowany Stol (Warped)", warped)
                cv2.putText(display_frame, "Stol wykryty poprawnie", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                # Logika automatycznego preflightu (tylko gdy stół jest wykryty)
                if preflight_active:
                    is_moving, _ = motion_detector.update(warped)
                    current_time = time.time()
                    
                    if is_moving:
                        # Ruch resetuje licznik stabilności
                        stable_start_time = None
                        cv2.putText(display_frame, "Auto-Preflight: Wykryto ruch...", (30, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    else:
                        if stable_start_time is None:
                            stable_start_time = current_time
                        
                        elapsed = current_time - stable_start_time
                        progress = min(1.0, elapsed / preflight_duration)
                        cv2.putText(display_frame, f"Auto-Preflight: Stabilizacja... {progress*100:.0f}%", (30, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                                    
                        if elapsed >= preflight_duration:
                            snapshot_manager.save_snapshot_0(warped)
                            has_snapshot_0 = True
                            print("-> [Auto-Preflight] ZAPISANO SNAPSHOT_0 (PUSTA MATA). Przechodzę do detekcji.")
                            break
            else:
                cv2.putText(display_frame, "BLAD: Nie wykryto 4 markerow ArUco!", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                stable_start_time = None # Brak stołu resetuje preflight
                            
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
                    print("-> ZAPISANO SNAPSHOT_0 (PUSTA MATA) RĘCZNIE. Przechodzę do detekcji.")
                    break
                else:
                    print("Nie można wykonać Snapshot_0 - brak widocznych 4 markerów ArUco na stole!")
            elif has_snapshot_0 and key != 255:
                # Każdy inny klawisz, jeśli mamy Snapshot_0 na dysku
                print("-> Używam istniejącego Snapshot_0 z dysku.")
                break
                
        # Reset detektora ruchu po preflighcie, aby zacząć od świeżego stanu
        motion_detector.reset()
        
        # Główna pętla detekcji
        print("\nRozpoczynam automatyczną detekcję na podstawie różnic obrazów...")
        print("Połóż kartę na stole i zabierz rękę.")
        
        cv2.destroyWindow("Podglad Live (Kamera)")
        
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            if warped is None:
                cv2.imshow("Wyprostowany Stol (Warped)", frame)
                cv2.waitKey(1)
                continue
                
            # 2. Aktualizacja detektora ruchu
            is_moving, is_stabilized = motion_detector.update(warped)
            
            display_warped = warped.copy()
            
            # Wyświetlanie statusu ruchu
            if is_moving:
                cv2.putText(display_warped, "STATUS: RUCH NA STOLE...", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.putText(display_warped, "STATUS: STABILNIE", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 3. Jeśli ruch ustał -> Wykrycie karty!
            if is_stabilized:
                print("\nWykryto ustabilizowanie obrazu. Aktualizuję snapshot stołu...")
                snapshot_manager.save_snapshot_current(warped)
                
                # Pobranie Snapshot_0 jako tła referencyjnego
                snap_0 = snapshot_manager.get_snapshot_0()
                
                # Detekcja zmiany (ROI)
                roi_rect, debug_mask = diff_detector.detect_change_roi(warped, snap_0)
                cv2.imwrite(str(output_dir / "debug_diff_mask.png"), debug_mask)
                
                if roi_rect is not None:
                    # Precyzyjne dopasowanie karty w ROI
                    card_data = refinery.refine_card(warped, roi_rect)
                    
                    if card_data is not None:
                        # Przygotowanie metadanych JSON
                        cards_metadata = [{
                            "id": "card_001",
                            "name": None,
                            "confidence": None,
                            "position": {
                                "x": card_data["center"][0],
                                "y": card_data["center"][1]
                            },
                            "size": {
                                "width": card_data["size"][0] if card_data["size"][0] < card_data["size"][1] else card_data["size"][1],
                                "height": card_data["size"][1] if card_data["size"][0] < card_data["size"][1] else card_data["size"][0]
                            },
                            "angle": round(card_data["angle"], 2),
                            "reversed": None,
                            "corners": card_data["corners"]
                        }]
                        
                        # Zapis metadanych JSON
                        with open(output_dir / "detected_cards.json", "w", encoding="utf-8") as f:
                            json.dump(cards_metadata, f, indent=2, ensure_ascii=False)
                            
                        # Narysowanie zielonego prostokąta
                        box = np.intp(card_data["corners"])
                        cv2.drawContours(display_warped, [box], -1, (0, 255, 0), 3)
                        cv2.circle(display_warped, card_data["center"], 7, (0, 0, 255), -1)
                        cv2.putText(display_warped, "card_001", (card_data["center"][0] - 25, card_data["center"][1] - 15),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                    
                        # Zapisz obraz wynikowy
                        cv2.imwrite(str(output_dir / "table_detected_diff.png"), display_warped)
                        print(f"-> Sukces! Zapisano obraz wynikowy w: {output_dir / 'table_detected_diff.png'}")
                        print(f"-> Zapisano JSON w: {output_dir / 'detected_cards.json'}")
                        
                    else:
                        print("-> Błąd: Precyzyjne dopasowanie karty w ROI nie powiodło się.")
                else:
                    print("-> Błąd: Detektor różnicowy nie wykrył obszaru zmian.")
            
            # W oknie Warped wyświetlamy nakładki
            cv2.imshow("Wyprostowany Stol (Warped)", display_warped)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27: # ESC
                print("Zakończono test.")
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run_diff_detection()

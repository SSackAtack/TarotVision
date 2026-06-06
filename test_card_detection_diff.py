import sys
import os
import cv2
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

def find_active_camera_index() -> int:
    """
    Skanuje urządzenia wideo w poszukiwaniu działającej kamery fizycznej.
    Używa pygrabber (po nazwie), a w przypadku braku biblioteki lub braku dopasowań
    skanuje porty wideo w poszukiwaniu kamery zwracającej nie-czarny obraz.
    """
    print("Skanowanie w poszukiwaniu aktywnej kamery...")
    
    # 1. Próba wykrycia po nazwach urządzeń (pygrabber)
    try:
        from pygrabber.dshow_graph import FilterGraph
        graph = FilterGraph()
        devices = graph.get_input_devices()
        for index, name in enumerate(devices):
            if "NVIDIA Broadcast" in name or "AnkerWork" in name:
                # Sprawdzamy czy ta kamera nie zwraca czarnego obrazu
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    success, frame = cap.read()
                    if success and frame is not None and np.mean(frame) > 5.0:
                        cap.release()
                        print(f"-> Dopasowanie nazwy: '{name}' na indeksie {index} (obraz aktywny).")
                        return index
                    cap.release()
                    
        for index, name in enumerate(devices):
            if "NDI" not in name and "OBS" not in name:
                cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
                if cap.isOpened():
                    success, frame = cap.read()
                    if success and frame is not None and np.mean(frame) > 5.0:
                        cap.release()
                        print(f"-> Dopasowanie alternatywne: '{name}' na indeksie {index} (obraz aktywny).")
                        return index
                    cap.release()
    except Exception as e:
        print(f"Brak lub błąd pygrabber ({e}). Przechodzę do skanowania sprzętowego...")

    # 2. Skanowanie sprzętowe portów 0-6 (sprawdzamy czy kamera żyje i nie zwraca czerni)
    for index in range(7):
        cap = cv2.VideoCapture(index, cv2.CAP_DSHOW)
        if cap.isOpened():
            # Warm-up 2 klatki na stabilizację sensora przy odpytaniu
            cap.read()
            success, frame = cap.read()
            if success and frame is not None:
                brightness = float(np.mean(frame))
                if brightness > 5.0:
                    cap.release()
                    print(f"-> Wykryto aktywną kamerę sprzętową: Indeks {index} (jasność obrazu: {brightness:.2f}).")
                    return index
            cap.release()
            
    print("-> Błąd: Nie znaleziono żadnej kamery zwracającej aktywny (nie-czarny) obraz. Używam indeksu 0.")
    return 0

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
    
    camera_index = find_active_camera_index()
    
    # Inicjalizacja kamery
    print(f"Otwieranie kamery o indeksie {camera_index}...")
    with CameraCapture(camera_index=camera_index, width=1920, height=1080) as cam:
        if cam.cap is None or not cam.cap.isOpened():
            print("Błąd: Nie można otworzyć kamery.")
            sys.exit(1)
            
        print("\n=== Instrukcja obsługi ===")
        if snapshot_manager.has_snapshot_0():
            print("-> Wykryto zapisany Snapshot_0 (pusta mata) na dysku.")
            print("-> Wciśnij SPACJĘ w oknie wideo, aby zrobić NOWY Snapshot_0.")
            print("-> Wciśnij DOWOLNY INNY KLAWISZ (np. Enter), aby pominąć i użyć zapisanego.")
        else:
            print("-> Brak Snapshot_0. Uporządkuj stół (pusta mata) i przygotuj się do kalibracji.")
            print("-> Wciśnij SPACJĘ w oknie wideo, aby wykonać Snapshot_0 (pusta mata).")
        print("-> Wciśnij ESC w oknie wideo, aby wyjść z programu.")
        print("==========================\n")
        
        has_snapshot_0 = snapshot_manager.has_snapshot_0()
        
        # Pętla kalibracji / oczekiwania na Snapshot_0
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            # Prostujemy obraz na bieżąco, aby operator widział wyprostowany stół
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            
            # Kopia do wyświetlania
            display_frame = frame.copy()
            
            if warped is not None:
                cv2.imshow("Wyprostowany Stol (Warped)", warped)
                cv2.putText(display_frame, "Stol wykryty poprawnie", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
            else:
                cv2.putText(display_frame, "BLAD: Nie wykryto 4 markerow ArUco!", (30, 40), 
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
                    print("-> ZAPISANO SNAPSHOT_0 (PUSTA MATA). Przechodzę do detekcji.")
                    break
                else:
                    print("Nie można wykonać Snapshot_0 - brak widocznych 4 markerów ArUco na stole!")
            elif has_snapshot_0 and key != 255:
                # Każdy inny klawisz, jeśli mamy Snapshot_0 na dysku
                print("-> Używam istniejącego Snapshot_0 z dysku.")
                break
                
        # Główna pętla detekcji
        print("\nRozpoczynam automatyczną detekcję na podstawie różnic obrazów...")
        print("Połóż kartę na stole i zabierz rękę.")
        
        cv2.destroyWindow("Podglad Live (Kamera)") # Zamykamy surowy podgląd, operator patrzy na wyprostowany stół
        
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            if warped is None:
                # Brak markerów - informujemy i pomijamy klatkę
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
                            
                        # Narysowanie zielonego prostokąta dopasowanej karty na obrazie wynikowym
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

import sys
import os
import cv2
import numpy as np
import json
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.decks.profile import DeckProfile
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery

def run_diagnostics_test():
    print("=== TarotVision: Test Diagnostyczny Dopasowania Modelu Karty (Offline) ===")
    
    # 1. Przygotowanie ścieżek
    detections_dir = Path("output/sessions/current/detections")
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    if not detections_dir.exists():
        print(f"Błąd: Katalog diagnostyczny {detections_dir} nie istnieje.")
        print("Najpierw należy uruchomić test z kamerą lub przygotować dane diagnostyczne w tej ścieżce.")
        sys.exit(1)
        
    # Wczytanie profilu talii (Gilded)
    profile_path = "assets/decks/gilded/deck_profile.json"
    try:
        deck_profile = DeckProfile.load(profile_path)
        print(f"Pomyślnie załadowano profil talii: {deck_profile.deck_name} (aspect ratio: {deck_profile.aspect_ratio_height_to_width:.3f})")
    except Exception as e:
        print(f"Błąd krytyczny: Nie można załadować profilu talii z {profile_path}: {e}")
        sys.exit(1)
        
    # Inicjalizacja komponentów
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    
    # Testujemy wykryte sesje
    detection_folders = sorted([d for d in detections_dir.iterdir() if d.is_dir()])
    if not detection_folders:
        print("Błąd: Brak folderów detekcji w katalogu diagnostycznym.")
        sys.exit(1)
        
    print(f"Znaleziono {len(detection_folders)} rekordów diagnostycznych.")
    
    all_passed = True
    
    for df in detection_folders:
        print(f"\n--- Analiza rekordu: {df.name} ---")
        prev_path = df / "previous.png"
        curr_path = df / "current.png"
        
        if not prev_path.exists() or not curr_path.exists():
            print(f"  Pominięto {df.name}: brak previous.png lub current.png")
            continue
            
        # Wczytanie obrazów
        prev_img = cv2.imread(str(prev_path))
        curr_img = cv2.imread(str(curr_path))
        
        if prev_img is None or curr_img is None:
            print(f"  Pominięto {df.name}: błąd odczytu obrazów")
            continue
            
        # Wczytanie oryginalnego statusu z metadanych
        meta_path = df / "metadata.json"
        expected_status = "accepted"
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                expected_status = meta.get("status", "accepted")
            except Exception:
                pass
                
        if expected_status == "no_roi":
            print(f"  Pominięto {df.name}: poprawny brak ROI (status: no_roi).")
            continue

        # Wykrycie ROI i maski
        roi_rect, debug_mask = diff_detector.detect_change_roi(curr_img, prev_img)
        
        if roi_rect is None:
            print(f"  Błąd: Detektor różnicowy nie wykrył zmiany w {df.name} (oryginalny status: {expected_status})")
            all_passed = False
            continue
            
        # Rafinacja z maską i profilem
        card_data = refinery.refine_card(curr_img, roi_rect, diff_mask=debug_mask, deck_profile=deck_profile)
        
        if card_data is None:
            print(f"  Błąd: Rafinacja krawędzi nie powiodła się dla {df.name} (oryginalny status: {expected_status})")
            all_passed = False
            continue
            
        # Analiza geometrii wyniku
        cx, cy = card_data["center"]
        w, h = card_data["size"]
        angle = card_data["angle"]
        corners = card_data["corners"]
        source = card_data.get("frame_source", "unknown")
        
        detected_ratio = max(w, h) / min(w, h) if min(w, h) > 0 else 0
        expected_ratio = deck_profile.aspect_ratio_height_to_width
        ratio_diff = abs(detected_ratio - expected_ratio)
        
        print(f"  Wynik dopasowania: {source}")
        print(f"  Środek: ({cx}, {cy}), Rozmiar: {w}x{h}, Kąt: {angle:.2f}°")
        print(f"  Proporcje boków: wykryta={detected_ratio:.3f}, oczekiwana={expected_ratio:.3f} (Różnica: {ratio_diff:.4f})")
        
        # Sprawdzamy czy różnica proporcji jest znikoma
        ratio_tolerance = 0.02
        if ratio_diff > ratio_tolerance:
            print(f"  [BŁĄD] Proporcje karty odbiegają od modelu talii o {ratio_diff:.4f} (tolerancja {ratio_tolerance})")
            all_passed = False
        else:
            print(f"  [OK] Proporcje karty są poprawne i zgodne z modelem talii.")
            
        # Dodatkowo sprawdzamy czy rozmiar nie jest zbyt mały (błąd z obcinaniem do rysunku)
        # Dla drugiej karty w poprzek, stary algorytm dawał np. 138x166, co jest za małe
        # (cała karta ma dłuższą krawędź min. 220px w rozdzielczości stołu)
        min_card_dimension = 200
        if max(w, h) < min_card_dimension:
            print(f"  [BŁĄD] Wykryty wymiar karty ({max(w, h)}) jest zbyt mały (oczekiwano > {min_card_dimension}px)")
            all_passed = False
        else:
            print(f"  [OK] Rozmiar karty jest fizycznie poprawny ({max(w, h)}px).")
            
        # Rysowanie ramki weryfikacyjnej
        verified_img = curr_img.copy()
        box = np.intp(corners)
        cv2.drawContours(verified_img, [box], -1, (0, 255, 0), 3) # zielona dopasowana
        
        # Narysujmy też pierwotny kontur dla porównania (jeśli był w starych metadanych)
        meta_path = df / "metadata.json"
        if meta_path.exists():
            try:
                with open(meta_path, "r") as f:
                    meta = json.load(f)
                if meta.get("metadata"):
                    old_corners = meta["metadata"][0]["corners"]
                    old_box = np.intp(old_corners)
                    cv2.drawContours(verified_img, [old_box], -1, (0, 0, 255), 2) # czerwona stara
                    cv2.putText(verified_img, "STARA", (old_corners[0][0], old_corners[0][1] - 5),
                                cv2.FONT_HERSHEY_SIMPLEX, 0.5, (0, 0, 255), 1)
            except Exception:
                pass
                
        cv2.circle(verified_img, (cx, cy), 7, (0, 255, 255), -1)
        cv2.putText(verified_img, f"NOWA ({source})", (int(corners[0][0]), int(corners[0][1]) - 10),
                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 0), 2)
                    
        # Zapisz obraz w processed
        test_out_path = output_dir / f"test_refinery_{df.name}.png"
        cv2.imwrite(str(test_out_path), verified_img)
        print(f"  Zapisano obraz weryfikacyjny: {test_out_path}")
        
    print("\n=================================================================")
    if all_passed:
        print("WYNIK KOŃCOWY: SUKCES - Wszystkie rekordy poprawnie dopasowane modelowo.")
        sys.exit(0)
    else:
        print("WYNIK KOŃCOWY: PORAŻKA - Wykryto niepoprawne dopasowania.")
        sys.exit(1)

if __name__ == "__main__":
    run_diagnostics_test()

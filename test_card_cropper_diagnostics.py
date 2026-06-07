import sys
import os
import cv2
import numpy as np
import json
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.decks.library import DeckLibrary
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery
from tarotvision.vision.cropper import CardCropper

def run_cropper_diagnostics():
    print("=== TarotVision: Test Diagnostyczny Wycinania Kart (Offline) ===")
    
    # 1. Przygotowanie ścieżek
    detections_dir = Path("output/sessions/current/detections")
    output_crops_dir = Path("output/processed/crops")
    output_crops_dir.mkdir(parents=True, exist_ok=True)
    
    if not detections_dir.exists():
        print("Brak rekordów diagnostycznych. Uruchom najpierw test_card_detection_diff.py albo przygotuj dane testowe.")
        sys.exit(0) # Zgodnie z wymaganiem kończymy bez stack trace
        
    # Wczytanie profilu talii (Gilded)
    try:
        library = DeckLibrary()
        active_profiles = library.load_active_profiles()
        gilded_profile = next((p for p in active_profiles if p.deck_id == "gilded"), None)
        if gilded_profile:
            print(f"Załadowano profil talii: {gilded_profile.deck_name} (aspect ratio: {gilded_profile.aspect_ratio_height_to_width:.3f})")
        else:
            print("Błąd: Nie znaleziono profilu gilded w aktywnej bibliotece.")
            sys.exit(1)
    except Exception as e:
        print(f"Błąd krytyczny podczas ładowania biblioteki talii: {e}")
        sys.exit(1)
        
    # Inicjalizacja komponentów
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    cropper = CardCropper()
    
    detection_folders = sorted([d for d in detections_dir.iterdir() if d.is_dir()])
    if not detection_folders:
        print("Brak rekordów diagnostycznych. Uruchom najpierw test_card_detection_diff.py albo przygotuj dane testowe.")
        sys.exit(0)
        
    print(f"Znaleziono {len(detection_folders)} rekordów diagnostycznych.")
    
    all_passed = True
    
    for df in detection_folders:
        print(f"\n--- Analiza rekordu: {df.name} ---")
        
        # Wczytanie statusu
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
            print(f"  Pominięto {df.name}: status no_roi (brak karty na stole).")
            continue
            
        prev_path = df / "previous.png"
        curr_path = df / "current.png"
        
        if not prev_path.exists() or not curr_path.exists():
            print(f"  Pominięto {df.name}: brak previous.png lub current.png")
            continue
            
        prev_img = cv2.imread(str(prev_path))
        curr_img = cv2.imread(str(curr_path))
        
        if prev_img is None or curr_img is None:
            print(f"  Pominięto {df.name}: błąd odczytu obrazów")
            continue
            
        # 2. Uruchomienie DiffDetector
        roi_rect, debug_mask = diff_detector.detect_change_roi(curr_img, prev_img)
        if roi_rect is None:
            print(f"  [BŁĄD] Detektor różnicowy nie wykrył zmiany w {df.name} (oczekiwano: {expected_status})")
            all_passed = False
            continue
            
        # 3. Uruchomienie CardRefinery
        card_data = refinery.refine_card(curr_img, roi_rect, diff_mask=debug_mask, deck_profiles=active_profiles)
        if card_data is None:
            print(f"  [BŁĄD] Rafinacja krawędzi nie powiodła się dla {df.name}")
            all_passed = False
            continue
            
        # 4. Uruchomienie CardCropper
        crop_res = cropper.crop_card(curr_img, card_data, gilded_profile)
        if crop_res is None or not crop_res.get("success"):
            print(f"  [BŁĄD] Wycinanie karty (crop) nie powiodło się dla {df.name}")
            all_passed = False
            continue
            
        crop_img = crop_res["crop_image"]
        h_crop, w_crop = crop_img.shape[:2]
        
        # Weryfikacja wymiarów
        expected_w = gilded_profile.canonical_width_px if gilded_profile.canonical_width_px else 600
        expected_h = gilded_profile.canonical_height_px if gilded_profile.canonical_height_px else 1032
        
        print(f"  Wymiary cropa: {w_crop}x{h_crop} px (oczekiwano: {expected_w}x{expected_h} px)")
        
        if w_crop != expected_w or h_crop != expected_h:
            print(f"  [BŁĄD] Wymiary cropa ({w_crop}x{h_crop}) odbiegają od kanonicznych ({expected_w}x{expected_h})")
            all_passed = False
        else:
            print(f"  [OK] Wymiary są poprawne.")
            
        # Weryfikacja czy crop nie jest pusty/czarny
        mean_val = np.mean(crop_img)
        print(f"  Średnia jasność cropa: {mean_val:.2f}")
        if mean_val < 5.0:
            print(f"  [BŁĄD] Obraz cropa wydaje się być pusty lub zbyt ciemny (średnia jasność {mean_val:.2f} < 5.0)")
            all_passed = False
        else:
            print(f"  [OK] Obraz cropa nie jest pusty.")
            
        # Zapis crop.png w diagnostyce i centralnym folderze
        diagnostics_crop_path = df / "crop.png"
        cv2.imwrite(str(diagnostics_crop_path), crop_img)
        
        central_crop_path = output_crops_dir / f"card_crop_{df.name}.png"
        cv2.imwrite(str(central_crop_path), crop_img)
        print(f"  Zapisano crop w: {diagnostics_crop_path}")
        print(f"  Zapisano centralny crop w: {central_crop_path}")
        
    print("\n=================================================================")
    if all_passed:
        print("WYNIK KOŃCOWY: SUKCES - Wszystkie cropy wygenerowane pomyślnie.")
        sys.exit(0)
    else:
        print("WYNIK KOŃCOWY: PORAŻKA - Niektóre cropy mają błędy geometryczne lub jasności.")
        sys.exit(1)

if __name__ == "__main__":
    run_cropper_diagnostics()

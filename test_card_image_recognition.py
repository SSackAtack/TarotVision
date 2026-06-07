import sys
import os
import cv2
import json
from pathlib import Path
import logging

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.recognition.reference_loader import ReferenceLoader
from tarotvision.recognition.image_matcher import ImageMatcher
from tarotvision.recognition.index_loader import ReferenceIndexLoader
from tarotvision.recognition.indexed_matcher import IndexedImageMatcher

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")
logger = logging.getLogger(__name__)

def run_card_recognition_test():
    print("=== TarotVision: Test Rozpoznawania Obrazowego Kart (Offline) ===")
    
    # 1. Przygotowanie ścieżek i katalogów
    detections_dir = Path("output/sessions/current/detections")
    output_rec_dir = Path("output/processed/recognition")
    output_rec_dir.mkdir(parents=True, exist_ok=True)
    
    # 2. Załadowanie referencji
    loader = ReferenceLoader()
    deck_id = "gilded"
    references = loader.load_references(deck_id)
    
    if not references:
        print(f"\n[BŁĄD/DIAGNOSTYKA] Brak skanów referencyjnych dla talii '{deck_id}' w assets/decks/{deck_id}/reference_scans/.")
        print("Nie można kontynuować testu rozpoznawania.")
        sys.exit(1)
        
    print(f"Załadowano {len(references)} skanów referencyjnych dla talii '{deck_id}'.")
    
    # 3. Wyszukiwanie cropów w sesji diagnostycznej
    if not detections_dir.exists():
        print("\n[INFO] Brak folderu detekcji sesji. Uruchom najpierw test_card_detection_diff.py z kamerą.")
        sys.exit(0)
        
    detection_folders = sorted([d for d in detections_dir.iterdir() if d.is_dir()])
    crop_paths = []
    
    for df in detection_folders:
        crop_file = df / "crop.png"
        if crop_file.exists():
            crop_paths.append((df.name, crop_file))
            
    if not crop_paths:
        print("\n[INFO] Brak wyciętych cropów kart (crop.png) w podkatalogach detekcji.")
        print("Uruchom najpierw test_card_detection_diff.py lub test_card_cropper_diagnostics.py.")
        sys.exit(0)
        
    print(f"Znaleziono {len(crop_paths)} cropów do przetestowania.")
    
    # Wczytanie opcjonalnego profilu kalibracji barwnej
    profile_path = Path("output/sessions/current/session_color_profile.json")
    profile = None
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
            print(f"[INFO] Załadowano profil kalibracji koloru sesji z: {profile_path}")
        except Exception as e:
            print(f"[OSTRZEŻENIE] Błąd podczas ładowania profilu kalibracji: {e}")
            
    # 4. Inicjalizacja matchera (indeksowego lub tradycyjnego fallbacku)
    index_loader = ReferenceIndexLoader()
    index = index_loader.load_index(deck_id)
    
    if index:
        print(f"[INFO] Używam szybkiego matchera indeksowego (IndexedImageMatcher) dla talii '{deck_id}'.")
        matcher = IndexedImageMatcher(index)
        use_indexed = True
    else:
        print(f"[OSTRZEŻENIE] Brak indeksu cech dla talii '{deck_id}'. Używam tradycyjnego matchera (ImageMatcher - fallback).")
        matcher = ImageMatcher(session_color_profile=profile)
        use_indexed = False
        
    results = {}
    
    for name, path in crop_paths:
        print(f"\n--- Rozpoznawanie dla: {name} ({path.name}) ---")
        
        crop_img = cv2.imread(str(path))
        if crop_img is None:
            print(f"  [BŁĄD] Nie można wczytać pliku cropa: {path}")
            continue
            
        # Dopasowanie
        if use_indexed:
            match_res = matcher.match_card(crop_img, session_color_profile=profile)
        else:
            match_res = matcher.match_card(crop_img, references, deck_id)
        
        print(f"  Najlepsze dopasowanie: {match_res['best_reference_id']}")
        print(f"  Talia: {match_res['recognized_deck']}")
        print(f"  Pewność (Confidence): {match_res['confidence']:.4f}")
        print(f"  Wybrana rotacja: {match_res['best_rotation']}°")
        
        if use_indexed and "candidates" in match_res and len(match_res["candidates"]) > 0:
            best_cand = match_res["candidates"][0]
            if "score_breakdown" in best_cand:
                print(f"  Diagnostyczny breakdown cech:")
                for feat, val in best_cand["score_breakdown"].items():
                    print(f"    - {feat}: {val:.4f}")
        
        results[name] = match_res
        
    # 5. Zapis wyników do pliku JSON
    out_json_path = output_rec_dir / "recognition_result.json"
    try:
        with open(out_json_path, "w", encoding="utf-8") as f:
            json.dump({"crops": results}, f, indent=2, ensure_ascii=False)
        print(f"\n[OK] Zapisano zbiorcze wyniki rozpoznawania w: {out_json_path}")
    except Exception as e:
        print(f"\n[BŁĄD] Nie udało się zapisać wyników do {out_json_path}: {e}")
        sys.exit(1)
        
    print("\n=== Test rozpoznawania zakończony pomyślnie. ===")
    sys.exit(0)

if __name__ == "__main__":
    run_card_recognition_test()

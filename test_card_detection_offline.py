import sys
import os
import cv2
import numpy as np
import json
import shutil
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery

def run_offline_test():
    print("--- TarotVision: Test Detekcji Kart w Trybie Offline (Bez Kamery) ---")
    
    # 1. Przygotowanie katalogów
    assets_dir = Path("tests/assets")
    assets_dir.mkdir(parents=True, exist_ok=True)
    
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    empty_table_path = assets_dir / "empty_table.png"
    table_with_card_path = assets_dir / "table_with_card.png"
    
    # 2. Automatyczne kopiowanie próbek z ostatniej sesji (jeśli istnieją i nie ma ich w assets)
    session_dir = Path("output/sessions/current")
    
    if not empty_table_path.exists() and (session_dir / "snapshot_0.png").exists():
        shutil.copy(session_dir / "snapshot_0.png", empty_table_path)
        print(f"Skopiowano snapshot_0.png jako {empty_table_path}")
        
    if not table_with_card_path.exists() and (session_dir / "snapshot_current.png").exists():
        shutil.copy(session_dir / "snapshot_current.png", table_with_card_path)
        print(f"Skopiowano snapshot_current.png jako {table_with_card_path}")
        
    # Sprawdzenie dostępności plików
    if not empty_table_path.exists() or not table_with_card_path.exists():
        print(f"Błąd: W katalogu {assets_dir} brakuje plików empty_table.png i table_with_card.png.")
        print("Uruchom najpierw test_card_detection_diff.py z kamerą, aby wygenerować pierwsze próbki.")
        sys.exit(1)
        
    # 3. Wczytanie obrazów
    print(f"Wczytywanie obrazu referencyjnego (pusty stół): {empty_table_path}")
    snap_0 = cv2.imread(str(empty_table_path))
    
    print(f"Wczytywanie obrazu testowego (stół z kartą): {table_with_card_path}")
    snap_current = cv2.imread(str(table_with_card_path))
    
    if snap_0 is None or snap_current is None:
        print("Błąd: Nie można wczytać obrazów testowych.")
        sys.exit(1)
        
    # 4. Inicjalizacja detektorów
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    
    # 5. Uruchomienie detekcji różnicowej (ROI)
    roi_rect, debug_mask = diff_detector.detect_change_roi(snap_current, snap_0)
    cv2.imwrite(str(output_dir / "debug_diff_mask_offline.png"), debug_mask)
    print(f"-> Zapisano maskę różnicową offline: {output_dir / 'debug_diff_mask_offline.png'}")
    
    if roi_rect is not None:
        # 6. Precyzyjne dopasowanie karty w ROI
        card_data = refinery.refine_card(snap_current, roi_rect)
        
        if card_data is not None:
            # Przygotowanie metadanych JSON
            cards_metadata = [{
                "id": "card_offline_001",
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
            
            # Zapis JSON
            json_path = output_dir / "detected_cards_offline.json"
            with open(json_path, "w", encoding="utf-8") as f:
                json.dump(cards_metadata, f, indent=2, ensure_ascii=False)
            print(f"-> Zapisano metadane JSON: {json_path}")
            
            # Rysowanie ramki diagnostycznej
            output_image = snap_current.copy()
            box = np.intp(card_data["corners"])
            cv2.drawContours(output_image, [box], -1, (0, 255, 0), 3)
            cv2.circle(output_image, card_data["center"], 7, (0, 0, 255), -1)
            cv2.putText(output_image, "card_offline_001", (card_data["center"][0] - 25, card_data["center"][1] - 15),
                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                        
            # Zapis obrazu
            output_image_path = output_dir / "table_detected_offline.png"
            cv2.imwrite(str(output_image_path), output_image)
            print(f"-> Zapisano obraz z ramką: {output_image_path}")
            
            print("\n--- Podsumowanie testu offline ---")
            print("Wynik: SUKCES - Karta została poprawnie zlokalizowana offline.")
            print(f"Wykryto kartę w środku {card_data['center']} pod kątem {card_data['angle']:.2f}°.")
            sys.exit(0)
        else:
            print("\nWynik: PORAŻKA - Rafinacja krawędzi karty w ROI nie powiodła się.")
            sys.exit(1)
    else:
        print("\nWynik: PORAŻKA - Detektor różnicowy nie znalazł żadnej zmiany (ROI).")
        sys.exit(1)

if __name__ == "__main__":
    run_offline_test()

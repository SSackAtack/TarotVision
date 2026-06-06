import sys
import os
import cv2
import json
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.vision.detector import CardDetector

def test_card_detection():
    print("--- Rozpoczęcie testu detekcji prostokątów kart ---")
    
    input_image_path = "output/processed/table_cropped.png"
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Wczytanie obrazu stołu
    print(f"Wczytywanie wyprostowanego obrazu stołu: {input_image_path}")
    image = cv2.imread(input_image_path)
    if image is None:
        print(f"Błąd: Nie można wczytać pliku {input_image_path}.")
        print("Upewnij się, że wcześniej uruchomiłeś test_perspective_correction.py.")
        sys.exit(1)
        
    # 2. Inicjalizacja detektora kart
    # Tarot card standard size is around 12x7cm. Aspect ratio ~ 1.7
    detector = CardDetector(
        min_area=10000, 
        max_area=150000, 
        min_aspect_ratio=1.3, 
        max_aspect_ratio=2.0
    )
    
    # 3. Uruchomienie detekcji
    output_image, cards_metadata = detector.detect_cards(image)
    
    # 4. Zapis obrazu wynikowego
    output_image_path = output_dir / "table_detected.png"
    cv2.imwrite(str(output_image_path), output_image)
    print(f"-> Zapisano obraz z ramkami: {output_image_path}")
    
    # 5. Zapis metadanych JSON
    metadata_path = output_dir / "detected_cards.json"
    with open(metadata_path, "w", encoding="utf-8") as f:
        json.dump(cards_metadata, f, indent=2, ensure_ascii=False)
    print(f"-> Zapisano metadane JSON: {metadata_path}")
    
    # 6. Podsumowanie
    print("\n--- Podsumowanie testu ---")
    if len(cards_metadata) > 0:
        print(f"Wynik: SUKCES")
        print(f"Wykryto kart: {len(cards_metadata)}")
        for card in cards_metadata:
            print(f"  {card['id']}: środek=({card['position']['x']}, {card['position']['y']}), kąt={card['angle']}°")
        sys.exit(0)
    else:
        print("Wynik: PORAŻKA - Nie wykryto żadnej karty na wyprostowanym stole.")
        sys.exit(1)

if __name__ == "__main__":
    test_card_detection()

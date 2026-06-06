import sys
import os
import cv2
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.vision.perspective import TablePerspectiveCorrector

def get_latest_capture(directory: str = "output/captures") -> Path:
    path = Path(directory)
    files = list(path.glob("*.png")) + list(path.glob("*.jpg"))
    if not files:
        return None
    return max(files, key=lambda x: x.stat().st_mtime)

def test_perspective():
    print("--- Rozpoczęcie testu korekcji perspektywy stołu ---")
    
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # 1. Wyszukanie najnowszego obrazu
    latest_capture = get_latest_capture()
    if latest_capture is None:
        print("Błąd: Brak plików w output/captures/. Najpierw uruchom test_image_storage.py.")
        sys.exit(1)
        
    print(f"Wczytywanie najnowszego obrazu testowego: {latest_capture}")
    image = cv2.imread(str(latest_capture))
    if image is None:
        print(f"Błąd: Nie można wczytać pliku {latest_capture}.")
        sys.exit(1)
        
    corrector = TablePerspectiveCorrector()
    
    # 2. Test opcji przyciętej (crop_to_markers = True)
    print("\nGenerowanie wersji PRZYCIĘTEJ (tylko stół)...")
    warped_cropped, matrix_cropped = corrector.get_warped_table(image, crop_to_markers=True)
    if warped_cropped is not None:
        path_cropped = output_dir / "table_cropped.png"
        cv2.imwrite(str(path_cropped), warped_cropped)
        print(f"-> Zapisano wersję przyciętą: {path_cropped}")
    else:
        print("-> Błąd: Nie udało się wygenerować wersji przyciętej.")
        sys.exit(1)
        
    # 3. Test opcji pełnej (crop_to_markers = False)
    print("\nGenerowanie wersji PEŁNEJ (z otoczeniem)...")
    warped_full, matrix_full = corrector.get_warped_table(image, crop_to_markers=False)
    if warped_full is not None:
        path_full = output_dir / "table_full.png"
        cv2.imwrite(str(path_full), warped_full)
        print(f"-> Zapisano wersję pełną: {path_full}")
    else:
        print("-> Błąd: Nie udało się wygenerować wersji pełnej.")
        sys.exit(1)
        
    # 4. Weryfikacja końcowa
    if path_cropped.exists() and path_full.exists():
        print("\n--- Podsumowanie testu ---")
        print("Wynik: SUKCES")
        print(f"Wersja przycięta: {path_cropped} (Rozmiar: {path_cropped.stat().st_size} bajtów)")
        print(f"Wersja pełna: {path_full} (Rozmiar: {path_full.stat().st_size} bajtów)")
        sys.exit(0)
    else:
        print("\nWynik: PORAŻKA - Pliki nie zostały poprawnie zapisane.")
        sys.exit(1)

if __name__ == "__main__":
    test_perspective()

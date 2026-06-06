import sys
import os
import cv2
from pathlib import Path
from pygrabber.dshow_graph import FilterGraph

# Dodanie katalogu src do ścieżki wyszukiwania modułów
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture
from tarotvision.storage.writer import ImageWriter

def find_active_camera_index() -> int:
    """
    Szybko znajduje indeks kamery szukając po nazwie urządzenia w DirectShow.
    Eliminuje to powolne odpytywanie wideo i limity czasowe.
    """
    print("Szybkie skanowanie nazw urządzeń DirectShow...")
    try:
        graph = FilterGraph()
        devices = graph.get_input_devices()
        
        # 1. Szukamy Nvidia Broadcast lub AnkerWork
        for index, name in enumerate(devices):
            if "NVIDIA Broadcast" in name or "AnkerWork" in name:
                print(f"-> Dopasowanie: Znaleziono '{name}' na indeksie {index}.")
                return index
                
        # 2. Szukamy czegokolwiek co nie jest NDI ani OBS
        for index, name in enumerate(devices):
            if "NDI" not in name and "OBS" not in name:
                print(f"-> Alternatywa: Wybrano '{name}' na indeksie {index}.")
                return index
                
        # 3. Jeśli są tylko wirtualne, bierzemy pierwsze lepsze
        if devices:
            print(f"-> Fallback: Brak dedykowanych kamer, wybieram '{devices[0]}' na indeksie 0.")
            return 0
            
    except Exception as e:
        print(f"Błąd pygrabber: {e}. Używam domyślnego indeksu 0.")
        
    return 0

def test_storage():
    print("--- Rozpoczęcie testu modułu ImageWriter ---")
    
    output_dir = "output/captures"
    
    # 1. Autodetekcja indeksu kamery po nazwie
    camera_index = find_active_camera_index()
    print(f"Wybrany indeks kamery do testu: {camera_index}")
    
    # 2. Inicjalizacja kamery i pobranie klatki
    try:
        with CameraCapture(camera_index=camera_index, width=1920, height=1080) as cam:
            if cam.cap is not None and cam.cap.isOpened():
                success, frame = cam.get_frame()
                if not success or frame is None:
                    print("Błąd: Nie udało się pobrać klatki z wybranej kamery.")
                    sys.exit(1)
                
                print(f"Pomyślnie pobrano klatkę z kamery {camera_index}. Rozdzielczość: {frame.shape[1]}x{frame.shape[0]}")
                
                # 3. Inicjalizacja ImageWriter i zapis
                writer = ImageWriter(base_output_dir=output_dir)
                saved_path = writer.save_image(frame, prefix="test_capture")
                
                # 4. Weryfikacja
                if saved_path.exists() and saved_path.stat().st_size > 7923:
                    print("\n--- Podsumowanie testu ---")
                    print("Wynik: SUKCES")
                    print(f"Użyta kamera (indeks): {camera_index}")
                    print(f"Zapisana klatka: {saved_path}")
                    print(f"Rozmiar pliku: {saved_path.stat().st_size} bajtów (potwierdzony obraz nie-czarny)")
                    sys.exit(0)
                else:
                    print(f"Błąd: Plik nie został utworzony lub jest pusty/czarny (rozmiar {saved_path.stat().st_size} bajtów).")
                    sys.exit(1)
            else:
                print(f"Błąd: Nie udało się otworzyć kamery o indeksie {camera_index}.")
                sys.exit(1)
                
    except Exception as e:
        print(f"Wystąpił nieoczekiwany błąd podczas testu: {e}")
        sys.exit(1)

if __name__ == "__main__":
    test_storage()

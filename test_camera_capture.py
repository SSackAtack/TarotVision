import sys
import os

# Dodanie katalogu src do ścieżki wyszukiwania modułów
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture

def test_camera():
    print("--- Rozpoczęcie testu modułu CameraCapture ---")
    
    # Przeskanujmy indeksy od 0 do 3 w poszukiwaniu działającej kamery
    working_camera_index = None
    frame_shape = None

    for index in range(4):
        print(f"Testowanie indeksu kamery: {index}...")
        try:
            with CameraCapture(camera_index=index) as cam:
                if cam.cap is not None and cam.cap.isOpened():
                    success, frame = cam.get_frame()
                    if success and frame is not None:
                        working_camera_index = index
                        frame_shape = frame.shape
                        print(f"-> SUKCES! Kamera o indeksie {index} działa. Wymiary klatki: {frame_shape[1]}x{frame_shape[0]} (szer x wys)")
                        break
                    else:
                        print(f"-> Kamera o indeksie {index} otworzyła się, ale nie udało się pobrać klatki.")
                else:
                    print(f"-> Nie udało się otworzyć kamery o indeksie {index}.")
        except Exception as e:
            print(f"-> Błąd podczas testowania indeksu {index}: {e}")

    print("\n--- Podsumowanie testu ---")
    if working_camera_index is not None:
        print(f"Wynik: SUKCES")
        print(f"Działający indeks kamery: {working_camera_index}")
        print(f"Rozdzielczość: {frame_shape[1]}x{frame_shape[0]}")
        sys.exit(0)
    else:
        print("Wynik: PORAŻKA - Nie znaleziono żadnej działającej kamery.")
        sys.exit(1)

if __name__ == "__main__":
    test_camera()

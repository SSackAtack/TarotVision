import sys
import os
import cv2
from pygrabber.dshow_graph import FilterGraph

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture

def find_active_camera_index() -> int:
    """
    Szybko znajduje indeks kamery szukając po nazwie urządzenia w DirectShow.
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

def test_camera_live_window():
    print("--- Test Okna Podglądu na Żywo (Szybka Autodetekcja) ---")
    
    # Inicjalizacja indeksu kamery po nazwie
    camera_index = find_active_camera_index()
    print(f"Wybrany indeks kamery do podglądu: {camera_index}")
    
    try:
        cam = CameraCapture(camera_index=camera_index, width=1920, height=1080)
        if cam.open():
            success, frame = cam.get_frame()
            if success and frame is not None:
                print(f"-> Sukces! Otwarto podgląd dla kamery na indeksie {camera_index}.")
                print("Wciśnij klawisz ESC w oknie wideo, aby zakończyć test.")
                
                try:
                    while True:
                        success, frame = cam.get_frame()
                        if not success or frame is None:
                            print("Błąd: Utracono połączenie.")
                            break
                        
                        cv2.imshow(f"TarotVision Live Test (Kamera {camera_index}) - Wcisnij ESC aby zamknac", frame)
                        
                        key = cv2.waitKey(30) & 0xFF
                        if key == 27:
                            print("Zamknięto klawiszem ESC.")
                            break
                finally:
                    cv2.destroyAllWindows()
                    cam.release()
            else:
                print(f"Błąd: Nie można pobrać obrazu z kamery {camera_index}.")
                cam.release()
        else:
            print(f"Błąd: Nie można otworzyć kamery o indeksie {camera_index}.")
    except Exception as e:
        print(f"Wyjątek: {e}")

if __name__ == "__main__":
    test_camera_live_window()

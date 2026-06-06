import sys
import os
import cv2
import numpy as np

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture
from tarotvision.storage.writer import ImageWriter

def scan_cameras():
    print("--- Skanowanie kamer i sprawdzanie jasności klatek ---")
    writer = ImageWriter(base_output_dir="output/captures")
    
    for index in range(5):
        print(f"\n--- Test kamery o indeksie {index} ---")
        try:
            with CameraCapture(camera_index=index) as cam:
                if cam.cap is not None and cam.cap.isOpened():
                    success, frame = cam.get_frame()
                    if success and frame is not None:
                        # Obliczenie średniej jasności pikseli (0-255)
                        avg_brightness = np.mean(frame)
                        print(f"Indeks {index}: Pobrano klatkę. Rozdzielczość: {frame.shape[1]}x{frame.shape[0]}")
                        print(f"Średnia jasność pikseli: {avg_brightness:.2f}")
                        
                        # Zapiszmy klatkę do analizy
                        saved_path = writer.save_image(frame, prefix=f"scan_cam_{index}_bright_{int(avg_brightness)}")
                        print(f"Zapisano jako: {saved_path}")
                        
                        if avg_brightness < 2.0:
                            print("-> UWAGA: Obraz jest niemal całkowicie czarny. Prawdopodobnie to czarna wirtualna kamera lub zasłonięty obiektyw.")
                        else:
                            print("-> SUKCES: Obraz zawiera rzeczywiste dane (nie jest czarny)!")
                    else:
                        print(f"Indeks {index}: Połączenie nawiązane, ale błąd pobierania klatki.")
                else:
                    print(f"Indeks {index}: Nie można otworzyć kamery.")
        except Exception as e:
            print(f"Indeks {index}: Wyjątek: {e}")

if __name__ == "__main__":
    scan_cameras()

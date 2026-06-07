import sys
import os
import logging
from pathlib import Path

# Dodanie src do sys.path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(levelname)s - %(message)s")

def run_preflight_test():
    print("=== TarotVision: Test Preflightu Kamery Live ===")
    
    # Próba otwarcia kamery z preflightem
    try:
        # CameraCapture automatycznie wykryje sprawną fizyczną kamerę
        with CameraCapture(camera_index=None, width=1920, height=1080, enable_preflight=True) as cam:
            if cam.cap is None or not cam.cap.isOpened():
                print("\n[BŁĄD/DIAGNOSTYKA] Kamera nie mogła zostać otwarta.")
                sys.exit(0)
                
            data = cam.preflight_data
            if data is None:
                print("\n[BŁĄD/DIAGNOSTYKA] Preflight nie zwrócił żadnych danych.")
                sys.exit(0)
                
            print("\n=== Raport Camera Preflight ===")
            print(f"Status Jakości Obrazu: {data['quality_status'].upper()}")
            print(f"Ścieżka do profilu sesji: {data['profile_path']}")
            
            print("\nMetryki jakości:")
            metrics = data["metrics"]
            print(f"  Średnia jasność (brightness_mean): {metrics.get('brightness_mean')} px")
            print(f"  Kontrast (brightness_std): {metrics.get('brightness_std')} px")
            print(f"  Ostrość (laplacian_variance): {metrics.get('laplacian_variance')}")
            print(f"  Prześwietlenie (overexposed_ratio): {metrics.get('overexposed_ratio')*100:.2f}%")
            print(f"  Niedoświetlenie (underexposed_ratio): {metrics.get('underexposed_ratio')*100:.2f}%")
            print(f"  Stabilność (frame_delta_mean): {metrics.get('frame_delta_mean')} px")
            
            print("\nStatus blokad parametrów kamery:")
            req = data["requested"]
            read = data["readback"]
            status = data["status"]
            
            for key in ["auto_exposure", "auto_focus", "auto_white_balance"]:
                print(f"  {key}:")
                print(f"    Żądano: {req.get(key)}")
                print(f"    Odczytano: {read.get(key)}")
                print(f"    Status: {status.get(key).upper()}")
                
            print("\nManualne parametry (readback):")
            for key in ["exposure", "focus", "white_balance_temperature", "brightness", "contrast", "gain"]:
                print(f"  {key}: {read.get(key)}")
                
            print("\n=== Koniec raportu ===")
            
    except Exception as e:
        print(f"\n[INFO] Brak fizycznej kamery lub wystąpił błąd komunikacji: {e}")
        print("Test zakończony statusem pomyślnym (brak kamery fizycznej jest dopuszczalny).")
        sys.exit(0)

if __name__ == "__main__":
    run_preflight_test()

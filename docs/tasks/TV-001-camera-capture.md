# Zadanie: TV-001

## ID zadania:
TV-001

## Nazwa zadania:
Utwórz moduł pobierania obrazu z kamery

## Cel:
Uruchomienie połączenia z kamerą AnkerWork C310 z poziomu kodu Pythona przy użyciu biblioteki OpenCV i przechwycenie pojedynczej klatki obrazu w czasie rzeczywistym.

## Kontekst projektu:
Zadanie stanowi pierwszy krok w warstwie TarotVision Core (moduł `camera`). Odpowiada za dostarczenie strumienia wejściowego wideo do dalszych etapów detekcji.

## Zakres:
1. Konfiguracja środowiska wirtualnego w PyCharm.
2. Napisanie skryptu/modułu Pythona inicjującego przechwytywanie wideo (obiekt `cv2.VideoCapture`).
3. Wybór odpowiedniego indeksu kamery dla AnkerWork C310.
4. Pobranie pojedynczej klatki obrazu i weryfikacja jej poprawności (czy klatka nie jest pusta).
5. Zamknięcie zasobów kamery po zakończeniu pracy.

## Poza zakresem:
* Analiza obrazu i wykrywanie krawędzi/prostokątów (zakres TV-003).
* Zapisywanie plików na dysku (zakres TV-002).
* Wyświetlanie okna z podglądem na żywo (tylko testowe).

## Pliki do utworzenia lub zmiany:
* `requirements.txt` (dodanie OpenCV)
* `src/tarotvision/camera/capture.py` (moduł kamery)
* `test_camera_capture.py` (skrypt testowy)

## Wymagania techniczne:
* Python 3.10+
* opencv-python
* Zgodność z systemem Windows i kamerą USB (UVC).

## Interfejs wejścia:
* Konfiguracja (indeks kamery lub ID urządzenia, opcjonalnie rozdzielczość).

## Interfejs wyjścia:
* Obiekt obrazu NumPy (klatka wideo w formacie BGR) lub błąd/brak sygnału.

## Kryteria akceptacji:
* Skrypt uruchamia się bez błędów.
* Zwracana jest prawidłowa, niepusta klatka obrazu z podłączonej kamery.
* Po zakończeniu przechwytywania zasoby kamery są prawidłowo zwalniane (`cap.release()`).

## Test ręczny:
* Podłącz kamerę AnkerWork C310 do laptopa HP EliteBook.
* Uruchom skrypt `test_camera_capture.py`.
* Konsola powinna wypisać komunikat o sukcesie oraz wymiary pobranego obrazu (np. 1920x1080).

## Uwagi integracyjne:
* Moduł ten będzie bezpośrednio wykorzystywany przez moduł zapisu zdjęć (TV-002) oraz moduł detekcji kart (TV-003).

---

## Wynik testu
*   **Data testu:** 2026-06-06
*   **System:** Microsoft Windows (Build 22000)
*   **Ścieżka projektu:** `E:\Antigravity\Projekty\TarotVision`

Wynik:
*   Kamera wykryta poprawnie (indeks `0`).
*   Użyty backend `cv2.CAP_DSHOW` (DirectShow) rozwiązał problemy z przechwytywaniem klatek na Windowsie.
*   Pomyślnie przechwycono klatkę o rzeczywistej rozdzielczości **1920x1080** (Full HD).
*   Zasoby kamery są prawidłowo i bezpiecznie zwalniane.

**Status:**
Zadanie TV-001 zaakceptowane i zakończone.


# TV-012: Camera Preflight, Quality Check and Parameter Lock

Status: Zakończone

## 1. Cel zadania
Dodanie procedury weryfikacji jakości klatek z kamery (Camera Preflight) oraz próby zablokowania parametrów ekspozycji, ostrości i balansu bieli przed rozpoczęciem sesji. Ma to na celu ustabilizowanie warunków oświetleniowych i wizyjnych na potrzeby modułu rozpoznawania cropów (TV-011).

## 2. Problem i wyzwania
Różne kamery i sterowniki (zwłaszcza przy użyciu OpenCV na Windows z DirectShow) posiadają ograniczone lub niepełne wsparcie dla blokowania parametrów takich jak autoekspozycja, autofokus czy balans bieli. Wymuszenie twardej blokady mogłoby uniemożliwić uruchomienie programu na niektórych urządzeniach.

## 3. Rozwiązanie (Dwuwarstwowe)
- **Warstwa A (Próba blokady):** System podejmuje próbę wyłączenia automatyki i ustawienia wartości manualnych na podstawie konfiguracji.
- **Warstwa B (Weryfikacja jakości i readback):** Niezależnie od sukcesu blokady, system sprawdza rzeczywiste wartości (`cap.get()`), rejestruje status (`applied`, `not_applied`, `unsupported`, `unknown`) oraz analizuje jakość klatek (jasność, ostrość, prześwietlenie, stabilność). Wyniki są zapisywane i prezentowane operatorowi.

## 4. Metryki jakości obrazu
- `brightness_mean`: Średnia jasność obrazu w skali szarości.
- `brightness_std`: Kontrast (odchylenie standardowe jasności).
- `laplacian_variance`: Miara ostrości (wariancja filtra Laplasjana).
- `overexposed_ratio`: Udział pikseli prześwietlonych (jasność >= 250).
- `underexposed_ratio`: Udział pikseli niedoświetlonych (jasność <= 5).
- `frame_delta_mean`: Średnia różnica pikseli między klatkami (stabilność strumienia).

## 5. Zakres TV-012
- Utworzenie konfiguracji progów jakościowych i parametrów blokad `config/camera_settings.json`.
- Implementacja modułu `tarotvision.camera.settings` do aplikacji konfiguracji kamery.
- Implementacja modułu `tarotvision.camera.preflight` do liczenia metryk i generowania profilu `camera_profile.json`.
- Integracja z `CameraCapture` w celu automatycznego lub ręcznego uruchomienia preflightu po warm-upie.
- Integracja z `test_card_detection_diff.py` — wyświetlenie przejrzystego statusu jakości operatorowi przed utworzeniem `Snapshot_0`.
- Skrypt testowy jakości obrazu offline `test_camera_quality_metrics.py`.
- Skrypt testowy preflightu live `test_camera_preflight.py`.

## 6. Wyniki Realizacji i Weryfikacji Live
Preflight został pomyślnie uruchomiony na kamerze fizycznej **AnkerWork C310 Webcam** po wdrożeniu poprawionej, rygorystycznej logiki weryfikacji.

### Wyniki metryk jakościowych:
- `brightness_mean`: **77.19 px** (w przedziale [50, 190] - OK)
- `brightness_std`: **43.86 px** (OK)
- `laplacian_variance`: **300.76** (wysoka ostrość, próg min 80 - OK)
- `overexposed_ratio`: **0.03%** (próg max 2% - OK)
- `underexposed_ratio`: **3.15%** (próg max 5% - OK)
- `frame_delta_mean`: **2.27 px** (próg max 3.0 px - OK)
- **Status ogólny jakości:** **ACCEPTED**

### Precyzyjny status blokad parametrów (readback):
- `auto_white_balance`: **APPLIED** (żądanego stanu `0.0` odpowiada odczytana wartość: `0.0` - automatyczny balans bieli został prawidłowo wyłączony).
- `auto_focus`: **NOT_APPLIED** (żądanego stanu `0.0` nie odpowiada odczytana wartość: `2.0` - sterownik zaakceptował polecenie `cap.set`, ale rzeczywisty stan nie uległ zmianie. Wyeliminowano fałszywy sukces).
- `auto_exposure`: **UNSUPPORTED** (OpenCV/DirectShow nie obsługuje programowej blokady ekspozycji, odczytana wartość: `unsupported`).

Profil sesji kamery został pomyślnie zapisany w: `output/sessions/current/camera_profile.json`.

## 7. Kryteria akceptacji
- [x] Istnieje moduł preflightu kamery.
- [x] Istnieje konfiguracja `config/camera_settings.json`.
- [x] System liczy 6 wymaganych metryk jakości obrazu.
- [x] System próbuje zablokować auto exposure, autofocus i auto white balance oraz zapisuje rzeczywisty stan (readback).
- [x] Wyniki preflightu są zapisywane w `output/sessions/current/camera_profile.json`.
- [x] Test offline `test_camera_quality_metrics.py` przechodzi bez błędów.
- [x] Test live `test_camera_preflight.py` działa z kamerą lub daje czytelny komunikat o jej braku.
- [x] Operator widzi status preflightu w `test_card_detection_diff.py` przed zatwierdzeniem `Snapshot_0`.
- [x] Dotychczasowe testy (w tym `test_card_image_recognition.py`) nadal przechodzą pomyślnie.

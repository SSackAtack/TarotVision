# Zadanie: TV-005 (Refinement)

## ID zadania:
TV-005

## Nazwa zadania:
Uporządkowanie i stabilizacja snapshot-diff MVP

## Cel:
Uporządkowanie nowo powstałego mechanizmu detekcji różnicowej snapshotów. Przeniesienie filtracji czarnych klatek do modułu kamery, dodanie testów offline oraz uzupełnienie zależności w `requirements.txt`.

---

## Zakres prac:

1.  **requirements.txt:**
    *   Wpisanie rzeczywistych zależności projektu: `opencv-python`, `numpy`, `pygrabber` (dla Windows).
2.  **Przeniesienie filtracji czarnych klatek do `CameraCapture`:**
    *   Klasa `CameraCapture` powinna podczas otwierania sprawdzić, czy obraz z kamery nie jest czarny (jasność < 5.0).
    *   Jeśli obraz jest czarny (np. wirtualna kamera w spoczynku), `CameraCapture` powinna spróbować otworzyć kolejny port wideo lub rzucić błąd. Usunie to konieczność ręcznego skanowania w skryptach testowych.
3.  **Weryfikacja trybu Snapshot_0 (Ręczny vs Automatyczny preflight):**
    *   Ustalenie strategii: preflight automatyczny może sprawdzić, czy obraz jest stabilny i zapisać go jako Snapshot_0 automatycznie w tle po starcie sesji, jeśli operator zagwarantuje, że stół jest pusty.
4.  **Test offline (`test_card_detection_offline.py`):**
    *   Stworzenie skryptu testującego detekcję bez kamery.
    *   Wykorzystuje dwa wczytane obrazy testowe: `empty_table.png` (Snapshot_0) oraz `table_with_card.png` (Snapshot_1), uruchamiając na nich wyłącznie logikę `DiffDetector` + `CardRefinery`.

---

## Pliki do utworzenia lub modyfikacji:
*   `requirements.txt`
*   `src/tarotvision/camera/capture.py`
*   `test_card_detection_offline.py`
*   `tests/assets/` (obrazy testowe do testu offline)

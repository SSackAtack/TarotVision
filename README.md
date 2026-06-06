# TarotVision

TarotVision to system komputerowej analizy obrazu (Computer Vision) i prezentacji wizualnej przeznaczony do wspierania prawdziwego czytania tarota.

Projekt jest rozwijany modularnie metodą VibeCodingu przy użyciu agentów AI.

---

## 🚀 Status Projektu: MVP 1 Ukończone

Zakończyliśmy pierwszy kluczowy etap techniczny (MVP 1) – stabilne pobieranie obrazu, korekcję perspektywy stołu oraz geometryczną detekcję położenia kart.

### 📸 Strategia Detekcji: Porównywanie Snapshotów (Image Differencing)

Aby wyeliminować zakłócenia takie jak faktura stołu, cienie czy odblaski światła na kartach, wdrożyliśmy zaawansowany przepływ detekcji:

1. **Kalibracja (Snapshot_0):** Na początku sesji operator wykonuje referencyjne zdjęcie pustego stołu (matrycy).
2. **Monitorowanie Ruchu:** System w czasie rzeczywistym analizuje klatki wideo. Wykrywa moment położenia karty (ruch dłoni).
3. **Stabilizacja:** Gdy ruch nad stołem ustaje na co najmniej 0.5s, wykonywany jest nowy snapshot (`Snapshot_current`).
4. **Odejmowanie Tła:** System oblicza różnicę bezwzględną między aktualnym stanem a pustym stołem, izolując nowo położony obiekt (ROI karty).
5. **Precyzyjna Rafinacja:** Wewnątrz wyznaczonego ROI algorytm Otsu precyzyjnie wyznacza krawędzie karty, jej środek oraz kąt obrotu.

---

## 🛠️ Struktura i Zrealizowane Moduły

*   **Pobieranie Obrazu (`src/tarotvision/camera/`):**
    *   `capture.py`: Klasa `CameraCapture` z obsługą DirectShow, warm-upu wideo oraz inteligentną filtracją czarnych klatek (ochrona przed wirtualnymi kamerami).
    *   `motion.py`: Klasa `MotionDetector` odpowiedzialna za wykrywanie ruchu i stabilizację obrazu.
*   **Segmentacja i Wizja (`src/tarotvision/vision/`):**
    *   `perspective.py`: Klasa `TablePerspectiveCorrector` lokalizująca markery narożne ArUco (`DICT_4X4_50` o ID: 10, 11, 12, 13) i prostująca perspektywę stołu.
    *   `diff.py`: Klasa `DiffDetector` wykrywająca ROI karty na podstawie maski różnicowej.
    *   `refinery.py`: Klasa `CardRefinery` dopasowująca precyzyjnie ramkę i kąt karty wewnątrz ROI.
*   **Zarządzanie Snapshotami (`src/tarotvision/storage/`):**
    *   `snapshots.py`: Klasa `SnapshotManager` zoptymalizowana pod kątem pamięci dyskowej (przechowuje historię w RAM, na dysku tylko Snapshot_0 i stan aktualny).

---

## 💻 Jak Uruchomić i Przetestować?

1. Zainstaluj zależności:
   ```powershell
   pip install -r requirements.txt
   ```
2. Uruchom skrypt integracyjny:
   ```powershell
   python test_card_detection_diff.py
   ```
3. Wciśnij **SPACJĘ** w oknie podglądu, aby zapisać referencyjny obraz pustego stołu (`Snapshot_0`).
4. Połóż kartę na stole i cofnij rękę – system automatycznie obrysuje kartę i zapisze metadane w `output/processed/detected_cards.json`.

---

## 📖 Dokumentacja Projektowa

Przed rozpoczęciem dalszych prac zapoznaj się z:
1.  [AGENTS.md](AGENTS.md) — Wskazówki i standardy pracy dla agentów AI.
2.  [docs/01_wizja_biznesowa.md](docs/01_wizja_biznesowa.md) — Wizja i cele biznesowe.
3.  [docs/02_strategia_techniczna.md](docs/02_strategia_techniczna.md) — Architektura i warstwy.
4.  [docs/03_metoda_pracy_i_architektura_modularna.md](docs/03_metoda_pracy_i_architektura_modularna.md) — Modularność i interfejsy JSON.
5.  Zadania szczegółowe w: [docs/tasks/](docs/tasks/)

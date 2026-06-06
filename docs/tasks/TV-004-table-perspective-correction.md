# Zadanie: TV-004

## ID zadania:
TV-004

## Nazwa zadania:
Utwórz moduł korekcji perspektywy stołu na podstawie markerów ArUco

## Cel:
Zaimplementowanie algorytmu wykrywającego 4 narożne markery ArUco (o ID 10, 11, 12, 13) na obrazie stołu, a następnie wyprostowanie perspektywy (Perspective Warp) w celu uzyskania idealnego widoku stołu roboczego z góry (top-down view) z opcjonalną możliwością przycięcia obrazu dokładnie do obszaru wyznaczonego przez te markery lub zachowania pełnego kadru z zachowaniem perspektywy.

## Kontekst projektu:
Moduł ten stanowi kluczowy element warstwy TarotVision Core (moduł `vision`). Pozwala na usunięcie zniekształceń wynikających z kąta ustawienia kamery oraz umożliwia precyzyjne wykadrowanie samego blatu stołu. Wyprostowany i przycięty obraz ułatwi detekcję i pozycjonowanie kart (TV-003).

## Zakres:
1.  Wykrywanie markerów ArUco przy użyciu OpenCV (słownik `DICT_4X4_50`).
2.  Identyfikacja 4 narożników na podstawie przypisanych ID (10 - TL, 11 - TR, 12 - BR, 13 - BL).
3.  Obliczenie punktów docelowych w zależności od parametru `crop_to_markers`:
    *   **Jeśli True (przycięty):** Punkty docelowe to narożniki wyjściowego obrazu `[0,0]`, `[W,0]`, `[W,H]`, `[0,H]`.
    *   **Jeśli False (pełny z marginesem):** Punkty docelowe są odsunięte od krawędzi obrazu o określony margines (np. 15%), dzięki czemu widoczne jest otoczenie poza markerami.
4.  Obliczenie macierzy transformacji perspektywicznej (`cv2.getPerspectiveTransform`).
5.  Wykonanie rzutowania perspektywicznego (`cv2.warpPerspective`) na klatce wideo.
6.  Zwrócenie wyprostowanego obrazu oraz macierzy transformacji.

## Poza zakresem:
*   Rozpoznawanie kart (zakres Etapu 3).
*   Detekcja samych konturów kart (zakres TV-003).

## Pliki do utworzenia lub zmiany:
*   `[NEW]` `src/tarotvision/vision/perspective.py` (moduł korekcji perspektywy)
*   `[NEW]` `test_perspective_correction.py` (skrypt testowy)
*   `[MODIFY]` `docs/tasks/TV-004-table-perspective-correction.md` (dopisanie wyników na końcu po realizacji)

## Wymagania techniczne:
*   Python 3.10+
*   OpenCV z obsługą ArUco (`cv2.aruco`)
*   Użycie słownika `cv2.aruco.DICT_4X4_50`

## Interfejs wejścia:
*   Obraz NumPy BGR (klatka 1920x1080).
*   `crop_to_markers` (bool) - czy przyciąć obraz wyłącznie do wnętrza obszaru markerów.
*   Wymiary docelowe wyprostowanego obrazu (domyślnie szerokość=1200, wysokość=800).


## Interfejs wyjścia:
*   Wyprostowany obraz NumPy BGR o docelowych wymiarach (lub None jeśli nie wykryto wszystkich 4 markerów).
*   Macierz transformacji perspektywicznej (3x3 float array).

## Kryteria akceptacji:
- [ ] Skrypt poprawnie wykrywa wszystkie 4 markery o ID 10, 11, 12, 13 na zapisanym zdjęciu referencyjnym.
- [ ] Obraz wyjściowy jest prawidłowo wycięty po obrysie wyznaczonym przez markery i "wyprostowany".
- [ ] Brak zniekształceń perspektywicznych w wyjściowym obrazie (krawędzie stołu są równoległe do krawędzi obrazu).

## Test ręczny:
1.  Uruchom skrypt `test_perspective_correction.py`.
2.  Skrypt powinien wczytać plik `output/captures/test_capture_20260606_183047.png`, wykryć markery, dokonać transformacji i zapisać wyprostowany stół w folderze `output/processed/` pod nazwą `straight_table.png`.
3.  Otwórz plik i sprawdź, czy stół jest wyprostowany, a leżąca karta tarota jest widoczna bez zniekształceń perspektywicznych.

## Uwagi integracyjne:
*   Wyprostowany obraz ze stołu (top-down) będzie stanowił podstawowe wejście dla modułu detekcji kart (TV-003), co uprości algorytm wyszukiwania konturów.

---

## Wynik testu
*   **Data testu:** 2026-06-06
*   **System:** Microsoft Windows (Build 22000)
*   **Ścieżka projektu:** `E:\Antigravity\Projekty\TarotVision`

Wynik:
*   Pomyślnie wykryto 4 narożne markery ArUco (słownik `DICT_4X4_50`):
    *   ID 10 (TL): `(324, 56)`
    *   ID 11 (TR): `(1418, 66)`
    *   ID 12 (BR): `(1435, 812)`
    *   ID 13 (BL): `(327, 785)`
*   Zaimplementowano tryb przycięty (`crop_to_markers=True`), który wycina blat stołu do pliku `output/processed/table_cropped.png` o wymiarach 1200x800.
*   Zaimplementowano tryb pełny (`crop_to_markers=False`), który zachowuje 15% marginesu tła wokół markerów i zapisuje go do pliku `output/processed/table_full.png` o wymiarach 1200x800.
*   Obie wersje są poprawnie wyprostowane i wolne od zniekształceń perspektywicznych.

**Status:**
Zadanie TV-004 zaakceptowane i zakończone.


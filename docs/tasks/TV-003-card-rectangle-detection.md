# Zadanie: TV-003

## ID zadania:
TV-003

## Nazwa zadania:
Utwórz moduł wykrywania prostokątów kart

## Cel:
Napisanie algorytmu przetwarzania obrazu za pomocą OpenCV, który analizuje klatkę wideo (lub statyczny obraz), odnajduje na niej prostokątne kształty kart leżących na stole i zwraca ich współrzędne oraz rysuje ramki diagnostyczne.

## Kontekst projektu:
Główny element pierwszego etapu (MVP 1) warstwy TarotVision Core (moduł `vision`). Odpowiada za bezpośrednią lokalizację geometryczną kart na stole roboczym.

## Zakres:
1. Konwersja obrazu wejściowego do odcieni szarości.
2. Zastosowanie filtracji szumów (rozmycie Gaussa).
3. Detekcja krawędzi (Canny) lub progowanie adaptacyjne (Adaptive Thresholding) w celu wyodrębnienia kart z tła.
4. Znalezienie konturów (funkcja `cv2.findContours`).
5. Filtrowanie konturów na podstawie:
    * Liczby wierzchołków po aproksymacji (szukamy dokładnie 4 wierzchołków).
    * Powierzchni (ignorowanie zbyt małych i zbyt dużych obiektów).
    * Proporcji boków (sprawdzenie, czy obiekt ma proporcje zbliżone do karty tarota, np. 1:1.5 - 1:1.7).
6. Narysowanie zielonych ramek wokół zakwalifikowanych obiektów na kopii obrazu.
7. Zwrócenie listy współrzędnych wierzchołków wykrytych kart.

## Poza zakresem:
* Przechwytywanie obrazu z kamery (wykorzystujemy TV-001).
* Zapis wyników na dysku (wykorzystujemy TV-002).
* Rozpoznawanie konkretnych nazw kart (np. Mag, Głupiec).
* Korekcja perspektywy i prostowanie obrazu karty (zakres TV-004).

## Pliki do utworzenia lub zmiany:
* `src/tarotvision/vision/detector.py` (moduł detekcji)
* `test_card_detection.py` (skrypt testowy)

## Wymagania techniczne:
* Python 3.10+
* Algorytmy geometryczne OpenCV (`cv2.arcLength`, `cv2.approxPolyDP`, `cv2.contourArea`).

## Interfejs wejścia:
* Obraz NumPy BGR (klatka).
* Parametry progowania (opcjonalnie, np. wartości min/max dla Canny).

## Interfejs wyjścia:
* Obraz NumPy BGR z narysowanymi ramkami.
* Lista słowników opisujących wykryte karty (współrzędne 4 rogów).

## Kryteria akceptacji:
* Algorytm poprawnie wykrywa co najmniej jedną kartę tarota na jednolitym tle (np. stole lub macie).
* System nie wykrywa drobnych obiektów ani cieni jako kart.
* Wynikowa lista wierzchołków zawiera poprawne współrzędne pikseli.

## Test ręczny:
* Połóż jedną kartę tarota na stole pod kamerą AnkerWork C310.
* Uruchom skrypt `test_card_detection.py`.
* Skrypt powinien zapisać w `output/processed/` obrazek z zielonym prostokątem wokół Twojej karty.

## Uwagi integracyjne:
* Moduł pobiera wyprostowany stół z modułu perspektywy (TV-004), dzięki czemu współrzędne są rzutowane na płaską płaszczyznę 2D. Wykryte rogi kart i ich obrysy będą stanowiły podstawę dla Etapu 3 (Rozpoznawanie konkretnych kart).

---

## Wynik testu
*   **Data testu:** 2026-06-06
*   **System:** Microsoft Windows (Build 22000)
*   **Ścieżka projektu:** `E:\Antigravity\Projekty\TarotVision`

Wynik:
*   Zaimplementowano klasę `CardDetector` opartą o progowanie adaptacyjne i morfologiczne domykanie krawędzi.
*   Pomyślnie wykryto obróconą kartę tarota na wyprostowanym stole.
*   Wyliczono dokładny środek `(1069, 386)` oraz kąt obrotu `-56.82°`.
*   Zapisano obraz z zieloną ramką diagnostyczną `output/processed/table_detected.png`.
*   Wygenerowano prawidłowy plik JSON z metadanymi `output/processed/detected_cards.json`.

**Status:**
Zadanie TV-003 zaakceptowane i zakończone.


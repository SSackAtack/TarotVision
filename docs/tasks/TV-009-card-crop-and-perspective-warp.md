# Zadanie: TV-009

## ID zadania
TV-009

## Nazwa zadania
Wycinanie (crop) i prostowanie pojedynczej karty do wymiarów kanonicznych talii Gilded

## Status
Zakończone

---

## Cel
Utworzyć moduł `CardCropper`, który na podstawie wierzchołków (`corners`) przekazanych z `CardRefinery` wycina kartę ze stołu, prostuje jej perspektywę i skaluje do wymiarów kanonicznych określonych w profilu talii (np. `600x1032 px` dla Gilded).

---

## Kontekst projektu
MVP 1 wraz z obsługą geometrii wielu talii (TV-008) jest w pełni stabilne. `CardRefinery` dostarcza nam metadane wykrytej karty o spójnym aspect ratio (1.720). Moduł `CardCropper` ma pobrać te wierzchołki, uporządkować je i wykonać transformację perspektywiczną, przygotowując czysty obraz karty pod przyszły etap rozpoznawania.

---

## Zakres
1. Utworzyć moduł `src/tarotvision/vision/cropper.py` z klasą `CardCropper`.
2. Zaimplementować helper `order_points(points)` porządkujący rogi do spójnej kolejności: top-left, top-right, bottom-right, bottom-left.
3. Wykorzystać `cv2.getPerspectiveTransform` oraz `cv2.warpPerspective` do wyprostowania karty i przeskalowania jej do pionowych wymiarów kanonicznych z profilu talii (fallback na domyślne `600x1032`).
4. Zapisać cropy wynikowe do `output/processed/crops/` oraz jako `crop.png` w folderach diagnostycznych.
5. Utworzyć test diagnostyczny offline `test_card_cropper_diagnostics.py` weryfikujący poprawność działania na zapisanych próbach z sesji (`detection_001` i `detection_002`).

---

## Poza zakresem
Nie robić w tym zadaniu:
*   Rozpoznawania tożsamości kart.
*   OCR i klasyfikacji talii.
*   Rozpoznawania pozycji odwróconej.
*   Zmieniania logiki porównywania snapshotów.

---

## Kryteria akceptacji
1. `CardCropper` pomyślnie wycina i prostuje obraz karty z `detection_001` i `detection_002`.
2. Wynikowy crop dla Gilded ma wymiary dokładnie `600x1032 px`.
3. Crop nie jest pusty ani czarny.
4. Cropy są zapisywane w wyznaczonych katalogach.
5. Wszystkie testy jednostkowe, diagnostyczne i regresyjne przechodzą pomyślnie.

---

## Wynik realizacji
- **Data realizacji:** 2026-06-07
- **Moduł:** Utworzono `src/tarotvision/vision/cropper.py` z klasą `CardCropper` i stabilnym porządkowaniem wierzchołków.
- **Integracja:** Zintegrowano proces wycinania z głównym programem `test_card_detection_diff.py`.
- **Weryfikacja:** Test diagnostyczny `test_card_cropper_diagnostics.py` potwierdził wycięcie klatki z `detection_001`, `detection_002` oraz `detection_004`.
- **Rozmiary:** Cropy dla talii Gilded mają wymiary dokładnie `600x1032 px` i nie są puste (średnia jasność > 70).
- **Regresje:** Brak regresji w pozostałych testach projektu.

---

## Następny krok po TV-009
*   **TV-010 — przygotowanie rozpoznawania obrazowego karty:** Przygotowanie infrastruktury porównywania cropa ze skanami referencyjnymi w celu rozpoznania nazwy karty tarota.

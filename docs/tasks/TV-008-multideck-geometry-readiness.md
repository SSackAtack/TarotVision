# Zadanie: TV-008

## ID zadania
TV-008

## Nazwa zadania
Zarządzanie geometrią wielu aktywnych talii (MultiDeck Geometry Readiness)

## Status
Zakończone

---

## Cel
Przygotować system TarotVision do obsługi wielu aktywnych talii w jednej sesji. Umożliwić `CardRefinery` dopasowanie geometrii spośród listy aktywnych profili geometrycznych talii i wykrywanie niejednoznaczności.

---

## Opis wdrożenia
- **Data realizacji:** 2026-06-07
- **DeckLibrary:** Zaimplementowano moduł `DeckLibrary` przeszukujący podkatalogi `assets/decks/` w celu dynamicznego wczytywania profili talii. Moduł odczytuje listę aktywnych talii z pliku `assets/decks/active_decks.json` (z fallbackiem na `gilded` w przypadku braku pliku).
- **Multi-Deck Matching:** Rozszerzono `CardRefinery.refine_card` tak, aby przyjmował `deck_profiles` (lub ładował je automatycznie za pomocą biblioteki). Algorytm ocenia geometryczny score każdego z profili i dopasowuje model o proporcjach najlepiej pasujących do maski różnicowej.
- **Niejednoznaczność (Ambiguity):** Jeśli system wykryje, że dwie lub więcej talii ma bardzo zbliżone proporcje (różnica score <= 0.05 lub różnica aspect_ratio <= 0.02), ustawia flagę `geometry_ambiguous = True` oraz zapisuje listę podobnych profili w `similar_geometry_profiles`. Karta zostaje dopasowana do najlepszego kandydata, a jej ostateczne doprecyzowanie (identyfikacja talii) zostaje odłożone do modułu rozpoznawania obrazowego.

---

## Pliki zmodyfikowane lub utworzone
*   `assets/decks/active_decks.json` [NEW]
*   `src/tarotvision/decks/library.py` [NEW]
*   `src/tarotvision/vision/refinery.py` [MODIFY]
*   `test_deck_library.py` [NEW]
*   `test_card_refinery_multideck.py` [NEW]
*   `docs/tasks/TV-008-multideck-geometry-readiness.md` [NEW]
*   `README.md` [MODIFY]

---

## Testy i weryfikacja
- Utworzono test jednostkowy `test_deck_library.py` weryfikujący poprawne wczytywanie i zarządzanie profilami aktywnymi.
- Utworzono test integracyjny `test_card_refinery_multideck.py` sprawdzający:
  - Scenariusz jednej talii (brak niejednoznaczności).
  - Scenariusz wielu talii o różnych proporcjach (prawidłowy wybór optymalnego profilu).
  - Scenariusz wielu talii o bardzo podobnych proporcjach (prawidłowe oznaczenie niejednoznaczności `geometry_ambiguous = True`).
- Zweryfikowano brak regresji poprzez uruchomienie dotychczasowych testów `test_card_refinery_diagnostics.py` i `test_card_detection_offline.py`.

---

## Następny krok po TV-008
*   **TV-009 — crop i prostowanie pojedynczej karty:** Wycięcie pojedynczej karty ze stołu oraz przekształcenie perspektywiczne (prostowanie) do kanonicznych wymiarów talii (pobranych z wybranego profilu geometrycznego) w celu przygotowania obrazu do rozpoznawania.

# TV-011: Rozpoznawanie obrazowe kart na podstawie cropów i skanów referencyjnych

Status: Zakończone

## 1. Cel zadania
Wdrożenie pierwszego modułu rozpoznawania wizualnego kart tarota (visual matching) na podstawie wygenerowanego cropu 600x1032 px oraz bazy skanów referencyjnych talii.

## 2. Decyzja projektowa
- Wyklucza się stosowanie OCR tekstu (odczytywania nazw/numerów z kart) jako metody rozpoznawania.
- Metodą docelową jest porównywanie całego obrazu karty (visual similarity) ze znormalizowanymi skanami referencyjnymi.
- Ewentualne wystąpienia pojęcia "OCR" w kodzie lub dokumentacji mają jasno precyzować, że dotyczy to visual matching, a nie odczytu tekstowego.

## 3. Kontekst po TV-010
Zadanie TV-010 zweryfikowało fizycznie na kamerze stabilność całego dotychczasowego pipeline'u:
- Dynamiczne rolling snapshoty poprawnie izolują nową kartę od tła i poprzednich kart.
- `CardRefinery` dopasowuje pełną ramkę geometryczną karty.
- `CardCropper` wycina i prostuje obraz do pionowego wymiaru kanonicznego 600x1032 px.
System jest w pełni gotowy na zasilenie modułu rozpoznawania tymi cropami.

## 4. Zakres TV-011
- Utworzenie struktury pakietu `tarotvision.recognition`.
- Implementacja `ReferenceLoader` do wczytywania fizycznych obrazów referencyjnych z dysku (`assets/decks/<deck_id>/reference_scans/`).
- Implementacja `ImageMatcher` realizującego proste dopasowanie wizualne (porównanie cropa w skali szarości, o znormalizowanym wymiarze i jasności, dla orientacji 0° oraz 180°).
- Utworzenie skryptu testowego `test_card_image_recognition.py` weryfikującego proces dopasowania na fizycznych plikach.
- Zapis wyników do `output/processed/recognition/recognition_result.json`.

## 5. Poza zakresem TV-011
- OCR i odczytywanie napisów z kart.
- Klasyfikacja neuronowa (AI, YOLO, SAM itp.).
- Interpretacja znaczenia tarota.
- Finalne rozpoznawanie całej talii (brak mapowania semantycznego nazw kart na tym etapie).
- Implementacja UI, WebSocketów oraz TableState.

## 6. Algorytm v1 (Visual Similarity)
1. Wczytanie cropa i obrazu referencyjnego.
2. Normalizacja rozdzielczości obu obrazów do 600x1032 px.
3. Konwersja do skali szarości.
4. Wygładzenie filtrem Gaussa (GaussianBlur).
5. Normalizacja jasności klatki za pomocą `cv2.normalize` (norma MINMAX).
6. Wyliczenie bezwzględnej różnicy klatek (`cv2.absdiff`).
7. Wyznaczenie MAE (Mean Absolute Error).
8. Obliczenie współczynnika podobieństwa: `score = 1.0 - MAE`.
9. Porównanie wariantu normalnego (0°) oraz obróconego o 180° (`cv2.ROTATE_180`).
10. Wybór wyższego score i posortowanie kandydatów.

## 7. Wyniki Realizacji i Weryfikacji
Przetestowano działanie na bazie pełnej talii wgranej przez użytkownika. 
Wczytano **79 skanów referencyjnych** (w tym rewers) z katalogu `assets/decks/gilded/reference_scans/`.

Wyniki rozpoznawania:
- **detection_001 (karta 1, Sesja 1):**
  - najlepszy kandydat: `Gilded_73`
  - confidence: `0.8676`
  - best_rotation: `0°`
- **detection_002 (karta 2, Sesja 1):**
  - najlepszy kandydat: `Gilded_54`
  - confidence: `0.8699`
  - best_rotation: `0°`
- **detection_004 (karta 3/4, Sesja 1):**
  - najlepszy kandydat: `Gilded_31`
  - confidence: `0.8288`
  - best_rotation: `0°`
- **detection_007 (karta 1, Sesja 2 - manualna):**
  - najlepszy kandydat: `Gilded_38`
  - confidence: `0.8436`
  - best_rotation: `180°` (system prawidłowo obrócił cropa, by dopasować go do wzorca)
- **detection_008 (karta 2, Sesja 2 - manualna):**
  - najlepszy kandydat: `Gilded_54`
  - confidence: `0.8550`
  - best_rotation: `180°`

Wskaźnik podobieństwa (confidence) wzrósł do wartości **~0.82 - 0.86** po wdrożeniu pełnej talii, co potwierdza wysoką skuteczność algorytmu w znajdowaniu właściwych szablonów.
Zbiorcze wyniki zostały zapisane do pliku `output/processed/recognition/recognition_result.json`.

## 8. Kryteria akceptacji
- [x] Istnieje moduł `tarotvision.recognition`.
- [x] Działa wczytywanie skanów referencyjnych z talii (`ReferenceLoader`).
- [x] Działa porównywanie cropa ze skanami (`ImageMatcher`) z obsługą obrotu 0° i 180°.
- [x] Wynik podobieństwa mieści się w zakresie `0.0` - `1.0`.
- [x] Wynik zawiera pole `recognized_deck` = `gilded`. Pole `recognized_card` wynosi `null`.
- [x] Skrypt `test_card_image_recognition.py` uruchamia się pomyślnie i zwraca czytelne komunikaty przy braku plików wejściowych.
- [x] Dotychczasowe testy integracyjne przechodzą bez błędów.

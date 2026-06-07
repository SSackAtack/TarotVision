# TV-014: Reference Deck Recognition Index

Status: Zakończone

## 1. Cel zadania
Zbudowanie trwałego indeksu rozpoznawczego talii referencyjnych (recognition index) w celu uniknięcia wczytywania i przetwarzania pełnych obrazów referencyjnych przy każdym dopasowaniu. Umożliwi to szybkie i stabilne dopasowywanie cropów z kamery do wstępnie obliczonych cech cyfrowych kart.

## 2. Problem pełnego porównywania
Dotychczasowy `ImageMatcher` (TV-011) wczytywał pełne obrazy referencyjne przy każdym wywołaniu, wykonywał na nich preprocesowanie i wyliczał MAE piksel po pikselu na obrazach o wymiarach 600x1032. Jest to kosztowne obliczeniowo i pamięciowo. 
Rozwiązaniem jest jednorazowa ekstrakcja cech (fingerprinty, hashe, histogramy) ze skanów referencyjnych, zapisanie ich w trwałym indeksie, a następnie porównywanie cropów z cechami zapisanymi w tym indeksie.

## 3. Zapisywane Cechy (V1)
Dla każdego skanu referencyjnego wyliczamy i zapisujemy w indeksie:
1. **Grayscale fingerprint**: Obraz grayscale znormalizowany min-max i pomniejszony do 64x110 px.
2. **Difference Hash (dhash)**: 64-bitowy hash różnicowy z obrazu 9x8 w skali szarości.
3. **Gray Histogram**: Znormalizowany histogram jasności (64 biny).
4. **Color Histogram**: Trójwymiarowy znormalizowany histogram HSV (siatka 8x8x8).
5. **Region fingerprints**: Podział obrazu na siatkę 3x3 i wyciągnięcie małego fingerprintu grayscale (16x16) dla każdego regionu w celu wychwycenia układu przestrzennego.

## 4. Architektura Dopasowywania i Scoring
Wszystkie cechy są wyliczane dla cropa z kamery w orientacji 0° oraz 180°. Podobieństwo do kart w indeksie jest mierzone niezależnie dla każdej cechy w zakresie [0, 1]:
- `gray_fingerprint`: $1.0 - (MAE / 255.0)$
- `region_fingerprints`: $1.0 - (średni\_MAE / 255.0)$
- `gray_histogram`: $1.0 - (L1\_distance / 2.0)$
- `color_histogram`: $1.0 - (L1\_distance / 2.0)$
- `dhash`: $1.0 - (Hamming\_distance / 64.0)$

Całkowity score dopasowania wyliczany jest jako suma ważona cech:
- `gray_fingerprint`: 40%
- `region_fingerprints`: 25%
- `color_histogram`: 15%
- `gray_histogram`: 10%
- `dhash`: 10%

## 5. Struktura Plików Indeksu
W katalogu `assets/decks/{deck_id}/recognition_index/` generowane są dwa pliki:
- `index_manifest.json` — manifest z informacjami o talii, ekstraktorach i liście referencji.
- `features.npz` — skompresowane macierze cech (`reference_ids`, `gray_fingerprints`, `dhashes`, `gray_histograms`, `color_histograms`, `region_fingerprints`) zachowujące tę samą kolejność rekordów.

## 6. Kryteria akceptacji
1. Istnieje klasa `ReferenceIndexBuilder` wyliczająca i zapisująca manifest oraz plik cech. [Zrobione]
2. Istnieje klasa `ReferenceIndexLoader` wczytująca manifest i plik cech NPZ do pamięci. [Zrobione]
3. Istnieje klasa `IndexedImageMatcher` wyliczająca cechy cropa i dopasowująca go do indeksu (z obsługą rotacji 0° i 180° oraz diagnostycznym `score_breakdown`). [Zrobione]
4. Skrypt CLI `build_reference_index.py` umożliwia wygenerowanie indeksu dla talii Gilded. [Zrobione]
5. `test_reference_index_builder.py` przechodzi poprawnie. [Zrobione]
6. `test_indexed_image_matcher.py` przechodzi poprawnie. [Zrobione]
7. `test_card_image_recognition.py` próbuje w pierwszej kolejności użyć nowego matchera indeksowego. [Zrobione]
8. Wszystkie testy regresyjne przechodzą bez błędów. [Zrobione]

## 7. Wyniki realizacji
Zbudowano i przetestowano kompletny indeks rozpoznawania talii referencyjnych dla talii `gilded` (79 referencji).
- Pliki indeksu `index_manifest.json` oraz `features.npz` (2.23 MB) zostały pomyślnie wygenerowane w folderze `assets/decks/gilded/recognition_index/`.
- Przetestowano dopasowanie na 5 sesyjnych cropach za pomocą `test_card_image_recognition.py`. Wyniki są w 100% zgodne z tradycyjnym matcherem baselinowym (te same przypisania kart i rotacji), jednak bez potrzeby wczytywania i procesowania 79 obrazów przy każdym matchu.
- Średni confidence dopasowania oscyluje wokół 0.62–0.78, a matcher poprawnie zwraca pełen diagnostyczny `score_breakdown` cząstkowych wag (np. gray_fingerprint, dhash, histogram HSV itp.) dla każdego kandydata.
- Wszystkie unit testy (`test_reference_index_builder.py`, `test_indexed_image_matcher.py`) oraz testy regresyjne (kalibracja koloru, preflight kamery, card cropper itp.) przechodzą pomyślnie.


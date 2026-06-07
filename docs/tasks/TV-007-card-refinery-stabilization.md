# Zadanie: TV-007

## ID zadania
TV-007

## Nazwa zadania
Modelowe dopasowanie pełnej ramki karty na podstawie maski różnicowej i geometrii talii

## Status
Do wykonania w kolejnej sesji.

---

## Cel

Poprawić moduł `CardRefinery`, aby finalna ramka diagnostyczna obejmowała pełny fizyczny obrys karty, a nie tylko kontrastowy, jasny albo graficznie wyróżniający się fragment ilustracji.

Nowa decyzja architektoniczna:

```text
CardRefinery nie powinien zgadywać ramki wyłącznie z progowania obrazu karty.
CardRefinery powinien dopasowywać znany model geometryczny karty do obszaru wykrytego przez snapshot-diff.
```

W tym zadaniu używamy faktu, że znamy talię i posiadamy skany referencyjne prawdziwej talii używanej w projekcie. Na początku biblioteka będzie zawierała tylko jedną przykładową kartę talii `Gilded`. Ten jeden skan ma posłużyć do pobrania danych geometrycznych: rozmiaru obrazu, proporcji boków i kanonicznego modelu ramki.

Nie robimy jeszcze rozpoznawania nazw kart. Nazwy plików skanów mogą być losowe i nie muszą odpowiadać rzeczywistym figurom tarota.

---

## Kontekst projektu

TV-006 potwierdziło fizycznie poprawność rolling snapshot comparison:

```text
Snapshot_current - Snapshot_previous
```

Druga detekcja użyła jako referencji stołu z pierwszą zaakceptowaną kartą i poprawnie wygenerowała maskę różnicową tylko dla drugiej karty.

Problem ujawniony w teście fizycznym dotyczy kolejnego etapu:

```text
DiffDetector -> CardRefinery
```

`DiffDetector` wskazuje właściwy ROI nowej karty, ale `CardRefinery` przy drugiej karcie dopasował zieloną ramkę tylko do górnej części karty. To oznacza, że problem nie leży już w wyborze referencji snapshotów, tylko w sposobie dopasowania pełnego obrysu karty wewnątrz ROI.

Obecne podejście w `CardRefinery` bazuje głównie na progowaniu Otsu obrazu ROI. To jest ryzykowne, ponieważ karta tarota ma bogatą grafikę, różne poziomy jasności, ramki, cienie, kontrastowe elementy i możliwe odblaski. Algorytm może więc złapać część grafiki karty zamiast pełnej fizycznej ramki.

---

## Główna decyzja techniczna

TV-007 ma przejść z podejścia:

```text
ROI obrazu -> Otsu -> największy kontur -> ramka
```

na podejście:

```text
maska różnicowa + ROI + znana geometria talii -> dopasowanie modelu ramki karty
```

Czyli:

```text
obszar zmiany mówi: gdzie mniej więcej leży karta,
profil talii mówi: jaki kształt musi mieć karta,
CardRefinery dopasowuje idealny model prostokąta karty do danych z maski.
```

---

## Talia startowa

Na potrzeby testów tworzymy bibliotekę talii:

```text
assets/decks/gilded/
```

Nazwa talii:

```text
Gilded
```

Założenia:

* na początku użytkownik załaduje tylko jeden skan prawdziwej karty,
* skan znajduje się docelowo w `assets/decks/gilded/reference_scans/`,
* nazwa pliku skanu nie ma jeszcze znaczenia semantycznego,
* z pierwszego skanu należy pobrać geometrię talii:
  * szerokość obrazu w pikselach,
  * wysokość obrazu w pikselach,
  * proporcję boków,
  * kanoniczny rozmiar cropa,
  * informację, czy karta jest pionowa czy pozioma,
  * ewentualnie orientację ramki.

Nie wolno zakładać, że nazwa pliku odpowiada konkretnej karcie tarota. Rozpoznawanie nazw i mapowanie skanów na figury zostanie wykonane w przyszłości.

---

## Docelowa struktura biblioteki talii

```text
assets/
└── decks/
    ├── README.md
    └── gilded/
        ├── README.md
        ├── deck_profile.json
        └── reference_scans/
            └── .gitkeep
```

W przyszłości struktura może zostać rozbudowana do:

```text
assets/decks/gilded/
├── deck_profile.json
├── reference_scans/
│   ├── random_name_001.png
│   ├── random_name_002.png
│   └── ...
├── normalized/
└── metadata/
```

Na etapie TV-007 potrzebna jest tylko geometria, nie semantyka kart.

---

## DeckProfile / CardGeometryModel

W TV-007 należy wprowadzić pojęcie profilu talii lub modelu geometrii karty.

Minimalny profil talii powinien zawierać:

```json
{
  "deck_id": "gilded",
  "deck_name": "Gilded",
  "geometry_source": "single_reference_scan",
  "reference_scan_dir": "assets/decks/gilded/reference_scans",
  "card_width_px": null,
  "card_height_px": null,
  "aspect_ratio_height_to_width": null,
  "canonical_width_px": null,
  "canonical_height_px": null,
  "notes": "Card names are not trusted at this stage. First scan is used only for geometry."
}
```

Po dodaniu pierwszego skanu agent powinien być w stanie automatycznie albo półautomatycznie uzupełnić wartości geometryczne.

Na tym etapie wystarczy geometria obrazu całej zeskanowanej karty. Nie trzeba jeszcze wycinać wewnętrznej ilustracji, wykrywać nazw, numerów ani znaczeń.

---

## Proponowana architektura rozwiązania

### 1. Deck profile loader

Dodać prosty mechanizm wczytywania profilu talii, np.:

```text
src/tarotvision/decks/profile.py
```

Przykładowa odpowiedzialność:

* wczytuje `assets/decks/gilded/deck_profile.json`,
* sprawdza, czy profil zawiera proporcję karty,
* jeśli profil nie jest uzupełniony, potrafi odczytać pierwszy obraz z `reference_scans/` i policzyć geometrię,
* zwraca model geometrii dla `CardRefinery`.

Minimalny interfejs:

```python
profile = DeckProfile.load("assets/decks/gilded/deck_profile.json")
aspect_ratio = profile.aspect_ratio_height_to_width
```

Dopuszczalne jest wykonanie tego prostszą funkcją, jeśli agent uzna, że pełna klasa jest jeszcze za wcześnie. Ważne, żeby logika nie była wpisana na sztywno do `CardRefinery`.

### 2. CardRefinery V2

Zaktualizować:

```text
src/tarotvision/vision/refinery.py
```

Tak, aby `CardRefinery` potrafił korzystać z:

* `roi_rect` z `DiffDetector`,
* `diff_mask`,
* `deck_profile` albo przynajmniej `aspect_ratio_height_to_width`.

Preferowany nowy interfejs, z zachowaniem kompatybilności:

```python
def refine_card(self, image, roi_rect, diff_mask=None, deck_profile=None):
    ...
```

Stare wywołania bez `diff_mask` i `deck_profile` powinny nadal działać przez fallback.

### 3. Mask-based model fitting

Podstawowa technika dla TV-007:

```text
diff_mask
↓
lokalne ROI z marginesem
↓
czyszczenie morfologiczne
↓
connected components / contours
↓
minAreaRect
↓
korekta aspect ratio według DeckProfile
↓
score dopasowania modelowej ramki do maski
↓
pełna ramka karty
```

Narzędzia OpenCV:

```text
cv2.findContours
cv2.connectedComponentsWithStats
cv2.morphologyEx
cv2.dilate
cv2.minAreaRect
cv2.boxPoints
```

### 4. Aspect ratio constraint

Najważniejsza poprawka:

```text
finalna ramka musi mieć proporcję zgodną z talią Gilded.
```

Jeśli skan referencyjny ma np.:

```text
width = 700 px
height = 1200 px
aspect_ratio_height_to_width = 1.714
```

wtedy dopasowana ramka z kamery nie powinna mieć losowych proporcji typu 1.1, 2.4 albo obejmować tylko górnego fragmentu karty.

Model dopasowania powinien:

* przyjąć środek i kąt z maski / `roi_rect`,
* dopasować szerokość i wysokość zgodnie z proporcją talii,
* dobrać skalę tak, aby ramka najlepiej pokrywała maskę różnicową,
* preferować pełny obrys karty zamiast fragmentów grafiki.

### 5. Scoring dopasowania

Wynik powinien być wybierany nie przez największy kontur z Otsu, ale przez najlepsze dopasowanie modelu.

Przykładowe kryteria:

* ile pikseli maski leży wewnątrz modelowej ramki,
* ile modelowej ramki jest puste,
* czy proporcja zgadza się z talią,
* czy ramka mieści się w granicach stołu,
* czy rozmiar jest zbliżony do spodziewanego ROI,
* czy ramka nie obejmuje tylko małego fragmentu karty.

Opcjonalne pola wyniku:

```json
{
  "frame_source": "diff_mask_deck_model_fit",
  "frame_confidence": 0.87,
  "aspect_ratio_expected": 1.714,
  "aspect_ratio_detected": 1.70
}
```

Nie muszą być wymagane przez istniejące moduły, ale są bardzo przydatne diagnostycznie.

---

## Fallback

Stare progowanie Otsu może zostać jako fallback:

```text
1. Najpierw próbuj dopasowania z maski różnicowej i geometrii talii.
2. Jeżeli brak maski albo dopasowanie jest słabe, użyj starego Otsu.
3. Jeżeli Otsu zwraca ramkę niezgodną z proporcją talii, odrzuć albo oznacz wynik jako niskiej jakości.
```

Otsu nie powinno być główną metodą, bo karta nie jest jednolitym obiektem. Jest obiektem graficznym.

---

## Zakres TV-007

1. Przygotować strukturę biblioteki talii `assets/decks/gilded/`.
2. Przygotować `deck_profile.json` dla talii `Gilded`.
3. Dodać miejsce na pierwszy skan referencyjny w `assets/decks/gilded/reference_scans/`.
4. Dodać mechanizm wczytania profilu talii albo przynajmniej helper do pobrania proporcji karty z profilu/skanu.
5. Zmodyfikować `CardRefinery`, aby używał `diff_mask` i geometrii talii do modelowego dopasowania pełnej ramki.
6. Zachować kompatybilność dotychczasowego interfejsu wyjściowego:
   * `center`,
   * `size`,
   * `angle`,
   * `corners`.
7. Dodać lub zaktualizować test offline oparty na rekordach diagnostycznych `detection_001` i `detection_002`.
8. Zweryfikować, że ramka dla `detection_002` obejmuje pełną drugą kartę, a nie tylko jej górny fragment.

---

## Poza zakresem

Nie robić w tym zadaniu:

* rozpoznawania nazw kart,
* mapowania plików skanów na konkretne figury tarota,
* OCR,
* klasyfikacji kart,
* rozpoznawania pozycji odwróconej,
* overlay HTML,
* WebSocket,
* WebRTC,
* portalu,
* finalnego `TableState`,
* treningu modelu AI,
* YOLO / ONNX / SAM,
* automatycznej interpretacji tarota.

---

## Pliki do utworzenia lub zmiany

### Dokumentacja i assets

* `assets/decks/README.md`
* `assets/decks/gilded/README.md`
* `assets/decks/gilded/deck_profile.json`
* `assets/decks/gilded/reference_scans/.gitkeep`

### Kod

* `src/tarotvision/vision/refinery.py`
* opcjonalnie: `src/tarotvision/decks/profile.py`
* test offline dla rafinacji, np. `test_card_refinery_diagnostics.py`

### Dokumentacja zadania

* `docs/tasks/TV-007-card-refinery-stabilization.md`

---

## Wymagania techniczne

* Zachować modularność: `CardRefinery` nie powinien obsługiwać kamery, snapshotów ani zapisu sesji.
* Nie zmieniać semantyki `Snapshot_previous` z TV-006.
* Nie rozszerzać `DiffDetector`, jeśli problem da się rozwiązać w `CardRefinery`.
* Preferować `diff_mask` i geometrię talii zamiast ponownego pełnego progowania grafiki karty.
* Nie zakładać, że nazwa pliku skanu jest nazwą karty.
* Nie robić rozpoznawania obrazowego konkretnej karty w TV-007.
* W razie braku profilu lub skanu referencyjnego system powinien użyć fallbacku na dotychczasowe zachowanie albo zwrócić czytelny komunikat diagnostyczny.

---

## Interfejs wejścia

Minimalne dane wejściowe dla nowego `CardRefinery`:

* wyprostowany obraz stołu BGR,
* `roi_rect` z `DiffDetector`,
* `diff_mask` z `DiffDetector`,
* profil talii albo aspect ratio talii.

Preferowany interfejs:

```python
card_data = refinery.refine_card(
    image=warped,
    roi_rect=roi_rect,
    diff_mask=debug_mask,
    deck_profile=deck_profile,
)
```

---

## Interfejs wyjścia

Minimalny wymagany słownik:

```json
{
  "center": [x, y],
  "size": [width, height],
  "angle": -4.5,
  "corners": [
    [x1, y1],
    [x2, y2],
    [x3, y3],
    [x4, y4]
  ]
}
```

Dopuszczalne i rekomendowane pola dodatkowe:

```json
{
  "frame_source": "diff_mask_deck_model_fit",
  "frame_confidence": 0.87,
  "aspect_ratio_expected": 1.714,
  "aspect_ratio_detected": 1.70
}
```

Pola dodatkowe nie powinny łamać dotychczasowych testów.

---

## Kryteria akceptacji

1. Istnieje struktura biblioteki talii `assets/decks/gilded/`.
2. Istnieje `deck_profile.json` dla talii `Gilded`.
3. W repo istnieje miejsce na pierwszy skan referencyjny:

```text
assets/decks/gilded/reference_scans/
```

4. `CardRefinery` potrafi użyć `diff_mask` i proporcji talii do dopasowania pełnej ramki.
5. `detection_002` zwraca ramkę obejmującą pełną drugą kartę.
6. Ramka nie ogranicza się do górnej części grafiki karty.
7. `detection_001` nadal działa poprawnie.
8. Rolling snapshot comparison z TV-006 pozostaje bez zmian.
9. Istniejące testy offline nadal przechodzą.
10. Nowy test rafinacji przechodzi na rekordach diagnostycznych albo na przygotowanych próbkach.

---

## Test ręczny

1. Umieścić jeden skan referencyjny prawdziwej karty talii `Gilded` w:

```text
assets/decks/gilded/reference_scans/
```

Nazwa pliku może być losowa, np.:

```text
scan_001.png
```

2. Uruchomić test/procedurę generowania lub weryfikacji profilu talii.
3. Uruchomić:

```powershell
python test_card_detection_diff.py
```

4. Zatwierdzić pusty stół jako `Snapshot_0`.
5. Położyć pierwszą kartę i zabrać rękę.
6. Położyć drugą kartę i zabrać rękę.
7. Sprawdzić:

```text
output/sessions/current/detections/detection_002/result.png
output/sessions/current/detections/detection_002/metadata.json
```

Oczekiwane:

* zielona ramka obejmuje pełną drugą kartę,
* JSON ma środek i rozmiar odpowiadające pełnej karcie,
* `frame_source` wskazuje użycie maski/modelu talii albo analogiczną informację diagnostyczną,
* proporcja ramki odpowiada profilowi talii `Gilded`.

---

## Uwaga integracyjna

TV-007 jest kontynuacją TV-006. TV-006 potwierdziło poprawny wybór referencji porównawczej. TV-007 nie powinno zmieniać mechaniki snapshotów.

Najważniejsza zmiana polega na tym, że `CardRefinery` ma dopasowywać znany fizyczny model karty do wykrytego obszaru zmiany, zamiast ponownie zgadywać obrys karty wyłącznie na podstawie progowania grafiki.

---

## Następny krok po TV-007

Po ustabilizowaniu pełnej ramki karty można przejść do:

```text
TV-008 — crop i prostowanie pojedynczej karty do kanonicznego rozmiaru talii
TV-009 — rozpoznawanie konkretnej karty na podstawie cropa i skanów referencyjnych
```

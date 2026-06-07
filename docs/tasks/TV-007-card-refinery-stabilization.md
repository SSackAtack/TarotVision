# Zadanie: TV-007

## ID zadania
TV-007

## Nazwa zadania
Stabilizacja pełnego dopasowania ramki karty w CardRefinery

## Status
Do wykonania w kolejnej sesji.

## Cel
Poprawić moduł `CardRefinery`, aby finalna ramka diagnostyczna obejmowała pełny fizyczny obrys karty wykrytej przez `DiffDetector`, a nie tylko kontrastowy lub jasny fragment grafiki wewnątrz karty.

## Kontekst projektu
TV-006 potwierdziło fizycznie, że rolling snapshot comparison działa poprawnie:

```text
Snapshot_current - Snapshot_previous
```

Druga detekcja użyła jako referencji stołu z pierwszą zaakceptowaną kartą i poprawnie wygenerowała maskę różnicową tylko dla drugiej karty.

Problem ujawniony w teście fizycznym dotyczy kolejnego etapu:

```text
DiffDetector -> CardRefinery
```

`DiffDetector` wskazuje właściwy ROI nowej karty, ale `CardRefinery` przy drugiej karcie dopasował zieloną ramkę tylko do górnej części karty.

## Zakres
1. Przeanalizować rekordy diagnostyczne z:
   * `output/sessions/current/detections/detection_001/`
   * `output/sessions/current/detections/detection_002/`
2. Zidentyfikować, dlaczego obecne progowanie Otsu w `CardRefinery` łapie tylko część karty.
3. Zmodyfikować `src/tarotvision/vision/refinery.py` tak, aby w pierwszej kolejności wykorzystywał stabilny obszar ROI/maski różnicowej do dopasowania pełnego obrysu karty.
4. Zachować interfejs wyjściowy `CardRefinery.refine_card()`:
   * `center`
   * `size`
   * `angle`
   * `corners`
5. Dodać lub zaktualizować test offline oparty na zapisanych rekordach diagnostycznych.
6. Zweryfikować, że ramka dla drugiej karty obejmuje pełną kartę, nie tylko jej górną ilustrację.

## Poza zakresem
Nie robić w tym zadaniu:

* rozpoznawania nazw kart,
* OCR,
* klasyfikacji talii,
* overlay HTML,
* WebSocket,
* WebRTC,
* portalu,
* finalnego modelu `TableState`,
* rozpoznawania pozycji odwróconej,
* automatycznej interpretacji tarota.

## Pliki do utworzenia lub zmiany
* `src/tarotvision/vision/refinery.py`
* test offline dla rafinacji, np. `test_card_refinery_diagnostics.py`
* opcjonalnie dokumentacja zadania po zakończeniu

## Wymagania techniczne
* Zachować modularność: `CardRefinery` nie powinien obsługiwać kamery, snapshotów ani zapisu sesji.
* Nie rozszerzać `DiffDetector`, jeśli problem da się rozwiązać w rafinacji.
* Preferować dane już dostępne z `roi_rect` i maski różnicowej zamiast ponownego pełnego progowania grafiki karty.
* Jeśli potrzebna będzie zmiana interfejsu, zrobić ją minimalnie i jawnie uzasadnić.

## Interfejs wejścia
* Wyprostowany obraz stołu BGR.
* ROI karty z `DiffDetector`, obecnie `minAreaRect`.
* Opcjonalnie maska różnicowa, jeżeli okaże się potrzebna do stabilnego dopasowania pełnego obrysu.

## Interfejs wyjścia
Słownik:

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

## Kryteria akceptacji
1. Test offline potwierdza, że `detection_002` zwraca ramkę obejmującą pełną drugą kartę.
2. Ramka nie ogranicza się do górnej części grafiki karty.
3. `detection_001` nadal działa poprawnie.
4. Rolling snapshot comparison z TV-006 pozostaje bez zmian.
5. Istniejące testy offline nadal przechodzą.

## Test ręczny
1. Uruchomić:

```powershell
python test_card_detection_diff.py
```

2. Zatwierdzić pusty stół jako `Snapshot_0`.
3. Położyć pierwszą kartę i zabrać rękę.
4. Położyć drugą kartę i zabrać rękę.
5. Sprawdzić:
   * `output/sessions/current/detections/detection_002/result.png`
   * `output/sessions/current/detections/detection_002/metadata.json`

Oczekiwane:
* zielona ramka obejmuje pełną drugą kartę,
* JSON ma środek i rozmiar odpowiadające pełnej karcie.

## Uwagi integracyjne
To zadanie jest kontynuacją TV-006. TV-006 potwierdziło poprawny wybór referencji porównawczej. TV-007 nie powinno zmieniać semantyki `Snapshot_previous`; powinno naprawić wyłącznie finalne dopasowanie geometrii karty w ROI.

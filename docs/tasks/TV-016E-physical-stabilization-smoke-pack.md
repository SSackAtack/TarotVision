# TV-016E-physical-stabilization-smoke-pack — Physical Stabilization Smoke Pack Runbook

> [!NOTE]
> Ten dokument stanowi oficjalny scenariusz testów dymnych (Smoke Pack Runbook) mający na celu zweryfikowanie poprawności działania całego, fizycznie zintegrowanego pipeline'u TarotVision po wdrożeniu zadań TV-016A, TV-016B, TV-016C oraz TV-016D.

---

## 1. Cel testu
Sprawdzenie w warunkach fizycznych (z użyciem rzeczywistej kamery oraz fizycznych kart), czy pipeline poprawnie obsługuje:
- Dodanie pierwszej karty na stół.
- Dodanie drugiej karty na stół.
- Dodanie trzeciej karty na stół.
- Zabranie jednej z aktywnych kart ze stołu.
- Ignorowanie zakłóceń takich jak przejściowy ruch ręki lub rzucany cień (brak fałszywego usuwania/dodawania).
- Zapis poprawnego i aktualnego pliku `table_state.json`.
- Zapis metryk różnicowych `diff_debug` w pliku `metadata.json`.
- Wyznaczanie poprawnej i precyzyjnej decyzji rozpoznawania (`recognition_decision`).

---

## 2. Przygotowanie stanowiska
Przed rozpoczęciem testu należy przygotować następujący sprzęt i środowisko:
- **Laptop:** HP EliteBook.
- **Kamera:** AnkerWork C310, stabilnie zamocowana nad stołem pod kątem 90 stopni (widok z góry).
- **Mata / Stół:** Mata testowa oznaczona 4 markerami ArUco w narożnikach.
- **Oświetlenie:** Stałe i równomierne, bez głębokich cieni oraz silnych odblasków na powierzchni kart/maty.
- **Talia testowa:** Talia *Gilded Tarot* jako podstawowa fizyczna talia testowa.
- **Stan początkowy:** Czysty, pusty stół (widoczna wyłącznie pusta mata z markerami).

---

## 3. Komendy startowe
Do uruchomienia testowanego pipeline'u służy skrypt detekcji różnicowej:
```powershell
python test_card_detection_diff.py
```

---

## 4. Scenariusz testowy

| Krok | Akcja Operatora | Oczekiwanie (Obraz / Logi) | Stan TableState | Stan metadata.json |
| :--- | :--- | :--- | :--- | :--- |
| **Krok 1 — Uruchomienie programu** | Wpisanie i zatwierdzenie komendy startowej w terminalu. | Okno podglądu wideo startuje. Widoczny raport Camera Preflight. Wykrycie 4 markerów ArUco. | Stan załadowany z pliku lub pusta, nowa instancja. | Brak nowych wpisów przed wykonaniem próby. |
| **Krok 2 — Zatwierdzenie Snapshot_0** | Upewnienie się, że stół jest pusty, i wciśnięcie **SPACJI** w oknie wideo. | Zapisano Snapshot_0 oraz Snapshot_previous. W logach komunikat o pomyślnym zapisie. | Inicjalizacja pustego stanu stołu (cards: `[]`, history: `[]`). | Brak, Snapshot_0 nie generuje wpisu w detections. |
| **Krok 3 — Dodanie karty 1** | Położenie pierwszej karty na matę i zabranie ręki. | Wykrycie stabilizacji. Zielona ramka wokół karty 1. Log: `[Matcher] Rozpoznano kartę: [Nazwa] (Gilded_XX)`. | Dodanie karty 1 (`card_001`). Event `card_added` w historii. | Utworzenie `detection_001/metadata.json` z sekcją `diff_debug` i `cards`. Status: `accepted`. |
| **Krok 4 — Dodanie karty 2** | Położenie drugiej karty w innym wolnym miejscu na macie i zabranie ręki. | Wykrycie stabilizacji. Zielona ramka wokół karty 2. Log: `[Matcher] Rozpoznano kartę: [Nazwa]`. | Dodanie karty 2 (`card_002`). Drugi event `card_added` w historii. | Utworzenie `detection_002/metadata.json` z sekcją `diff_debug`. Status: `accepted`. |
| **Krok 5 — Dodanie karty 3** | Położenie trzeciej karty i zabranie ręki. | Wykrycie stabilizacji. Zielona ramka wokół karty 3. Log: `[Matcher] Rozpoznano kartę`. | Dodanie karty 3 (`card_003`). Trzeci event `card_added` w historii. | Utworzenie `detection_003/metadata.json` z sekcją `diff_debug`. Status: `accepted`. |
| **Krok 6 — Zabranie karty 2** | Fizyczne zabranie karty 2 z maty i wycofanie ręki. | Wykrycie stabilizacji. Czerwona ramka i X na pozycji karty 2. Log: `[Removal] Wykryto usunięcie aktywnej karty: card_002`. | Karta `card_002` zmienia status na `"removed"`. Dodanie eventu `card_removed` w historii. Karta fizycznie zostaje na liście `cards`. | Utworzenie `detection_004/metadata.json` z sekcją `removal` i `diff_debug`. Status: `card_removed`. |
| **Krok 7 — Ruch ręką nad kartami** | Przesunięcie otwartej dłoni nad ułożonymi kartami (zasłonięcie i odsłonięcie) bez zabierania kart. | Wykrycie ruchu i ponownej stabilizacji. Logi powinny zignorować tę zmianę lub pokazać brak trwałej zmiany ROI. | Stan pozostaje bez zmian (cards: 3, aktywnych: 2). | Rejestracja próby ze statusem `no_roi` lub `refinery_failed` zawierającej dane `diff_debug`. |
| **Krok 8 — Zakończenie programu** | Wciśnięcie klawisza **ESC** w oknie podglądu wideo. | Zakończenie działania skryptu, zamknięcie okna wideo. | Stan zapisany ostatecznie w `table_state.json`. | Wszystkie katalogi diagnostyczne kompletne. |
| **Krok 9 — Kontrola plików** | Sprawdzenie zawartości folderów wyjściowych. | Pliki `table_state.json` oraz foldery `detection_*` istnieją na dysku. | Zgodność stanu pliku JSON z oczekiwanym rezultatem. | Sprawdzenie czy metadane w detections posiadają sekcje `diff_debug` i `removal`. |

---

## 5. Oczekiwany wynik TableState
W pliku `output/sessions/current/table_state.json` powinny znajdować się następujące informacje:
- Wszystkie dodane karty fizyczne widnieją w tablicy `cards` (łączna długość tablicy = 3).
- Karta, która została zabrana ze stołu, posiada następujące wartości:
  - `status`: `"removed"`
  - `removed_at`: niepusty ciąg znaków czasu UTC.
  - `removal_detection_id`: identyfikator detekcji (np. `"detection_004"`).
  - `removal_confidence`: wartość pewności usunięcia (liczba zmiennoprzecinkowa).
- Pozostałe dwie aktywne karty mają status `"recognized"` (lub `"ambiguous"` / `"unrecognized"` w zależności od rezultatu rozpoznania).
- Historia (`history`) zawiera chronologiczne eventy:
  - Trzy eventy typu `"card_added"`.
  - Jeden event typu `"card_removed"` wskazujący na usuniętą instancję karty.
- Współrzędne `center_norm` oraz `bbox_norm` są obliczone poprawnie i precyzyjnie (wartości nie opierają się na sztywnym fallbacku `1920x1080`, lecz są wyliczone na bazie rzeczywistych wymiarów `set_table_size`).

---

## 6. Oczekiwany wynik metadata.json
W podkatalogach diagnostycznych (np. `output/sessions/current/detections/detection_*/metadata.json`):

- **W sekcji `diff_debug` dla każdej próby:**
  - `diff_threshold`: próg detekcji różnicowej (int).
  - `min_area`, `max_area`: ograniczenia pól powierzchni (float).
  - `contours_count`: liczba znalezionych konturów (int).
  - `accepted`: flaga logiczna określająca sukces detekcji (bool).
  - `accepted_area`: pole powierzchni zaakceptowanego konturu (float lub null).
  - `accepted_rect`: słownik z kluczami `center`, `size` i `angle` (lub null).
  - `accepted_bbox`: prostokąt `[x, y, w, h]` (lub null).
  - `rejected_contours`: lista odrzuconych konturów z polami `area` i `reason` (np. `"area_below_min"`, `"area_above_max"`, `"valid_but_not_largest"`).

- **W sekcji rozpoznawania (`recognition_decision`):**
  - `recognition_decision`: status decyzji (`"recognized"`, `"ambiguous"` lub `"unrecognized"`).
  - `top1_score`, `top2_score`: wyniki dopasowania dla pierwszego i drugiego kandydata (float).
  - `score_margin`: różnica między dwoma najlepszymi kandydatami (float).

- **W sekcji usunięcia (`removal` - tylko dla usuniętej karty):**
  - `overlap_ratio`: współczynnik pokrycia ROI zmiany z bboxem karty (float).
  - `previous_vs_background`: różnica poprzedniego stanu względem tła referencyjnego (float).
  - `current_vs_background`: różnica aktualnego stanu względem tła referencyjnego (float).
  - `restoration_delta`: spadek różnicy tła po zabraniu karty (float).
  - `removal_confidence`: wyliczona pewność usunięcia (float).

---

## 7. Kryteria PASS
Test kończy się wynikiem **PASS** w przypadku spełnienia wszystkich poniższych warunków:
1. Skrypt uruchamia się stabilnie, raportuje stan preflightu kamery i reaguje na SPACJĘ.
2. `Snapshot_0` zostaje poprawnie zapisany w katalogu sesji.
3. Położenie kart tworzy nowe obiekty kart w `TableState` z poprawnym eventem `card_added`.
4. Usunięcie karty zmienia status wybranej karty na `"removed"`, wypełnia metadane usunięcia i dodaje event `card_removed` do historii.
5. Usunięta karta **nie** znika fizycznie z listy `cards` w `TableState`.
6. Przejściowy ruch ręki lub rzucony cień **nie** wywołują fałszywego statusu `"removed"` (decyzja detektora usunięcia brzmi `"not_removed"`).
7. Zapisywane pliki `metadata.json` zawierają kompletny słownik `diff_debug` w poprawnym formacie.
8. Decyzja rozpoznawania i metryki `top1_score`, `top2_score`, `score_margin` są poprawnie rejestrowane.
9. `Snapshot_previous` ulega aktualizacji dopiero po udanym i bezbłędnym zapisaniu nowej karty w `TableState`.

---

## 8. Kryteria FAIL / Blocker
Test kończy się wynikiem **FAIL (Blocker)**, jeśli wystąpi chociaż jedno z poniższych zdarzeń:
1. Program nie jest w stanie uruchomić kamery lub zawiesza się podczas startu.
2. Zapis `Snapshot_0` kończy się błędem zapisu lub nie jest tworzony na dysku.
3. Karta położona na stół nie generuje wpisu w `TableState` mimo stabilnego zatrzymania ruchu.
4. Zabranie karty jest wykrywane jako dodanie nowej karty (brak poprawnej detekcji usunięcia).
5. Karta po usunięciu zostaje fizycznie usunięta (wykasowana) z listy `cards`.
6. Ruch ręką nad stołem powoduje fałszywe oznaczenie karty jako `"removed"`.
7. W plikach `metadata.json` brakuje słownika `diff_debug` lub nie jest on serializowalny do formatu JSON.
8. W wynikach rozpoznawania brakuje pól `recognition_decision` lub `score_margin`.
9. Współrzędne `center_norm` i `bbox_norm` są niepoprawne lub wyliczone z fałszywym rozmiarem `1920x1080`.
10. `Snapshot_previous` zostaje zaktualizowany (nadpisany) mimo błędu podczas fazy cropowania, rozpoznawania lub zapisu stanu stołu.

---

## 9. Sekcja do ręcznego raportu

## Wynik testu fizycznego

Data:
Operator:
Sprzęt:
Kamera:
Talia:
Oświetlenie:

Wynik:
PASS / FAIL

Scenariusz dodawania kart:
...

Scenariusz usunięcia karty:
...

Scenariusz ruchu ręką bez usunięcia:
...

Problemy:
...

Linki / ścieżki do diagnostyki:
...

Decyzja:
- przechodzimy do TV-017
- albo tworzymy blocker task

# TV-018: Program poprawy skuteczności rozpoznawania kart (Recognition Accuracy Program)

Status: Plan gotowy do realizacji
Data utworzenia planu: 2026-06-11
Autor: analiza techniczna agenta AI (Claude) na bazie pełnego przeglądu kodu modułów `recognition/`, `vision/`, `storage/` oraz narzędzi TV-016E.

**Prerequisite (twardy):** zmergowany do `master` kod TV-016E — narzędzia benchmarku i wizarda kalibracji (PR #8, gałąź `task/TV-016E-calibration-benchmark-tools`: `tools/benchmark_indexed_recognition.py`, `tools/physical_recognition_calibration_wizard.py`, `tools/generate_calibration_target_a4.py` + testy). Bez tych narzędzi protokół benchmarku z sekcji 3.1 jest niewykonalny — nie rozpoczynaj żadnego zadania TV-018 przed ich merge'em.

---

## 0. Jak korzystać z tego dokumentu (instrukcja dla agenta wykonującego)

1. Przeczytaj najpierw `AGENTS.md` oraz `docs/03_metoda_pracy_i_architektura_modularna.md` — obowiązują wszystkie zasady projektu (modularność, zakaz rozszerzania zakresu, format raportu końcowego).
2. Ten dokument zawiera **7 niezależnych zadań** (TV-018A … TV-018G). Realizuj **wyłącznie jedno zadanie naraz**, w kolejności z sekcji 2, na osobnej gałęzi `task/TV-018X-krotka-nazwa`.
3. Każde zadanie ma pełny szablon (Cel, Zakres, Poza zakresem, Pliki, Kryteria akceptacji, Test ręczny, Uwagi integracyjne). Sekcje 1–4 i Załącznik A to wspólny kontekst — przeczytaj je w całości przed rozpoczęciem któregokolwiek zadania.
4. Numery linii podane w tym dokumencie odpowiadają stanowi kodu z 2026-06-11 (master + zmergowany kod TV-016E z PR #8). Jeśli kod się przesunął, kieruj się nazwami klas/funkcji — są podane zawsze.
5. Wymaganie nadrzędne: **żadna zmiana w torze rozpoznawania nie może zostać zmergowana bez porównania benchmarku przed/po** (protokół w sekcji 3.1).

---

## 1. Diagnoza — dlaczego ten program istnieje

Obecny tor rozpoznawania (stan po TV-016E):

```
Kamera 1920×1080 (preflight + lock, TV-012, config/camera_settings.json)
  → ArUco DICT_4X4_50 (ID 10,11,12,13) → warp stołu 1200×800   [vision/perspective.py]
  → rolling snapshot diff → ROI (minAreaRect)                   [vision/diff.py]
  → CardRefinery: dopasowanie proporcji talii / fallback Otsu   [vision/refinery.py]
  → CardCropper: warp 4 narożników → crop 600×1032              [vision/cropper.py]
  → [opcjonalnie] korekcja barw LAB mean/std (TV-013)           [recognition/session_color_calibration.py]
  → IndexedImageMatcher: 5 cech ważonych, rotacje 0°/180°       [recognition/indexed_matcher.py]
  → bramka decyzyjna: score ≥ 0.82 i margines ≥ 0.04            [recognition/decision.py]
```

Zidentyfikowane problemy (w kolejności wpływu na skuteczność):

| # | Problem | Gdzie | Naprawia |
|---|---------|-------|----------|
| P1 | **Domain gap**: indeks budowany ze skanów, dopasowywane cropy z kamery (inna ostrość, oświetlenie, odblaski, interpolacja) | `recognition/index_builder.py` + `assets/decks/gilded/reference_scans/` | TV-018D |
| P2 | **Karta pozioma jest nierozpoznawalna**: `CardCropper.order_points` zawsze mapuje narożniki na pion 600×1032; pozioma karta zostaje obrócona o 90° **i anizotropowo rozciągnięta**. Test rotacji 0°/180° tego nie naprawia. W rozkładach tarota karta pozioma to standard (karta krzyżująca w Krzyżu Celtyckim). | `vision/cropper.py` (`crop_card`, `order_points`) | TV-018B |
| P3 | **Podwójne przepróbkowanie**: 1920×1080 → warp stołu 1200×800 → upscale do 600×1032. Karta na warpie stołu ma realnie ~150–250 px szerokości; crop 600×1032 to interpolacja, nie detal. Macierz homografii stołu jest już zwracana przez `get_warped_table` — wystarczy ją wykorzystać. | `vision/perspective.py`, `vision/cropper.py`, `test_card_detection_diff.py` | TV-018C |
| P4 | **Globalna normalizacja min-max wrażliwa na odblaski**: jeden prześwietlony piksel (≈255) kotwiczy maksimum i spłaszcza kontrast całej karty; karty są laminowane, a talia Gilded ma złocenia. | `recognition/index_builder.py` (`extract_features`), `recognition/image_matcher.py` (`_preprocess`) | TV-018E |
| P5 | **Brak weryfikacji geometrycznej**: wszystkie cechy są globalnie-statystyczne; ściśnięta skala score (poprawne ~0.86–0.87, próg 0.82, margines 0.04). Karty blotkowe (5 vs 6 tego samego koloru) różnią się jednym symbolem — globalny MAE ich prawie nie rozróżnia. | `recognition/indexed_matcher.py` | TV-018F |
| P6 | **Benchmark nie mierzy false-accept** (decyzja „recognized" przy błędnym top1) — najgroźniejszego błędu dla sesji na żywo. Brak raportu mylonych par i sweepa progów. | `tools/benchmark_indexed_recognition.py` | TV-018A |
| P7 | **Wagi i progi ustawione ręcznie**, rozproszone w kodzie (wagi w `indexed_matcher.py`, progi jako defaulty w `decision.py`) — wbrew zasadzie centralnej konfiguracji z `docs/03` (sekcja 6, pkt 4–5). | `recognition/indexed_matcher.py`, `recognition/decision.py` | TV-018G |

Świadomie odłożone: klasyfikacja neuronowa / embeddingi CNN — patrz sekcja 12.

---

## 2. Kolejność zadań i zależności

Kolejność jest **obowiązkowa** — wynika z zależności technicznych:

```
TV-018A (benchmark+)  ──→  baseline pomiarowy dla wszystkiego poniżej
TV-018B (orientacja croppera)  ──→  poprawna geometria cropów
TV-018C (crop natywny)         ──→  finalna jakość cropów
TV-018D (indeks kamerowy)      ──→  wymaga B i C (referencje mają przejść przez FINALNY tor cropowania)
TV-018E (preprocessing v2)     ──→  wymaga D (przebudowa indeksu z surowych cropów kamerowych)
TV-018F (weryfikacja ORB)      ──→  zalecane po D (deskryptory liczone z referencji kamerowych)
TV-018G (config + strojenie)   ──→  ostatnie (stroi parametry całości na danych z benchmarku)
```

Uzasadnienie kolejności D po B i C: enrollment talii (fizyczne przechwycenie 79 kart) to ~30–60 min pracy operatora. Musi się odbyć na **ostatecznym** torze geometrycznym (poprawiona orientacja + crop natywny), inaczej trzeba będzie go powtarzać.

Uzasadnienie „surowych cropów" w D: zadanie D zapisuje na dysk **surowe obrazy PNG** (bez preprocessingu cech). Dzięki temu zmiana preprocessingu w E wymaga tylko przebudowy indeksu (sekundy), a nie ponownego przechwytywania talii.

---

## 3. Zasady wspólne dla wszystkich zadań

### 3.1. Protokół benchmarku przed/po (obowiązkowy dla TV-018B, C, D, E, F, G)

1. Przed zmianą: uruchom benchmark na aktualnym zbiorze przypadków i zapisz raport jako `output/calibration_runs/<data>_baseline/indexed_recognition_report.json`.
2. Po zmianie: uruchom ten sam benchmark na **tych samych przypadkach** i zapisz raport obok.
3. W raporcie końcowym zadania podaj tabelę: `top1_accuracy`, `top3_accuracy`, `false_accept_rate` (od TV-018A), `false_reject_rate`, `avg_correct_margin` — przed i po.
4. Kryterium blokujące: zmiana nie może pogorszyć `top1_accuracy` ani zwiększyć `false_accept_rate` na zbiorze referencyjnym. Wyjątek wymaga jawnej zgody operatora.

Polecenie benchmarku:
```powershell
.venv\Scripts\python.exe tools/benchmark_indexed_recognition.py --index assets/decks/gilded/recognition_index --cases <ścieżka>/benchmark_cases.json --output <ścieżka>/indexed_recognition_report.json
```

Zbiór przypadków fizycznych generuje wizard:
```powershell
.venv\Scripts\python.exe tools/physical_recognition_calibration_wizard.py --index assets/decks/gilded/recognition_index/index_manifest.json --output-dir output/calibration_runs --quick-count 10
```

### 3.2. Wersjonowanie indeksu

- Każda zmiana preprocessingu lub zestawu cech **unieważnia** istniejące pliki `features.npz`. Manifest indeksu musi wtedy dostać podbicie pola `index_version` (`recognition_index_v1` → `v2` …) oraz nowe pole opisujące preprocessing (szczegóły w TV-018E).
- `IndexedImageMatcher` musi konfigurować ekstrakcję cech cropa **na podstawie manifestu wczytanego indeksu**, nigdy na podstawie zaszytych defaultów — inaczej stary indeks z nowym kodem da ciche błędy dopasowania (szczegóły w TV-018E, sekcja „Spójność matcher–indeks").

### 3.3. Kompatybilność wsteczna

- Formaty wynikowe (`match_result`, `table_state.json`, raport benchmarku) wolno **rozszerzać o nowe pola**, nie wolno usuwać ani zmieniać znaczenia istniejących.
- `ImageMatcher` (fallback bez indeksu) pozostaje nietknięty we wszystkich zadaniach poza miejscami wskazanymi jawnie.

### 3.4. Testy

- Framework: `unittest` (standard projektu — patrz `tests/test_benchmark_indexed_recognition.py`). Uruchamianie: `.venv\Scripts\python.exe -m unittest discover -s . -p test_*.py -v`.
- Wzorzec: wstrzykiwanie zależności przez konstruktor (fake'i jak `FakeMatcher`, `FakeCapturePipeline` w istniejących testach), bez patchowania importów.
- Każde zadanie dodaje testy jednostkowe dla nowej logiki; testy nie mogą wymagać fizycznej kamery (logika kamerowa za interfejsem, jak w wizardzie).

### 3.5. Raport końcowy zadania

Format z `AGENTS.md` sekcja 8 (Wykonane / Zmienione pliki / Jak przetestować / Poza zakresem — nie ruszano / Uwagi) + tabela benchmarku z 3.1.

---

## 4. Docelowe metryki programu (Definition of Done)

Mierzone na fizycznym benchmarku pełnej talii (79 referencji × 2 rotacje = 158 przypadków, wygenerowanym wizardem po TV-018D):

| Metryka | Cel |
|---|---|
| `top1_accuracy` | ≥ 0.97 |
| `false_accept_rate` (przy progach produkcyjnych) | 0.00 |
| `false_reject_rate` | ≤ 0.05 |
| Karty poziome (rotacja 90°/270° na stole) | rozpoznawane (osobny zestaw ≥ 10 przypadków) |
| Czas rozpoznania jednej karty (pełny tor matcher + weryfikacja) | ≤ 500 ms na CPU |

---

## 5. TV-018A — Rozszerzenie benchmarku o false-accept, pary mylone i sweep progów

**ID zadania:** TV-018A
**Nazwa zadania:** Benchmark v2 — metryki bezpieczeństwa decyzji i strojenie progów
**Gałąź:** `task/TV-018A-benchmark-extensions`

### Cel
Benchmark ma mierzyć wszystkie tryby błędu bramki decyzyjnej (w tym najgroźniejszy: false-accept), raportować systematycznie mylone pary kart oraz wyliczać charakterystykę progów (sweep), aby progi w TV-018G mogły zostać dobrane z danych.

### Kontekst projektu
`tools/benchmark_indexed_recognition.py` (TV-016E) liczy obecnie: top1/top3 accuracy, `false_reject` (poprawny top1, ale decyzja `unrecognized`), liczniki decyzji, min/avg score i margines poprawnych dopasowań. Rekordy per-przypadek już zawierają `top1_score`, `score_margin_top1_top2`, `is_top1_correct`, `recognition_decision` — sweep progów da się policzyć z samych rekordów, bez ponownego dopasowywania.

### Zakres
1. W `build_summary()` dodaj:
   - `false_accept_count` / `false_accept_rate` — przypadki, gdzie `recognition_decision == "recognized"` **i** `is_top1_correct == False`;
   - `rotation_correct_count` / `rotation_correct_rate` — liczone po przypadkach z `is_rotation_correct is not None`;
   - `misrecognized_pairs` — lista `{expected_reference_id, predicted_reference_id, count, avg_top1_score, avg_margin}` zagregowana po wszystkich przypadkach z błędnym top1, posortowana malejąco po `count`.
2. Nowa funkcja `build_threshold_sweep(case_records, score_grid, margin_grid) -> list[dict]`:
   - siatka domyślna: `min_score` od 0.70 do 0.95 co 0.01; `min_margin` od 0.00 do 0.10 co 0.005;
   - dla każdej kombinacji symuluj decyzję na rekordach (ta sama logika co `apply_recognition_decision`: `recognized` gdy `top1_score ≥ min_score` i `margin ≥ min_margin`) i policz: `recognized_rate`, `false_accept_rate`, `false_reject_rate`, `ambiguous_rate`;
   - wynik zapisywany w raporcie pod kluczem `threshold_sweep`.
3. Nowa funkcja `recommend_thresholds(sweep) -> dict`:
   - wybierz kombinację maksymalizującą `recognized_rate` przy ograniczeniu `false_accept_rate == 0.0`; przy remisie wybierz wyższy `min_score`;
   - wynik w raporcie pod kluczem `recommended_thresholds`: `{min_recognition_score, min_score_margin, expected_recognized_rate, expected_false_reject_rate}`;
   - gdy żadna kombinacja nie daje `false_accept_rate == 0.0`, zwróć kombinację o minimalnym `false_accept_rate` i ustaw flagę `"constraint_satisfied": false`.
4. Wszystkie zmiany w raporcie wyłącznie **addytywne** (istniejące klucze bez zmian — wizard i jego testy konsumują obecny format).
5. Testy jednostkowe w `tests/test_benchmark_indexed_recognition.py`: false-accept zliczany poprawnie; pary mylone agregowane; sweep daje monotoniczność (wyższy próg ⇒ nie więcej recognized); rekomendacja spełnia ograniczenie; przypadki brzegowe (0 błędów, 0 przypadków).

### Poza zakresem
- Zmiany w `recognition/decision.py`, matcherach, wizardzie.
- Automatyczne stosowanie rekomendowanych progów (to TV-018G).

### Pliki do utworzenia lub zmiany
- `tools/benchmark_indexed_recognition.py` (zmiana)
- `tests/test_benchmark_indexed_recognition.py` (zmiana)

### Kryteria akceptacji
1. Raport zawiera nowe klucze: `false_accept_count`, `false_accept_rate`, `rotation_correct_rate`, `misrecognized_pairs`, `threshold_sweep`, `recommended_thresholds`.
2. Stare klucze raportu niezmienione; istniejące testy przechodzą bez modyfikacji ich asercji (poza ewentualnym dopisaniem nowych).
3. `.venv\Scripts\python.exe -m unittest tests.test_benchmark_indexed_recognition` — wszystkie testy zielone.

### Test ręczny
Uruchom benchmark na dowolnym istniejącym zbiorze z `output/calibration_runs/` i sprawdź w JSON obecność oraz sensowność nowych sekcji (np. że `recommended_thresholds.min_recognition_score` mieści się w siatce).

### Uwagi integracyjne
Funkcje `build_threshold_sweep` i `recommend_thresholds` będą importowane przez optymalizator z TV-018G — utrzymuj je jako czyste funkcje na liście rekordów (bez I/O).

---

## 6. TV-018B — Poprawka orientacji w CardCropper (karty poziome)

**ID zadania:** TV-018B
**Nazwa zadania:** Mapowanie długiej krawędzi karty na długi bok cropu
**Gałąź:** `task/TV-018B-cropper-orientation`

### Cel
Crop karty ma zawsze zachowywać proporcje fizycznej karty: długa krawędź karty trafia na długi bok kanonicznego cropu 600×1032, niezależnie od tego, czy karta leży na stole pionowo, poziomo czy skośnie. Po tej poprawce pozostała niejednoznaczność orientacji to wyłącznie 0°/180°, którą matcher już obsługuje.

### Kontekst projektu
`CardCropper.crop_card` (`src/tarotvision/vision/cropper.py`, linie 36–100) porządkuje narożniki przez `order_points` (sortowanie po sumie i różnicy współrzędnych obrazu) i mapuje je sztywno na `[[0,0],[599,0],[599,1031],[0,1031]]`. Dla karty leżącej poziomo jej długa krawędź zostaje zmapowana na krótki bok cropu — obraz jest obrócony o 90° i niejednorodnie przeskalowany, co całkowicie psuje dopasowanie. Wejściowe narożniki pochodzą z `cv2.boxPoints` w `CardRefinery.refine_card` i tworzą zawsze prostokąt (kolejność obiegowa, punkt startowy zależny od kąta).

### Zakres
1. W `CardCropper.crop_card`, po `order_points`, zmierz długości krawędzi uporządkowanego czworokąta:
   - `top_len = ‖TL−TR‖`, `bottom_len = ‖BL−BR‖`, `left_len = ‖TL−BL‖`, `right_len = ‖TR−BR‖`;
   - `horiz = (top_len + bottom_len) / 2`, `vert = (left_len + right_len) / 2`.
2. Jeżeli `horiz > vert` (karta leży poziomo względem obrazu stołu): przesuń cyklicznie listę narożników o jedną pozycję — `src_pts_rot = [TR, BR, BL, TL]` — tak aby fizycznie długa krawędź mapowała się na bok o długości 1032 px. Wybór kierunku przesunięcia jest umowny (obrót treści o 90° vs 270°); pozostałą niejednoznaczność 180° rozstrzyga matcher.
3. Przypadek prawie-kwadratowy: jeżeli `max(horiz, vert) / min(horiz, vert) < 1.05`, nie zmieniaj kolejności i zaloguj ostrzeżenie (geometria niezgodna z profilem talii — `aspect_ratio_height_to_width` dla Gilded wynosi 1.72).
4. Do słownika wynikowego dodaj pola diagnostyczne: `"orientation_normalized": bool` (czy wykonano przesunięcie) oraz `"source_card_landscape": bool`.
5. Testy jednostkowe w nowym pliku `tests/test_card_cropper_orientation.py`:
   - zbuduj syntetyczny obraz stołu z wzorcem o jednoznacznej orientacji (np. prostokąt 200×344 px z białym pasem przy „górnej" krótkiej krawędzi i czarnym przy „dolnej");
   - umieść wzorzec pod kątami 0°, 90°, 180°, 270° i ~30° (przez `cv2.warpAffine`), wyznacz narożniki przez `cv2.boxPoints(((cx,cy),(w,h),angle))`;
   - dla każdego przypadku wykonaj `crop_card` i zweryfikuj: (a) crop ma 600×1032; (b) crop **lub crop obrócony o 180°** ma jasny pas przy krótkiej krawędzi — czyli treść nie jest obrócona o 90° ani rozciągnięta; (c) `source_card_landscape` zgadza się z ułożeniem.

### Poza zakresem
- Zmiany w `CardRefinery`, `DiffDetector`, matcherach.
- Obsługa kart częściowo zasłoniętych.

### Pliki do utworzenia lub zmiany
- `src/tarotvision/vision/cropper.py` (zmiana)
- `tests/test_card_cropper_orientation.py` (nowy)

### Interfejs wejścia/wyjścia
Sygnatura `crop_card(image, card_metadata, deck_profile=None)` bez zmian; słownik wynikowy rozszerzony o 2 pola (3.3 — addytywnie).

### Kryteria akceptacji
1. Testy 5 orientacji przechodzą.
2. Crop karty pionowej (dotychczasowy przypadek) bajt-w-bajt identyczny jak przed zmianą (test regresyjny: orientacja 0° ⇒ `orientation_normalized == False`).
3. Benchmark przed/po na istniejącym zbiorze pionowym: brak regresji (3.1).

### Test ręczny
Uruchom `.venv\Scripts\python.exe test_card_detection_diff.py`, połóż kartę **poziomo** — w `output/processed/crops/` crop ma być nierozciągnięty (proporcje karty zachowane), a rozpoznanie ma zwrócić sensownego kandydata.

### Uwagi integracyjne
TV-018F może później odczytywać faktyczny obrót karty z homografii ORB; pola diagnostyczne z tego zadania pozwolą odtworzyć pełną orientację na stole (potrzebne w przyszłości dla overlay i znaczenia kart odwróconych).

---

## 7. TV-018C — Crop karty z natywnej rozdzielczości kamery (pojedynczy warp)

**ID zadania:** TV-018C
**Nazwa zadania:** Jednoprzebiegowy warp klatka→karta z pominięciem pośredniego obrazu stołu
**Gałąź:** `task/TV-018C-native-crop`

### Cel
Crop 600×1032 ma być liczony jedną transformacją perspektywiczną bezpośrednio z surowej klatki 1920×1080, zamiast z dwukrotnie przepróbkowanego obrazu stołu 1200×800. Detekcja (diff, refinery) pozostaje na warpie stołu — zmienia się wyłącznie źródło pikseli finalnego cropu.

### Kontekst projektu
- `TablePerspectiveCorrector.get_warped_table` (`src/tarotvision/vision/perspective.py`, linie 67–120) **już zwraca** macierz `matrix` (3×3, `cv2.getPerspectiveTransform`) jako drugi element krotki; `test_card_detection_diff.py` ignoruje ją (`warped, _ = ...`, linie 157 i 231).
- Narożniki karty z `CardRefinery` są we współrzędnych obrazu stołu (1200×800). Współrzędne w klatce natywnej: `corners_frame = cv2.perspectiveTransform(corners_table, np.linalg.inv(matrix))`.
- Surowa klatka `frame` jest dostępna w tej samej iteracji pętli głównej, w której wykonywany jest crop (przepływ: capture → warp → diff → refine → crop w jednym obiegu) — nie trzeba niczego dodawać do `SnapshotManager`.

### Zakres
1. W `CardCropper` dodaj metodę:
   ```python
   def crop_card_native(self, original_frame, table_matrix, card_metadata, deck_profile=None) -> dict | None
   ```
   - przelicz narożniki karty (po uporządkowaniu i normalizacji orientacji z TV-018B) na współrzędne klatki natywnej przez odwrotność `table_matrix` (`cv2.perspectiveTransform` wymaga kształtu `(N,1,2)` i `float32`);
   - zweryfikuj, że wszystkie przeliczone narożniki leżą w granicach klatki (z tolerancją 2 px); jeśli nie — zwróć `None` (wołający użyje fallbacku);
   - policz `cv2.getPerspectiveTransform(corners_frame, dst)` i jeden `cv2.warpPerspective` z `original_frame` do 600×1032;
   - w słowniku wynikowym ustaw `"transform_source": "native_frame_single_warp"` i dodaj `"crop_source": "native_frame"`.
   - logika porządkowania/orientacji narożników ma być **współdzielona** z `crop_card` (wydziel prywatną metodę pomocniczą — nie duplikuj kodu).
2. W `test_card_detection_diff.py`:
   - przechwyć macierz: `warped, table_matrix = corrector.get_warped_table(frame, crop_to_markers=True)` (pętla główna, obecnie linia 231);
   - w miejscu cropu (obecnie linia 353): najpierw spróbuj `cropper.crop_card_native(frame, table_matrix, card_data, deck_profile)`; przy `None` użyj dotychczasowego `cropper.crop_card(warped, card_data, deck_profile)`;
   - pole `crop_source` zapisuj w metadanych detekcji (trafia do rekordu diagnostycznego i przez `files`/`diagnostics` do TableState — wystarczy dołożyć do istniejącego słownika metadanych, bez zmian w `state/table_state.py`).
3. W `tools/physical_recognition_calibration_wizard.py` w klasie `ExistingVisionCapturePipeline` analogicznie: przechwyć macierz i preferuj crop natywny (fallback jak wyżej) — żeby zbiory benchmarkowe i przyszły enrollment używały tego samego toru.
4. Testy jednostkowe `tests/test_card_cropper_native.py`:
   - syntetyczna „klatka" z wzorcem + znana macierz warpa stołu; zweryfikuj, że `crop_card_native` daje treść zgodną z `crop_card` na warpie (porównanie po downsamplingu, tolerancja MAE), ale o wyższej ostrości (wariancja Laplace'a natywnego cropu ≥ wariancja cropu z warpu, gdy wzorzec ma drobne detale);
   - przypadek narożników poza klatką ⇒ `None`.

### Poza zakresem
- Zmiany w `SnapshotManager`, `DiffDetector`, `MotionDetector` (detekcja zostaje na warpie 1200×800).
- Zmiany rozdzielczości warpa stołu.

### Pliki do utworzenia lub zmiany
- `src/tarotvision/vision/cropper.py` (zmiana)
- `test_card_detection_diff.py` (zmiana)
- `tools/physical_recognition_calibration_wizard.py` (zmiana)
- `tests/test_card_cropper_native.py` (nowy)

### Kryteria akceptacji
1. Testy jednostkowe zielone; istniejące testy wizardu zielone (interfejs `ExistingVisionCapturePipeline` niezmieniony dla fake'ów).
2. W teście fizycznym crop ma `crop_source == "native_frame"` (fallback loguje ostrzeżenie).
3. Benchmark przed/po (3.1): brak regresji. Uwaga: dopóki indeks pochodzi ze skanów, poprawa może być niewielka — pełny efekt po TV-018D/E.

### Test ręczny
`.venv\Scripts\python.exe test_card_detection_diff.py`, połóż kartę z drobnym tekstem; porównaj wizualnie `output/processed/crops/card_crop_NNN.png` z cropem sprzed zmiany — tekst ma być wyraźnie ostrzejszy.

### Uwagi integracyjne
Macierz warpa zmienia się w każdej iteracji (markery wykrywane na bieżąco) — używaj macierzy **z tej samej iteracji**, z której pochodzi obraz stołu użyty w detekcji. Nie cachuj macierzy między iteracjami.

---

## 8. TV-018D — Kamerowy indeks referencyjny (enrollment talii)

**ID zadania:** TV-018D
**Nazwa zadania:** Przechwycenie referencji talii kamerą i budowa indeksu z domeny kamery
**Gałąź:** `task/TV-018D-camera-reference-index`

### Cel
Wyeliminować domain gap: indeks cech ma być budowany z cropów przechwyconych **tą samą kamerą i tym samym torem geometrycznym**, którym pracuje rozpoznawanie na żywo. Skany pozostają w `reference_scans/` jako grafiki wzorcowe (przyszły overlay), ale przestają być źródłem cech.

### Kontekst projektu
- Wizard (`tools/physical_recognition_calibration_wizard.py`) ma już cały tor przechwytywania: `ExistingVisionCapturePipeline` (CameraCapture 1920×1080, TablePerspectiveCorrector, MotionDetector, DiffDetector(diff_threshold=25, min_area=10000, max_area=150000), CardRefinery(margin=20), CardCropper), kontrolę jakości `crop_quality_check()`, plany kart z manifestu indeksu, tryby auto/manual i strukturę katalogów sesji. Zadanie polega na **reużyciu** tych komponentów, nie na pisaniu nowego toru.
- `ReferenceLoader.load_references(deck_id)` (`src/tarotvision/recognition/reference_loader.py`) czyta podkatalog `reference_scans` (rozszerzenia: .png/.jpg/.jpeg/.bmp/.tiff; `reference_id` = stem pliku).
- `ReferenceIndexBuilder.build_index(deck_id)` (`src/tarotvision/recognition/index_builder.py`) woła ten loader, zapisuje `features.npz` + `index_manifest.json` do `assets/decks/<deck_id>/recognition_index/`; ścieżka źródłowa `reference_scans/` jest też zaszyta w manifestach (linie 137 i 179).
- `ReferenceIndexLoader.load_index(deck_id)` czyta wyłącznie `assets/decks/<deck_id>/recognition_index/` — produkcyjne przełączenie indeksu odbywa się przez podmianę zawartości tego katalogu.
- Nazewnictwo plików kamerowych musi zachować te same `reference_id` (`Gilded_00` … `Gilded_77`, `Gilded_back`), bo `card_mapping.json` mapuje po `reference_id`.

### Zakres
1. **Parametryzacja źródła referencji:**
   - `ReferenceLoader.load_references(deck_id, source_subdir: str = "reference_scans")`;
   - `ReferenceIndexBuilder.__init__(..., source_subdir: str = "reference_scans", output_subdir: str = "recognition_index")` i użycie tych pól w `build_index` (w tym w polach manifestu `source_scan_dir` i `references[].source_path`);
   - nowe pole manifestu: `"source_domain": "scan" | "camera"`.
2. **Narzędzie CLI budowy indeksu** `tools/build_recognition_index.py`:
   - argumenty: `--deck` (wymagany), `--source-subdir` (default `reference_scans`), `--output-subdir` (default `recognition_index`), `--source-domain` (default wyprowadzany: `camera` gdy source-subdir to `camera_references`, inaczej `scan`);
   - wypisuje podsumowanie: liczba referencji, ścieżki plików wynikowych.
3. **Narzędzie enrollment** `tools/enroll_camera_references.py`:
   - importuje z modułu wizardu: `ExistingVisionCapturePipeline`, `crop_quality_check`, pomocniki planu i sesji (jeżeli import wymaga drobnej refaktoryzacji wizardu — np. wydzielenia współdzielonych elementów — wykonaj ją bez zmiany zachowania wizardu i jego CLI);
   - plan: pełna lista `reference_id` z listingu `assets/decks/<deck_id>/reference_scans/` (stemy plików), posortowana; nazwy wyświetlane z `card_mapping.json` (`display_name`), żeby operator wiedział, którą fizyczną kartę położyć;
   - przebieg na kartę: operator kładzie kartę **pionowo, awersem, w orientacji „góra karty od siebie"** (instrukcja w prompt'cie narzędzia) → przechwycenie cropu → `crop_quality_check` → przy `--samples N` (default 3) wybierz próbkę o najlepszym wyniku jakości; pozostałe próbki zapisz w katalogu sesji (diagnostyka);
   - zapis wybranej próbki: `assets/decks/<deck_id>/camera_references/<reference_id>.png` (surowy crop BGR 600×1032, **bez** preprocessingu i bez korekcji barw);
   - manifest enrollmentu `assets/decks/<deck_id>/camera_references/enrollment_manifest.json`: data, profil kamery (`camera_profile_name` z `config/camera_settings.json`), parametry toru (crop_source, rozdzielczość), wyniki jakości per karta, lista braków;
   - tryb `--resume`: pomija karty, które już mają plik PNG (enrollment można dokończyć w kolejnej sesji);
   - kontrola tożsamości: po przechwyceniu wykonaj dopasowanie do **istniejącego indeksu skanowego** i jeżeli `top1 != oczekiwany reference_id`, pokaż ostrzeżenie i wymagaj potwierdzenia operatora (chroni przed pomyleniem fizycznej karty podczas enrollmentu).
4. **Budowa i walidacja indeksu kamerowego:**
   - zbuduj indeks do `recognition_index_camera/` (`--output-subdir recognition_index_camera`);
   - benchmark A/B na tym samym zbiorze przypadków fizycznych: `--index .../recognition_index` vs `--index .../recognition_index_camera`; oba raporty dołącz do raportu zadania;
   - po potwierdzeniu poprawy: udokumentowany krok operatorski podmiany — skopiowanie zawartości `recognition_index_camera/` do `recognition_index/` (loader produkcyjny pozostaje bez zmian).
5. **Korekcja barw (TV-013):** przy dopasowywaniu do indeksu kamerowego profil barwny sesji **nie powinien być stosowany** (obie strony są w domenie kamery). Zakres minimalny: do `config/session_color_calibration.json` nic nie dodawaj; w `test_card_detection_diff.py` pomiń przekazywanie profilu, gdy manifest aktywnego indeksu ma `source_domain == "camera"` (jeden warunek `if` przy wywołaniu `match_card`).
6. Testy jednostkowe: parametryzacja loadera/buildera (tymczasowe katalogi z 2–3 sztucznymi PNG); logika wyboru najlepszej próbki; `--resume`; tożsamość zapisanych `reference_id`. Tor kamery przez fake pipeline (wzorzec `FakeCapturePipeline` z testów wizardu).

### Poza zakresem
- Usuwanie/zmiana skanów w `reference_scans/`.
- Zmiany w `card_mapping.json` i jego loaderze.
- Automatyczna podmiana produkcyjnego indeksu (decyzja operatora).
- Wielość talii naraz (enrollment per talia).

### Pliki do utworzenia lub zmiany
- `src/tarotvision/recognition/reference_loader.py` (zmiana — parametr)
- `src/tarotvision/recognition/index_builder.py` (zmiana — parametry + pola manifestu)
- `tools/build_recognition_index.py` (nowy)
- `tools/enroll_camera_references.py` (nowy)
- `tools/physical_recognition_calibration_wizard.py` (ew. refaktoryzacja umożliwiająca import — bez zmian zachowania)
- `test_card_detection_diff.py` (zmiana — warunek z pkt 5)
- `tests/test_enroll_camera_references.py`, `tests/test_build_recognition_index.py` (nowe)

### Kryteria akceptacji
1. Pełny enrollment talii Gilded wykonany fizycznie: 79 plików w `camera_references/` + manifest.
2. Indeks kamerowy zbudowany; benchmark A/B wykazuje poprawę `top1_accuracy` i `avg_correct_margin` względem indeksu skanowego na tym samym zbiorze przypadków.
3. Domyślne wywołania (`ReferenceLoader.load_references(deck_id)`, `ReferenceIndexBuilder().build_index(deck_id)`) zachowują się identycznie jak przed zmianą.
4. Testy jednostkowe zielone.

### Test ręczny
`.venv\Scripts\python.exe tools/enroll_camera_references.py --deck gilded --samples 3` → przejdź 3–4 karty, przerwij, uruchom ponownie z `--resume` — narzędzie kontynuuje od pierwszej brakującej karty.

### Uwagi integracyjne
- Enrollment wykonuj po zmergowaniu TV-018B i TV-018C oraz z zablokowanymi ustawieniami kamery (preflight TV-012) w oświetleniu docelowym sesji. Manifest enrollmentu ma to odnotować.
- Po każdej istotnej zmianie fizycznego setupu (kamera, lampy, wysokość) enrollment należy powtórzyć — odnotuj to w README przy zamykaniu zadania.

---

## 9. TV-018E — Preprocessing v2: CLAHE, pHash, fingerprint krawędziowy

**ID zadania:** TV-018E
**Nazwa zadania:** Odporność cech na oświetlenie i odblaski + spójność matcher–indeks
**Gałąź:** `task/TV-018E-preprocessing-v2`

### Cel
Zastąpić wrażliwą na odblaski globalną normalizację min-max lokalnym wyrównaniem histogramu (CLAHE), dodać cechy pHash i fingerprint krawędziowy oraz zagwarantować, że matcher zawsze ekstrahuje cechy cropa identycznie jak builder indeksu, z którego korzysta.

### Kontekst projektu
- `ReferenceIndexBuilder.extract_features` (`index_builder.py`, linie 31–99): `GaussianBlur(5,5)` → `cv2.normalize(MINMAX)` → 5 cech wg `self.config_features`.
- `IndexedImageMatcher.__init__` tworzy własny `ReferenceIndexBuilder` z **defaultową** konfiguracją (`indexed_matcher.py`, linie 29–33) — ukryte sprzężenie: zmiana defaultów buildera psuje dopasowanie do starych indeksów. To zadanie usuwa tę kruchość.
- Manifest indeksu zawiera już `feature_extractors` (kopię `config_features`) — ale matcher go nie używa.

### Zakres
1. **Konfigurowalny preprocessing w builderze:**
   - `ReferenceIndexBuilder.__init__(..., preprocess: dict | None = None)`; default (kompatybilny wstecz): `{"version": "v1", "blur_kernel": [5,5], "normalization": "minmax"}`;
   - wariant v2: `{"version": "v2", "blur_kernel": [5,5], "normalization": "clahe", "clahe_clip_limit": 2.0, "clahe_tile_grid": [8,8]}` — `cv2.createCLAHE(clipLimit=2.0, tileGridSize=(8,8))` aplikowane na `gray_canon` po rozmyciu, zamiast `cv2.normalize`;
   - manifest dostaje pola `"preprocess"` (pełny dict) i `"index_version": "recognition_index_v2"`.
2. **Nowe cechy** (w `extract_features`, za flagami w `config_features`):
   - `phash` (64-bit): `norm_gray` → resize 32×32 → `cv2.dct(np.float32(...))` → blok 8×8 lewego-górnego rogu → odrzuć współczynnik DC `[0,0]` → próg = mediana pozostałych 63 → wektor `bool` długości 64 (DC zawsze `False`); podobieństwo = `1 − hamming/64`;
   - `edge_fingerprint`: magnituda Sobela (`cv2.Sobel` dx/dy, ksize=3, `cv2.magnitude`) na obrazie po preprocessingu → normalizacja do 0–255 → resize 64×110 → `float32 flatten`; podobieństwo = `1 − MAE/255` (jak `gray_fingerprint`).
3. **Spójność matcher–indeks (krytyczne):**
   - `IndexedImageMatcher.__init__` ma konstruować swój builder z `manifest["feature_extractors"]` i `manifest.get("preprocess", DEFAULT_V1)` — nigdy z defaultów klasy;
   - scoring iteruje po cechach **obecnych w indeksie**: gdy w `features.npz` brakuje którejś cechy (stary indeks), jej waga jest pomijana, a pozostałe wagi renormalizowane (jest już mechanizm normalizacji wag — rozszerz go);
   - wagi domyślne po zmianie (prowizoryczne, stroi je TV-018G): `gray_fingerprint 0.30, region_fingerprints 0.20, edge_fingerprint 0.15, color_histogram 0.10, phash 0.10, gray_histogram 0.05, dhash 0.10`.
4. **Przebudowa i pomiar:** zbuduj indeks v2 z `camera_references/` (TV-018D), benchmark A/B v1-vs-v2 na tym samym zbiorze; dodatkowo zbierz wizardem ≥ 10 przypadków w celowo trudnym oświetleniu (lampa pod kątem, widoczny odblask) i porównaj.
5. Testy jednostkowe: pHash stabilny na obraz + obraz rozjaśniony liniowo (identyczne bity); CLAHE poprawia podobieństwo pary „czysty vs z syntetycznym odblaskiem" względem min-max; matcher ze starym manifestem v1 działa jak dotychczas (regresja); matcher pomija brakujące cechy z renormalizacją wag.

### Poza zakresem
- `ImageMatcher` (fallback) — pozostaje na v1.
- Strojenie wag (TV-018G).
- Zmiany w `session_color_calibration.py`.

### Pliki do utworzenia lub zmiany
- `src/tarotvision/recognition/index_builder.py` (zmiana)
- `src/tarotvision/recognition/indexed_matcher.py` (zmiana)
- `src/tarotvision/recognition/index_loader.py` (zmiana — wczytywanie nowych tablic cech, gdy obecne w NPZ)
- `tests/test_index_features_v2.py` (nowy)

### Kryteria akceptacji
1. Indeks v2 buduje się i jest poprawnie wczytywany; manifest zawiera `preprocess` i nową wersję.
2. Stary indeks v1 nadal działa z nowym kodem (test regresyjny).
3. Benchmark: brak regresji na zbiorze standardowym; poprawa na zbiorze „trudne oświetlenie" (raport w opisie zadania).

### Test ręczny
Połóż kartę tak, by lampa dawała widoczny odblask na laminacie; porównaj `confidence` i `score_margin` z indeksem v1 i v2.

### Uwagi integracyjne
Po tym zadaniu manifest jest jedynym źródłem prawdy o preprocessingu. Każde przyszłe zadanie zmieniające cechy MUSI podbić `index_version` i przejść protokół 3.1.

---

## 10. TV-018F — Weryfikacja geometryczna ORB + RANSAC (drugi stopień dopasowania)

**ID zadania:** TV-018F
**Nazwa zadania:** Coarse-to-fine: weryfikacja kandydatów homografią na punktach kluczowych
**Gałąź:** `task/TV-018F-geometric-verification`

### Cel
Dodać drugi stopień rozpoznawania: dla top-K kandydatów z matchera indeksowego dopasowanie punktów kluczowych ORB z weryfikacją homografii RANSAC. Liczba inlierów daje miarę pewności odporną na odblaski, częściowe przesłonięcie i błędy wycięcia — i rozstrzyga przypadki, w których globalne cechy dają zbyt mały margines (karty blotkowe).

### Kontekst projektu
- `requirements.txt` zawiera `opencv-python` — ORB i AKAZE są dostępne (nie wymagają contrib).
- Strategia techniczna (`docs/02_strategia_techniczna.md`, sekcja Baza Referencyjna) od początku przewidywała „dane techniczne do rozpoznawania obrazu (np. deskryptory cech ORB/SIFT)".
- Wynik matchera przechodzi przez `apply_recognition_decision` na końcu `IndexedImageMatcher.match_card` (`indexed_matcher.py`, linie 201–202).

### Zakres
1. **Deskryptory w indeksie** — rozszerz `ReferenceIndexBuilder`:
   - ekstraktor: `cv2.ORB_create(nfeatures=500, scaleFactor=1.2, nlevels=8)` na obrazie po preprocessingu (ta sama ścieżka co cechy z TV-018E);
   - zapis do **osobnego pliku** `orb_features.npz` w katalogu indeksu (nie powiększaj `features.npz`): tablice spłaszczone z offsetami — `desc_concat` (suma_punktów × 32, uint8), `kp_concat` (suma_punktów × 4: x, y, size, angle, float32), `offsets` (R+1, int64), `reference_ids` (R,);
   - manifest: `"orb_features_file": "orb_features.npz"` + parametry ORB.
2. **Nowy moduł** `src/tarotvision/recognition/geometric_verifier.py`, klasa `GeometricVerifier`:
   - `__init__(self, orb_index: dict, params: dict | None = None)` — defaulty: `{"lowe_ratio": 0.75, "min_good_matches": 10, "ransac_reproj_threshold": 5.0, "min_inliers": 15, "min_inlier_ratio": 0.25}`;
   - `verify(self, crop_image, candidate_reference_ids: list[str]) -> dict` — dla cropa: ekstrakcja ORB (raz), dla każdego kandydata: `BFMatcher(NORM_HAMMING).knnMatch(k=2)` + test ilorazowy Lowe; przy `good < min_good_matches` ⇒ `passed=False`; inaczej `cv2.findHomography(..., cv2.RANSAC, ransac_reproj_threshold)`; sanity-check homografii: rzutowane narożniki referencji tworzą czworokąt wypukły (`cv2.isContourConvex`), stosunek pól w [0.5, 2.0], wyznacznik podmacierzy 2×2 > 0;
   - `passed = inliers ≥ min_inliers and inlier_ratio ≥ min_inlier_ratio and sanity_ok`;
   - dodatkowo wylicz kąt obrotu z homografii (`atan2(h[1,0], h[0,0])`, zaokrąglony do najbliższej z {0, 90, 180, 270}) — pole `rotation_from_homography`;
   - zwrot: `{"crop_keypoints": int, "results": [{"reference_id", "good_matches", "inliers", "inlier_ratio", "passed", "rotation_from_homography"}]}`.
3. **Integracja w `IndexedImageMatcher`:**
   - opcjonalny argument konstruktora `geometric_verifier: GeometricVerifier | None = None` (wstrzykiwanie zależności — zgodnie ze stylem testów projektu);
   - w `match_card`, po zbudowaniu listy kandydatów a **przed** `apply_recognition_decision`: jeżeli verifier obecny — `verify(crop, top_5_ids)`; do wyniku dodaj sekcję `"geometric_verification"`; jeżeli najlepszy kandydat **z `passed=True`** różni się od top1, przesuń go na czoło listy kandydatów (zachowaj oryginalną kolejność w polu `"index_ranking"`);
   - rozszerz `apply_recognition_decision` o opcjonalną ścieżkę: gdy wynik zawiera `geometric_verification`, decyzja `recognized` wymaga dodatkowo `passed=True` dla top1; top1 bez `passed` przy istniejącym innym kandydacie z `passed` ⇒ podmiana opisana wyżej; nikt nie przeszedł ⇒ `unrecognized` z polem `"rejection_reason": "geometric_verification_failed"`. Brak sekcji geometrycznej ⇒ zachowanie identyczne jak dziś (pełna kompatybilność).
4. **Aktywacja w pipeline:** w `test_card_detection_diff.py` twórz verifier, gdy `orb_features.npz` istnieje w katalogu indeksu (analogicznie do obecnej logiki wyboru matchera); loguj jego obecność przy starcie.
5. **Benchmark:** uruchom A/B (z weryfikacją / bez) na pełnym zbiorze; raportuj też wpływ na `misrecognized_pairs` z TV-018A oraz czas na przypadek (budżet: ≤ 300 ms dodatkowo dla K=5 na CPU).
6. Testy jednostkowe `tests/test_geometric_verifier.py`: para crop/referencja z syntetycznym wzorcem bogatym w narożniki (szachownica z naniesionymi znacznikami) ⇒ `passed=True` i poprawna rotacja dla obrotów 0/90/180/270; para niezgodna ⇒ `passed=False`; serializacja/deserializacja `orb_features.npz` (offsety); integracja matcher+verifier na fake'owym verifierze (podmiana top1).

### Poza zakresem
- FLANN/LSH (przy 78 kartach BFMatcher wystarcza).
- Użycie `rotation_from_homography` do semantyki kart odwróconych (przyszłe zadanie).
- `ImageMatcher` (fallback).

### Pliki do utworzenia lub zmiany
- `src/tarotvision/recognition/geometric_verifier.py` (nowy)
- `src/tarotvision/recognition/index_builder.py` (zmiana — ORB do `orb_features.npz`)
- `src/tarotvision/recognition/index_loader.py` (zmiana — opcjonalne wczytanie `orb_features.npz`)
- `src/tarotvision/recognition/indexed_matcher.py` (zmiana — integracja)
- `src/tarotvision/recognition/decision.py` (zmiana — ścieżka geometryczna)
- `test_card_detection_diff.py` (zmiana — aktywacja)
- `tests/test_geometric_verifier.py` (nowy)

### Kryteria akceptacji
1. Testy jednostkowe zielone; stare testy decision/matcher bez zmian zachowania, gdy verifier nieobecny.
2. Benchmark: `false_accept_rate` nie rośnie, `misrecognized_pairs` maleje lub bez zmian, czas w budżecie.
3. Wynik `match_card` zawiera sekcję `geometric_verification` z kompletem pól.

### Test ręczny
Połóż dwie wizualnie podobne karty blotkowe kolejno; porównaj `inliers`/`passed` top-2 kandydatów w zapisanym wyniku rozpoznania.

### Uwagi integracyjne
Werifier wymaga indeksu z `orb_features.npz` — przebuduj indeks narzędziem z TV-018D po wdrożeniu. Progi (`min_inliers` itd.) są prowizoryczne; TV-018G obejmie je strojeniem.

---

## 11. TV-018G — Centralna konfiguracja rozpoznawania + strojenie wag i progów z danych

**ID zadania:** TV-018G
**Nazwa zadania:** `config/recognition.json` + optymalizator parametrów na bazie benchmarku
**Gałąź:** `task/TV-018G-recognition-config-tuning`

### Cel
Zebrać wszystkie parametry rozpoznawania w jednym pliku konfiguracyjnym (zasada z `docs/03`, sekcja 6) i dostarczyć narzędzie, które na podstawie zebranych przypadków benchmarkowych proponuje optymalne wagi cech i progi decyzyjne.

### Kontekst projektu
- Wagi cech: zaszyte w `IndexedImageMatcher.__init__` (`indexed_matcher.py`, linie 36–42).
- Progi: defaulty `apply_recognition_decision(min_recognition_score=0.82, min_score_margin=0.04)` (`decision.py`, linie 5–9).
- Progi weryfikacji geometrycznej: defaulty w `GeometricVerifier` (po TV-018F).
- Sweep progów i rekomendacja: funkcje z TV-018A (`build_threshold_sweep`, `recommend_thresholds`).
- Wzorzec konfiguracyjny w projekcie: `config/camera_settings.json`, `config/session_color_calibration.json`.

### Zakres
1. **Plik `config/recognition.json`** (utworzyć z aktualnymi wartościami produkcyjnymi):
   ```json
   {
     "config_version": "recognition_config_v1",
     "weights": {
       "gray_fingerprint": 0.30, "region_fingerprints": 0.20, "edge_fingerprint": 0.15,
       "color_histogram": 0.10, "phash": 0.10, "gray_histogram": 0.05, "dhash": 0.10
     },
     "decision": {
       "min_recognition_score": 0.82,
       "min_score_margin": 0.04,
       "margin_mode": "absolute"
     },
     "geometric_verification": {
       "enabled": true, "top_k": 5,
       "lowe_ratio": 0.75, "min_good_matches": 10,
       "ransac_reproj_threshold": 5.0, "min_inliers": 15, "min_inlier_ratio": 0.25
     }
   }
   ```
2. **Loader** `src/tarotvision/recognition/config.py`: funkcja `load_recognition_config(path="config/recognition.json") -> dict` — bezpieczne defaulty przy braku pliku/kluczy (deep-merge z wartościami obecnie zaszytymi w kodzie), walidacja sumy wag > 0, cache na poziomie modułu z możliwością resetu (na potrzeby testów).
3. **Podpięcie:** `IndexedImageMatcher` (wagi), `apply_recognition_decision` (progi — argumenty funkcji mają pierwszeństwo nad configiem, config nad dotychczasowymi defaultami), `GeometricVerifier` (parametry), `test_card_detection_diff.py` (top_k, enabled).
4. **Tryb marginesu względnego:** w `apply_recognition_decision` obsłuż `margin_mode: "relative"` — margines liczony jako `(top1 − top2) / max(top1, 1e-6)`; sweep z TV-018A rozszerz o ten tryb (osobna siatka 0.00–0.15 co 0.005).
5. **Optymalizator** `tools/optimize_recognition_params.py`:
   - wejście: `--index`, `--cases` (benchmark_cases.json), `--output` (ścieżka raportu propozycji);
   - krok 1: **prekomputacja** — dla każdego przypadku i każdej referencji policz podobieństwa per-cecha dla rotacji 0° i 180° (jednorazowo; macierz `przypadki × referencje × cechy × 2`); dalsze kroki to wyłącznie operacje macierzowe — nie wywołuj ponownie `match_card`;
   - krok 2: przeszukiwanie wag — próbkowanie Dirichleta (N=2000, seed podawany argumentem `--seed`, default 42) + dostrajanie lokalne top-10 kandydatów (perturbacje współrzędnych ±0.02, renormalizacja); dla każdego zestawu wag: score = ważona suma per-cecha, wybór lepszej rotacji per referencja (identycznie jak matcher), ranking, metryki;
   - funkcja celu: maksymalizuj `top1_accuracy`; remis → wyższy `avg_correct_margin`; następnie dla zwycięskich wag policz `recommend_thresholds` (import z `tools/benchmark_indexed_recognition.py`) dla obu trybów marginesu;
   - wyjście: `recognition_optimization_proposal.json` — zwycięskie wagi, rekomendowane progi (oba tryby), metryki przed/po, parametry przebiegu. **Narzędzie nie zapisuje do `config/recognition.json`** — zastosowanie propozycji to świadoma decyzja operatora (ręczna edycja configu);
   - ograniczenie zakresu: optymalizator NIE stroi parametrów ORB (osobna, droższa pętla — poza zakresem; odnotuj w raporcie jako przyszłą opcję).
6. Testy: loader (brak pliku, częściowy plik, zła suma wag); margines względny w decision; optymalizator na syntetycznych macierzach podobieństw (zbiór, w którym znane „idealne" wagi odzyskiwane są z dokładnością rankingu); determinizm przy stałym seedzie.

### Poza zakresem
- Automatyczna aktualizacja configu produkcyjnego.
- Strojenie parametrów ORB/RANSAC.
- UI.

### Pliki do utworzenia lub zmiany
- `config/recognition.json` (nowy)
- `src/tarotvision/recognition/config.py` (nowy)
- `src/tarotvision/recognition/indexed_matcher.py` (zmiana)
- `src/tarotvision/recognition/decision.py` (zmiana)
- `src/tarotvision/recognition/geometric_verifier.py` (zmiana)
- `tools/optimize_recognition_params.py` (nowy)
- `tools/benchmark_indexed_recognition.py` (ew. drobne rozszerzenie sweepa o tryb względny)
- `test_card_detection_diff.py` (zmiana)
- `tests/test_recognition_config.py`, `tests/test_optimize_recognition_params.py` (nowe)

### Kryteria akceptacji
1. Przy braku `config/recognition.json` system działa identycznie jak przed zadaniem (defaulty w kodzie).
2. Optymalizator na pełnym fizycznym zbiorze produkuje propozycję; po jej ręcznym zastosowaniu benchmark wykazuje `top1_accuracy` ≥ wartości sprzed strojenia i spełnia cele z sekcji 4.
3. Wszystkie testy projektu zielone.

### Test ręczny
Zmień jedną wagę w `config/recognition.json`, uruchom rozpoznanie — wynik `score_breakdown` odzwierciedla nową wagę. Usuń plik — system wraca do defaultów.

### Uwagi integracyjne
Po zamknięciu TV-018G zaktualizuj README (sekcja „Następny Krok Techniczny") o wynik programu i finalne metryki.

---

## 12. Świadomie odłożone: embeddingi neuronowe (CNN)

Decyzja TV-011 („Wyklucza się … klasyfikacja neuronowa") pozostaje w mocy dla całego programu TV-018. Mały model embeddingowy (metric learning, ONNX na CPU) byłby silniejszy od cech ręcznych, ale dokłada zależności i proces treningu.

**Kryterium powrotu do tematu:** jeżeli po TV-018G `top1_accuracy` na pełnym fizycznym benchmarku < 0.97 lub `misrecognized_pairs` nadal zawiera powtarzalne pary blotek — utwórz zadanie TV-019 (embeddingi) z benchmarkiem TV-018A jako kryterium porównawczym.

---

## Załącznik A: Zweryfikowane fakty o kodzie (ściąga dla agenta wykonującego)

Stan na 2026-06-11, po merge PR #8 do `master`:

**Tor główny** — `test_card_detection_diff.py`:
- kamera: `CameraCapture(camera_index=None, width=1920, height=1080, enable_preflight=True)` (linia 82);
- warp: `warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)` (linie 157, 231) — **macierz jest zwracana i ignorowana**;
- diff: `DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)` (linia 47); `roi_rect, debug_mask, diff_debug = diff_detector.detect_change_roi_with_debug(...)` (linia 263);
- refinery: `refinery.refine_card(warped, roi_rect, diff_mask=debug_mask, deck_profile=deck_profile)` (linia 347);
- crop: `cropper.crop_card(warped, card_data, deck_profile)` (linia 353); zapisy: `output/processed/crops/card_crop_{NNN}.png` i `record_dir/crop.png` (linie 403–405);
- matcher: `IndexedImageMatcher(index)` gdy `ReferenceIndexLoader().load_index(deck_id)` zwróci indeks, inaczej `ImageMatcher` (linie 58–78); wywołanie: `matcher.match_card(crop_img, session_color_profile=profile)` (linia 413);
- mapowanie: `enrich_recognition_with_card_mapping(match_res, deck_id)` (linia 417);
- stan: `table_state.add_card_from_recognition(detection_id=..., recognition_result=..., position=..., files=...)` (linia 451), `table_state.save()` (linia 459);
- oryginalna klatka NIE jest nigdzie przechowywana po warpie; `SnapshotManager` trzyma wyłącznie obrazy warpa (`snapshot_0/previous/current` w `output/sessions/current/`).

**Rozpoznawanie:**
- `ReferenceLoader.load_references(deck_id) -> list[{"reference_id", "deck_id", "path", "image"}]`; `reference_id` = stem pliku; rozszerzenia .png/.jpg/.jpeg/.bmp/.tiff; czyta `assets/decks/<deck_id>/reference_scans/`;
- `ReferenceIndexLoader.load_index(deck_id) -> {"manifest": dict, "features": dict} | None`; czyta `assets/decks/<deck_id>/recognition_index/{index_manifest.json, features.npz}`;
- `ReferenceIndexBuilder`: cechy `gray_fingerprint` (64×110), `dhash` (9×8→64 bit), `gray_histogram` (64), `color_histogram` (HSV 8×8×8), `region_fingerprints` (3×3, 16×16); preprocessing: `GaussianBlur(5,5)` + `cv2.normalize(MINMAX)`;
- `IndexedImageMatcher`: wagi 0.40/0.25/0.15/0.10/0.10; rotacje 0°/180°; tworzy własny builder z defaultami (linie 29–33 — do naprawy w TV-018E); na końcu woła `apply_recognition_decision`;
- `apply_recognition_decision(match_result, min_recognition_score=0.82, min_score_margin=0.04)` → pola `top1_*`, `top2_*`, `score_margin`, `recognition_decision` ∈ {recognized, ambiguous, unrecognized}, `ambiguous`, `decision_thresholds`;
- `card_mapping.json`: `assets/decks/gilded/card_mapping.json`; wpisy z `reference_id`, `entry_type` ∈ {tarot_card, deck_back}, `card_id`, `display_name`, `arcana`, `suit`, `rank`, `is_deck_back`; funkcja `enrich_recognition_with_card_mapping(result, deck_id)` dodaje `recognized_card` / `recognized_special` / `mapping_status`.

**Talia / konfiguracja:**
- `DeckProfile` (atrybuty: `deck_id`, `deck_name`, `geometry_source`, `reference_scan_dir`, `card_width_px`, `card_height_px`, `aspect_ratio_height_to_width`, `canonical_width_px`, `canonical_height_px`); plik `assets/decks/gilded/deck_profile.json` (600×1032, ratio 1.72);
- `DeckLibrary.load_active_profiles()` — czyta `assets/decks/active_decks.json` (`{"active_decks": ["gilded"]}`), fallback `["gilded"]`;
- `config/camera_settings.json` (profil `ankerwork_c310_default`, 1920×1080, lock auto-parametrów, progi jakości), `config/session_color_calibration.json` (`enabled: true`, `apply_to_matcher: true`, referencja `Gilded_38`);
- referencje: 79 plików PNG `Gilded_00..77` + `Gilded_back` w `assets/decks/gilded/reference_scans/`;
- `requirements.txt`: `opencv-python`, `numpy`, `pygrabber (win32)`; pakiet `tarotvision` zainstalowany edytowalnie (src-layout, `src/tarotvision.egg-info/`); brak `pyproject.toml`/`setup.py` w repo.

**Narzędzia TV-016E:**
- `tools/benchmark_indexed_recognition.py`: czyste funkcje `evaluate_match_case`, `build_summary`, `benchmark_cases(cases, matcher, image_loader)`; CLI `--index --cases --output`; format przypadku: `{"crop_path", "expected_reference_id", "expected_rotation"}`;
- `tools/physical_recognition_calibration_wizard.py`: `ExistingVisionCapturePipeline` (reużywa CameraCapture/Corrector/MotionDetector(threshold=1.2)/DiffDetector(25,10000,150000)/CardRefinery(margin=20)/CardCropper), `crop_quality_check()` (jasność, ostrość, prześwietlenie, gęstość krawędzi), plan z manifestu indeksu lub `--plan`/`--quick-count`, rotacje `--rotations` (default 0,180), `--samples-per-pose`, struktura sesji `crops/ snapshots/ diagnostics/ benchmark_cases.json run_manifest.json`; zależności wstrzykiwane konstruktorem (pipeline, benchmark runner, input/print) — wzorzec do naśladowania;
- testy: `unittest`, fake'i `FakeMatcher`, `FakeCapturePipeline`, `FakeBenchmarkRunner`; bez patchowania importów.

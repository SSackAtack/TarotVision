# Zadanie: TV-006

## ID zadania
TV-006

## Nazwa zadania
Rolling Snapshot Comparison — korekta logiki porównywania snapshotów

## Status
Zakończone.

## Cel
Skorygowanie obecnego mechanizmu detekcji różnicowej tak, aby system nie porównywał każdej kolejnej sceny wyłącznie do pustej maty `Snapshot_0`, lecz wykrywał nową zmianę względem ostatniego zaakceptowanego stanu stołu.

Celem nie jest dodawanie rozpoznawania nazw kart. Celem jest uporządkowanie logiki sesji i przygotowanie detekcji pod wiele kolejno dokładanych kart.

---

## Kontekst obecnego systemu

Projekt ma obecnie działający pipeline snapshot-diff:

```text
CameraCapture
↓
TablePerspectiveCorrector
↓
MotionDetector
↓
SnapshotManager
↓
DiffDetector
↓
CardRefinery
↓
detected_cards.json
```

Obecny system potrafi:

- wykrywać kamerę fizyczną,
- prostować stół przez markery ArUco,
- wymuszać lub automatycznie wykonywać `Snapshot_0`,
- wykrywać ruch i stabilizację,
- wykonać snapshot aktualnego stołu,
- porównać aktualną scenę z referencją,
- wykryć ROI karty,
- doprecyzować krawędzie karty,
- zapisać JSON i obraz diagnostyczny.

Problem architektoniczny polega na tym, że aktualna pętla detekcji porównuje każdą kolejną scenę do `Snapshot_0`, czyli do pustej maty.

Obecny model:

```text
Snapshot_0 = pusty stół

Snapshot_1 = stół + karta 1
porównanie: Snapshot_1 - Snapshot_0

Snapshot_2 = stół + karta 1 + karta 2
porównanie: Snapshot_2 - Snapshot_0

Snapshot_3 = stół + karta 1 + karta 2 + karta 3
porównanie: Snapshot_3 - Snapshot_0
```

Taki model działa dla jednej karty, ale przy kolejnych kartach różnica obejmuje cały aktualny rozkład, a nie tylko nową zmianę.

---

## Decyzja architektoniczna

Wykrywanie nowej zmiany powinno działać na zasadzie porównania rolling snapshotów:

```text
Snapshot_0 = pusty stół, zatwierdzony przez operatora
Snapshot_previous = ostatni zaakceptowany stan stołu
Snapshot_current = nowy kandydat po ustaniu ruchu
```

Główne porównanie detekcyjne:

```text
Snapshot_current - Snapshot_previous
```

Nie:

```text
Snapshot_current - Snapshot_0
```

`Snapshot_0` ma pozostać w systemie jako stała kotwica sesji, ale nie powinien być domyślną referencją dla każdej kolejnej detekcji nowej karty.

---

## Rola poszczególnych snapshotów

### Snapshot_0 / empty_reference

Rola:

- pusty stół / pusta mata,
- punkt startowy sesji,
- referencja kalibracyjna,
- kotwica do pełnego audytu rozkładu,
- awaryjna baza do resetu lub ponownej analizy,
- możliwość sprawdzenia całego aktualnego rozkładu względem pustej sceny.

Zasada:

- powinien być wykonany i zatwierdzony przez operatora,
- nie powinien być przypadkowo nadpisywany,
- nie powinien być automatycznie uznawany za poprawny bez świadomości operatora.

### Snapshot_previous / previous_accepted

Rola:

- ostatni zaakceptowany stan stołu,
- główna referencja do wykrywania nowej zmiany,
- powinien być aktualizowany tylko po zaakceptowanej detekcji.

Zasada:

- po zapisaniu `Snapshot_0` należy ustawić `Snapshot_previous = Snapshot_0`,
- po każdej zaakceptowanej zmianie należy ustawić `Snapshot_previous = Snapshot_current`,
- jeśli detekcja się nie powiedzie albo zostanie uznana za fałszywą, `Snapshot_previous` nie może być aktualizowany.

### Snapshot_current / current_candidate

Rola:

- aktualny obraz stołu po ustaniu ruchu,
- kandydat do porównania z `Snapshot_previous`,
- po zaakceptowaniu staje się nowym `Snapshot_previous`.

Zasada:

- może być nadpisywany,
- nie trzeba przechowywać całej historii snapshotów.

---

## Docelowy przebieg sesji

```text
START SESJI

1. Operator przygotowuje pusty stół.
2. Operator zatwierdza Snapshot_0.
3. System zapisuje Snapshot_0.
4. System ustawia Snapshot_previous = Snapshot_0.

PĘTLA PRACY

5. System obserwuje ruch.
6. Po ustaniu ruchu zapisuje Snapshot_current.
7. System porównuje:
   Snapshot_current - Snapshot_previous

8. Jeżeli zmiana wygląda jak karta:
   - wykryj ROI,
   - doprecyzuj krawędzie przez CardRefinery,
   - zapisz metadane,
   - zaakceptuj nowy stan:
     Snapshot_previous = Snapshot_current

9. Jeżeli zmiana nie wygląda jak karta:
   - nie aktualizuj Snapshot_previous,
   - zapisz diagnostykę błędu,
   - czekaj na kolejną stabilizację.
```

---

## Ważna decyzja: Snapshot_0 powinien być wymuszony przez operatora

Obecny Auto-Preflight jest wygodny, ale może być ryzykowny.

Ryzyko:

- operator zostawi kartę na stole,
- na stole będzie pudełko, cień, ręka albo dekoracja,
- system po 3 sekundach stabilności uzna ten stan za pustą matę,
- później ten obiekt stanie się częścią tła i nie będzie poprawnie wykrywany.

Dlatego docelowo:

```text
Snapshot_0 powinien być zatwierdzany świadomie przez operatora.
```

Rekomendowane zachowanie:

- system może pokazać komunikat, że obraz jest stabilny,
- system może zasugerować: „Stół stabilny — naciśnij SPACJĘ, aby zatwierdzić pustą matę”,
- zapis `Snapshot_0` następuje dopiero po akcji operatora.

Auto-Preflight może zostać później jako opcja konfiguracyjna, ale nie powinien być domyślną ścieżką pracy na tym etapie.

---

## Zakres TV-006

### 1. SnapshotManager

Dostosować lub rozszerzyć `src/tarotvision/storage/snapshots.py` tak, aby jawnie obsługiwał trzy role:

```text
snapshot_0 / empty_reference
snapshot_previous / previous_accepted
snapshot_current / current_candidate
```

Wymagane zachowania:

- po zapisaniu `Snapshot_0` ustawić `snapshot_previous = snapshot_0`,
- dodać metodę typu `accept_current_as_previous()` albo równoważną,
- nie aktualizować `snapshot_previous` przy samym zapisie `snapshot_current`, jeśli detekcja nie została zaakceptowana,
- nie przechowywać historii wszystkich snapshotów,
- na dysku wystarczą:
  - `snapshot_0.png`,
  - `snapshot_previous.png`,
  - `snapshot_current.png`.

### 2. test_card_detection_diff.py

Zmienić główną pętlę detekcji:

Obecnie do porównania używany jest `Snapshot_0`:

```python
snap_0 = snapshot_manager.get_snapshot_0()
roi_rect, debug_mask = diff_detector.detect_change_roi(warped, snap_0)
```

Docelowo powinno być używane `Snapshot_previous`:

```python
previous = snapshot_manager.get_snapshot_previous()
roi_rect, debug_mask = diff_detector.detect_change_roi(snapshot_current, previous)
```

Po sukcesie:

```python
snapshot_manager.accept_current_as_previous()
```

Po porażce:

```python
# nie aktualizować snapshot_previous
```

### 3. Snapshot_0 jako ręczny krok operatora

Zmienić logikę preflightu:

- domyślnie `Snapshot_0` powinien wymagać zatwierdzenia przez operatora,
- Auto-Preflight nie powinien sam zapisywać pustej maty bez akcji operatora,
- można zostawić licznik stabilności jako informację pomocniczą,
- zachować możliwość ręcznego nadpisania `Snapshot_0` przez operatora.

### 4. Test offline

Zaktualizować `test_card_detection_offline.py` lub dodać nowy test, który potwierdzi sekwencję rolling comparison.

Minimalny test offline powinien obejmować:

```text
empty_table.png
one_card.png
two_cards.png
```

Oczekiwany przebieg:

```text
Snapshot_previous = empty_table
current = one_card
różnica wykrywa kartę 1
accept → previous = one_card

current = two_cards
różnica wykrywa tylko nową kartę 2
accept → previous = two_cards
```

Jeżeli nie ma jeszcze realnych próbek `one_card.png` i `two_cards.png`, test może zostać przygotowany strukturalnie, a próbki uzupełnione później.

---

## Poza zakresem TV-006

Nie robić w tym zadaniu:

- rozpoznawania nazw kart,
- klasyfikacji talii,
- OCR,
- overlay HTML,
- WebSocket,
- obsługi wielu kart jako finalnego TableState,
- treningu modelu AI,
- YOLO / ONNX / OpenVINO,
- rozbudowanego interfejsu operatora.

To zadanie dotyczy tylko korekty logiki snapshotów i właściwej referencji porównawczej.

---

## Kryteria akceptacji

TV-006 można uznać za zakończone, jeśli:

1. `Snapshot_0` jest zapisywany świadomie przez operatora albo auto-preflight jest wyłączony domyślnie.
2. Po zapisaniu `Snapshot_0` system ustawia `Snapshot_previous = Snapshot_0`.
3. Po ustaniu ruchu system zapisuje `Snapshot_current`.
4. Główne porównanie detekcyjne działa jako:

```text
Snapshot_current - Snapshot_previous
```

5. Po skutecznej detekcji karta jest zapisana do JSON i dopiero wtedy:

```text
Snapshot_previous = Snapshot_current
```

6. Po nieudanej detekcji `Snapshot_previous` nie jest aktualizowany.
7. Na dysku nie powstaje długa historia snapshotów.
8. Test offline lub live potwierdza sekwencję:

```text
empty → one_card → two_cards
```

z wykrywaniem tylko nowej zmiany względem poprzedniego zaakceptowanego stanu.

---

## Uwaga architektoniczna na przyszłość

`Snapshot_0` nadal może być używany w przyszłości do pełnego audytu całego rozkładu:

```text
Snapshot_current - Snapshot_0
```

ale nie powinien być domyślną referencją dla wykrywania kolejnej nowo dołożonej karty.

Docelowo system może mieć dwa tryby:

```text
change detection:
Snapshot_current - Snapshot_previous

full layout audit:
Snapshot_current - Snapshot_0
```

TV-006 dotyczy wyłącznie pierwszego trybu, czyli `change detection`.

---

## Pierwotnie planowany następny krok po TV-006

Dopiero po tej korekcie można bezpiecznie planować:

```text
TV-007 — standaryzacja DetectedCard / detection_confidence
TV-008 — crop i prostowanie pojedynczej karty
TV-009 — rozpoznawanie konkretnej karty na podstawie cropa
```

Po fizycznej weryfikacji TV-006 najbliższym praktycznym krokiem powinno być jednak ustabilizowanie `CardRefinery`, ponieważ rolling comparison działa, a błąd ujawnia się dopiero przy finalnym dopasowaniu ramki do drugiej karty.

---

## Wynik realizacji

*   **Data realizacji:** 2026-06-07
*   **Ścieżka projektu:** `E:\Antigravity\Projekty\TarotVision`

Wynik:
*   `SnapshotManager` obsługuje jawne role `snapshot_0`, `snapshot_previous` i `snapshot_current`.
*   Zapis `Snapshot_0` ustawia jednocześnie `Snapshot_previous`.
*   Zapis `Snapshot_current` nie aktualizuje `Snapshot_previous`.
*   Dodano jawne zaakceptowanie stanu przez `accept_current_as_previous()`.
*   Główna pętla `test_card_detection_diff.py` porównuje teraz `Snapshot_current - Snapshot_previous`.
*   Po nieudanej detekcji `Snapshot_previous` nie jest aktualizowany.
*   Auto-Preflight nie zapisuje już automatycznie pustej maty; Snapshot_0 wymaga akcji operatora.
*   Dodano test offline sekwencji rolling comparison dla układu `empty -> one_card -> two_cards`.

Weryfikacja:
*   `python test_snapshot_manager_rolling.py`
*   `python test_rolling_snapshot_offline.py`
*   `python test_card_detection_offline.py`

**Status:**
Zadanie TV-006 zaakceptowane i zakończone.

---

## Dopisek diagnostyczny do testów fizycznych

*   **Data dopisku:** 2026-06-07

Na czas testów fizycznych dodano ograniczony zapis diagnostyczny prób detekcji.

Zasada:
*   Operacyjny mechanizm snapshotów nadal przechowuje tylko:
    *   `snapshot_0.png`,
    *   `snapshot_previous.png`,
    *   `snapshot_current.png`.
*   Dodatkowa diagnostyka zapisuje osobne rekordy prób w:
    *   `output/sessions/current/detections/detection_###/`.
*   Każdy rekord zawiera:
    *   `previous.png` — referencja użyta do porównania,
    *   `current.png` — aktualny kandydat po stabilizacji,
    *   `mask.png` — maska różnicowa,
    *   `result.png` — obraz diagnostyczny z ramką, jeśli powstał,
    *   `metadata.json` — status próby i dane wykrytej karty.
*   `output/sessions/current/session.log` zawiera krótką linię tekstową dla każdej próby.
*   Retencja diagnostyczna jest ograniczona do ostatnich 20 prób, żeby nie zbierać niepotrzebnej historii bez końca.

---

## Wynik fizycznej weryfikacji

*   **Data testu:** 2026-06-07
*   **Kamera:** AnkerWork C310 Webcam, indeks DirectShow `4`
*   **Rozdzielczość:** 1920x1080
*   **Tryb testu:** `python test_card_detection_diff.py`

Przebieg:
*   Operator ręcznie zatwierdził pustą matę jako `Snapshot_0`.
*   `detection_001` porównał pusty stół z pierwszą kartą.
*   `detection_001/previous.png` zawiera pusty stół.
*   `detection_001/current.png` zawiera stół z pierwszą kartą.
*   `detection_001/mask.png` zawiera pojedynczy obszar odpowiadający pierwszej karcie.
*   Po sukcesie system wykonał `accept_current_as_previous()`.
*   `detection_002` porównał stół z pierwszą kartą ze stołem z dwiema kartami.
*   `detection_002/previous.png` zawiera już pierwszą zaakceptowaną kartę.
*   `detection_002/current.png` zawiera pierwszą i drugą kartę.
*   `detection_002/mask.png` zawiera pojedynczy obszar odpowiadający drugiej karcie.

Wniosek:
*   Rolling snapshot comparison działa poprawnie.
*   Druga detekcja nie porównuje aktualnej sceny do pustego stołu, tylko do ostatniego zaakceptowanego stanu.
*   Mechanizm `Snapshot_previous` jest aktualizowany dopiero po zaakceptowanej detekcji.
*   Dodatkowa próba `detection_003` miała status `no_roi`, co jest akceptowalne, ponieważ zawierała tylko drobne zmiany przy krawędziach/markerach, bez nowej karty.

Wykryty problem poza zakresem TV-006:
*   Przy `detection_002` maska różnicowa obejmuje właściwie drugą kartę, ale `CardRefinery` dopasował finalną zieloną ramkę tylko do górnej części karty.
*   Problem nie leży już w rolling comparison, tylko w sposobie rafinacji obrysu karty wewnątrz ROI.

Rekomendowane następne zadanie:
*   `TV-007-card-refinery-stabilization.md` — ustabilizować pełne dopasowanie ramki karty na podstawie ROI/maski różnicowej.

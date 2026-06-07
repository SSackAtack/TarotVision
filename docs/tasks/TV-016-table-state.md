# TV-016: TableState — stan techniczny kart na stole

Status: Zakończone

## 1. Cel zadania
Utworzenie modułu `TableState` przechowującego techniczny stan aktualnego rozkładu kart na stole w formacie JSON oraz integracja go z systemem detekcji i rozpoznawania. Pozwoli to na zgromadzenie wszystkich informacji o sesji w jednym spójnym pliku stanu.

## 2. Architektura i Przepływ
Po udanym rozpoznaniu (lub wykryciu rewersu) karta dopisywana jest do pliku `output/sessions/current/table_state.json`.

Przepływ danych:
```text
recognition result
↓
TableState
↓
output/sessions/current/table_state.json
```

## 3. Struktura Stanu Stołu (table_state.json)
Plik stanu zawiera metadane sesji, informacje o aktywnych taliach oraz listę kart i historię zdarzeń.

```json
{
  "schema_version": "table_state_v1",
  "session_id": "current",
  "created_at": "2026-06-07T15:20:00.000Z",
  "updated_at": "2026-06-07T15:25:12.000Z",
  "table": {
    "coordinate_system": "corrected_table_image",
    "image_width": 1920,
    "image_height": 1080
  },
  "active_decks": ["gilded"],
  "cards_count": 2,
  "cards": [],
  "history": []
}
```

## 4. Statusy kart
Dozwolone statusy to:
*   `detected` — wykryta geometrycznie, bez rozpoznania.
*   `recognized` — rozpoznana i zmapowana semantycznie.
*   `unrecognized` — matcher dopasował, ale brak pewności / brak mapowania.
*   `ambiguous` — różnica między kandydatami zbyt mała.
*   `deck_back` — wykryto rewers talii.
*   `rejected` — detekcja odrzucona przez operatora.

## 5. Zapis Pozycji
Zapisywane są współrzędne w pikselach oraz znormalizowane `center_norm` i `bbox_norm` względem rozdzielczości obrazu stołu.

## 6. Kryteria akceptacji
1. Istnieje moduł `src/tarotvision/state/table_state.py` z klasą `TableState`.
2. Stan zapisywany jest do `table_state.json`.
3. Każda karta otrzymuje unikalne `card_instance_id` (np. `card_001`) i rosnący `sequence_index`.
4. Wykryty rewers zapisywany jest ze statusem `deck_back`.
5. Zaimplementowano zabezpieczenie przed duplikatami (po `detection_id` oraz progowo po odległości środków).
6. Istnieją testy jednostkowe (`test_table_state.py`) i integracyjne (`test_table_state_from_recognition.py`).
7. Program `test_card_detection_diff.py` poprawnie integruje i zapisuje `TableState` podczas pracy.

## 7. Wyniki realizacji
Zaimplementowano moduł stanu stołu `TableState` dla projektu TarotVision:
- Stworzono klasę `TableState` i `TableCard` w `src/tarotvision/state/table_state.py`.
- Klasa automatycznie zarządza serializacją do formatu `table_state_v1` w pliku `output/sessions/current/table_state.json`.
- Zaimplementowano wyliczanie współrzędnych znormalizowanych `center_norm` i `bbox_norm` względem rozdzielczości obrazu.
- Zaimplementowano zabezpieczenie przed duplikatami (odrzucanie po identycznym `detection_id` oraz odrzucanie, gdy środek nowej karty znajduje się bliżej niż 30px od istniejącej karty).
- Zintegrowano proces zapisu `TableState` bezpośrednio z procesem detekcji w `test_card_detection_diff.py`.
- Napisano testy jednostkowe (`test_table_state.py`) i integracyjne (`test_table_state_from_recognition.py`) weryfikujące pełną funkcjonalność. Wszystkie testy regresyjne systemu przechodzą bez błędów.

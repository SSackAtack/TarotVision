# TV-015: Semantic Card Mapping + Deck Back Recognition

Status: Zakończone

## 1. Cel zadania
Utworzenie jawnego mapowania technicznych identyfikatorów skanów referencyjnych (np. `Gilded_73`) na rzeczywiste znaczenia kart tarota (np. `The Sun`) lub specjalne typy obrazu talii (np. rewers talii `Gilded_back`). Umożliwi to prezentację czytelnych semantycznych danych dla użytkownika.

## 2. Problem braku danych semantycznych
Dotychczasowy system po dopasowaniu karty zwracał jedynie techniczny identyfikator `best_reference_id` (np. `Gilded_73`) z wartością `recognized_card: null`. Wprowadzenie pliku mapowania `card_mapping.json` pozwala przypisać do technicznych identyfikatorów bogate metadane semantyczne (nazwa wyświetlana, arkana, numer, kolor, ranga).

## 3. Obsługa rewersu talii (Deck Back Recognition)
W skanach referencyjnych znajduje się rewers talii (np. `Gilded_back`). Rewers nie jest kartą w sensie semantycznym, dlatego wprowadzamy dla niego specjalny typ `entry_type: "deck_back"`.
*   Rewers jest specjalnym obrazem referencyjnym.
*   Nie jest kartą rozkładu.
*   Może służyć do automatycznej identyfikacji talii w sesji wielotalijnej.
*   Może pomóc wykryć błąd (np. karta położona na stole rewersem do góry).

## 4. Format Pliku card_mapping.json
Plik mapowania znajduje się w folderze danej talii `assets/decks/{deck_id}/card_mapping.json`.
Zawiera listę wpisów, gdzie każdy wpis posiada metadane oraz pole `needs_human_review: true`. Pozwala to na wstępne wygenerowanie mapowania i jego późniejszą ręczną weryfikację przez operatora.

Dozwolone wartości pól w mapowaniu:
*   `entry_type`: `tarot_card`, `deck_back`, `extra_card`, `unknown`
*   `arcana`: `major`, `minor`, `extra`, `unknown`
*   `suit`: `wands`, `cups`, `swords`, `pentacles`, `null`, `unknown`
*   `rank`: `ace`, `two` ... `ten`, `page`, `knight`, `queen`, `king`, `null`, `unknown`
*   `mapping_confidence`: `high`, `medium`, `low`, `unknown`

## 5. Walidacja mapowania
Skrypt `validate_card_mapping.py` odpowiada za weryfikację poprawności pliku mapowania:
*   Sprawdza istnienie i poprawność formatu JSON.
*   Waliduje dozwolone wartości dla pól typu enum.
*   Wyszukuje duplikaty `reference_id`.
*   Sprawdza czy zdefiniowane `reference_id` faktycznie istnieją w indeksie/skanach referencyjnych.
*   Dopuszcza mapowania częściowe.

## 6. Kryteria akceptacji
1. Istnieje plik `assets/decks/gilded/card_mapping.json` (wersjonowany w Git). [Zrobione]
2. Plik mapowania uwzględnia rewers talii z oznaczonym `entry_type: "deck_back"`. [Zrobione]
3. Każdy rekord posiada pole `needs_human_review: true`. [Zrobione]
4. Istnieje moduł `src/tarotvision/recognition/card_mapping.py` z loaderem i funkcją wzbogacania wyników. [Zrobione]
5. Wyniki dopasowania otrzymują status `mapping_status`. [Zrobione]
6. Istnieje skrypt walidacji `validate_card_mapping.py` i testy `test_card_mapping.py`. [Zrobione]
7. `test_card_image_recognition.py` poprawnie wypisuje informacje o dopasowaniu semantycznym na konsoli. [Zrobione]
8. Wszystkie testy regresyjne przechodzą bez błędów. [Zrobione]

## 7. Wyniki realizacji
Zaimplementowano mapowanie semantyczne dla talii `gilded`.
- Stworzono plik `assets/decks/gilded/card_mapping.json` obejmujący 79 rekordów. 9 kart oraz rewers zostały zidentyfikowane wizualnie i w pełni zdefiniowane, pozostałe 69 kart oznaczono jako `unknown` z confidence `unknown`. Wszystkie rekordy mają flagę `needs_human_review: true`.
- Stworzono `CardMappingLoader` wczytujący plik mapowania i `enrich_recognition_with_card_mapping`, które dekoruje wyniki dopasowania o metadane karty/rewersu oraz status mapowania (`mapped`, `deck_back`, `unmapped_reference_id`, `missing_mapping`).
- Zaimplementowano CLI `validate_card_mapping.py`, który weryfikuje strukturę JSON, unikalność identyfikatorów, obecność wymaganych pól oraz dozwolone wartości dla enumów. Walidacja talii `gilded` przebiegła pomyślnie.
- Zintegrowano proces dekorowania z głównym skryptem `test_card_image_recognition.py`. Wypisuje on teraz czytelne polskie nazwy kart (np. *Karta: The Sun*, *Karta: The Magician*), a także prawidłowo raportuje rewersy.
- Uruchomiono i zaliczono unit testy (`test_card_mapping.py`) oraz regresyjne testy całego systemu.


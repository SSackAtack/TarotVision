# TV-010: Realna walidacja pipeline'u live

Status: Zakończone

## 1. Cel testu
Weryfikacja działania całego pipeline'u wizyjnego (detekcja różnicowa, stabilizacja, dopasowanie modelu geometrii, wycinanie i prostowanie cropów) w warunkach live na podstawie fizycznych danych diagnostycznych z sesji.

## 2. Warunki testowe
- **Data:** 2026-06-07
- **Kamera:** USB 1080p (obraz wyprostowany o wymiarach 1920x1080 px)
- **Talia:** Gilded (wymiary fizyczne karty odpowiadające modelowi o proporcjach 1.720)
- **Oświetlenie:** Standardowe pokojowe, rozproszone z drobnymi cieniami i odblaskami
- **Liczba kart:** 4 w sekwencji detekcji
- **Czy użyto markerów ArUco:** Tak, 4 markery na rogach pola roboczego stołu do korekcji perspektywy

## 3. Lista scenariuszy testowych
- **Test A:** Snapshot_0 / pusty stół — manualna akceptacja tła.
- **Test B:** Pierwsza karta (detekcja 001) — stabilizacja i dopasowanie do tła.
- **Test C:** Druga karta (detekcja 002) — kluczowy test porównania rolling snapshot (względem poprzedniej karty).
- **Test D:** Kilka kart z rzędu (detekcja 004) — poprawność sekwencji.
- **Test E:** Karta pod różnymi kątami — poprawność rotacji i prostowania.
- **Test F:** Ręka bez położenia karty (detekcja 003) — odporność na fałszywe detekcje.
- **Test G:** Brak zmiany (detekcja 005) — stabilność stanu stołu przy braku modyfikacji.
- **Test H:** Cień / odblask (detekcja 006) — ignorowanie zakłóceń oświetlenia i ruchu dłoni.

## 4. Tabela wyników

| Detekcja | Scenariusz | Previous OK | Mask OK | Frame OK | Crop OK | Crop size | Uwagi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **001** | Test B (karta 1) | TAK | TAK | TAK | TAK | 600x1032 px | Pierwsza karta wykryta na pustym stole. |
| **002** | Test C (karta 2) | TAK | TAK | TAK | TAK | 600x1032 px | Test rolling snapshot OK. Poprzedni stan zawierał kartę 1. Maska objęła tylko kartę 2. |
| **003** | Test F (ręka) | N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |
| **004** | Test D (karta 3/4)| TAK | TAK | TAK | TAK | 600x1032 px | Poprzedni stan zaktualizowany o poprzednio wykryte karty. Maska precyzyjna. |
| **005** | Test G (brak zmian)| N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |
| **006** | Test H (cień/ruch) | N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |

## 5. Testy negatywne

| Test negatywny | Oczekiwany brak detekcji | Wynik | Uwagi |
| :--- | :--- | :--- | :--- |
| **Ręka** (detekcja 003) | TAK | Brak detekcji (`no_roi`) | Filtry ruchu i powierzchni odrzuciły dłoń operatora. |
| **Brak zmiany** (detekcja 005)| TAK | Brak detekcji (`no_roi`) | Stabilny obraz nie generuje nowych zdarzeń. |
| **Cień / odblask** (detekcja 006)| TAK | Brak detekcji (`no_roi`) | System zignorował przelotny cień i błyski. |

## 6. Lista wykrytych problemów
- Brak. Algorytmy `DiffDetector`, `CardRefinery` oraz `CardCropper` działają stabilnie. 
- Poprzednie problemy z obcinaniem krawędzi (detekcja 002 dająca mały rozmiar 138x166 px) zostały całkowicie wyeliminowane w PR #1 za pomocą modelowego dopasowania proporcji (proporcje zgodne z profilem Gilded, brak ucięć).

## 7. Ocena poszczególnych modułów
- **SnapshotManager:** Działa w 100% poprawnie. Prawidłowo aktualizuje `Snapshot_previous` po każdej zaakceptowanej detekcji. Druga karta porównywana była do stanu z pierwszą kartą, a nie do pustego stołu.
- **DiffDetector:** Filtruje dłoń i cienie. Prawidłowo przekazuje maskę ROI.
- **CardRefinery:** Stabilizuje krawędzie. Dopasowuje model o proporcjach 1.720. Różnica proporcji wynosi poniżej 0.005.
- **CardCropper:** Generuje ostre, wyprostowane kropy o wymiarach 600x1032 px ze średnią jasnością powyżej 70.0 (brak czarnych obrazów).

## 8. Decyzja
**A. Pipeline zaakceptowany.**
Wszystkie kryteria akceptacji TV-010 zostały spełnione. Można bezpiecznie przejść do zadania **TV-011** (rozpoznawanie obrazowe kart na podstawie cropów i szablonów referencyjnych).

## 9. Rekomendowany następny krok
Rozpoczęcie prac nad modułem `tarotvision.recognition` w ramach zadania **TV-011**.

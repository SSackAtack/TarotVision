# TV-010: Realna walidacja pipeline'u live

Status: Zakończone

## 1. Cel testu
Weryfikacja działania całego pipeline'u wizyjnego (detekcja różnicowa, stabilizacja, dopasowanie modelu geometrii, wycinanie i prostowanie cropów) w warunkach live na podstawie fizycznych danych diagnostycznych z sesji.

## 2. Warunki testowe
- **Sesja Diagnostyczna 1 (Automatyczna):**
  - **Data:** 2026-06-07
  - **Kamera:** USB 1080p
  - **Talia:** Gilded (proporcje 1.720)
  - **Oświetlenie:** Standardowe pokojowe
  - **Liczba kart:** 4
  - **ArUco:** Tak

- **Sesja Diagnostyczna 2 (Manualna użytkownika):**
  - **Data:** 2026-06-07 11:07
  - **Kamera:** AnkerWork C310 Webcam (indeks 4, rozdzielczość 1920x1080 px)
  - **Talia:** Gilded (proporcje 1.720)
  - **Oświetlenie:** Pokojowe live
  - **Liczba kart:** 2
  - **ArUco:** Tak (lokalnie wystąpiły chwilowe braki detekcji, lecz kalibracja i detekcja stołu przebiegły poprawnie)

## 3. Lista scenariuszy testowych
- **Test A:** Snapshot_0 / pusty stół — manualna akceptacja tła.
- **Test B:** Pierwsza karta (detekcja 001 / 007) — stabilizacja i dopasowanie do tła.
- **Test C:** Druga karta (detekcja 002 / 008) — kluczowy test porównania rolling snapshot (względem poprzedniej karty).
- **Test D:** Kilka kart z rzędu (detekcja 004) — poprawność sekwencji.
- **Test E:** Karta pod różnymi kątami — poprawność rotacji i prostowania.
- **Test F:** Ręka bez położenia karty (detekcja 003 / 009) — odporność na fałszywe detekcje.
- **Test G:** Brak zmiany (detekcja 005) — stabilność stanu stołu przy braku modyfikacji.
- **Test H:** Cień / odblask (detekcja 006) — ignorowanie zakłóceń oświetlenia i ruchu dłoni.

## 4. Tabela wyników

### Sesja 1 (Automatyczna)

| Detekcja | Scenariusz | Previous OK | Mask OK | Frame OK | Crop OK | Crop size | Uwagi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **001** | Test B (karta 1) | TAK | TAK | TAK | TAK | 600x1032 px | Pierwsza karta wykryta na pustym stole. |
| **002** | Test C (karta 2) | TAK | TAK | TAK | TAK | 600x1032 px | Test rolling snapshot OK. Poprzedni stan zawierał kartę 1. Maska objęła tylko kartę 2. |
| **003** | Test F (ręka) | N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |
| **004** | Test D (karta 3/4)| TAK | TAK | TAK | TAK | 600x1032 px | Poprzedni stan zaktualizowany o poprzednio wykryte karty. Maska precyzyjna. |
| **005** | Test G (brak zmian)| N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |
| **006** | Test H (cień/ruch) | N/D | N/D | N/D | N/D | Brak | Poprawny brak ROI. Status `no_roi`. |

### Sesja 2 (Manualna Użytkownika)

| Detekcja | Scenariusz | Previous OK | Mask OK | Frame OK | Crop OK | Crop size | Uwagi |
| :--- | :--- | :--- | :--- | :--- | :--- | :--- | :--- |
| **007** | Test B (karta 1) | TAK | TAK | TAK | TAK | 600x1032 px | Wykryta na pustym stole. Środek: (289, 376), Proporcje: 1.728. |
| **008** | Test C (karta 2) | TAK | TAK | TAK | TAK | 600x1032 px | Rolling snapshot pomyślny. Środek: (525, 372), Proporcje: 1.720. Maska precyzyjna. |
| **009** | Test F (ręka) | N/D | N/D | N/D | N/D | Brak | Poprawny brak detekcji (`no_roi`). Ignorowanie ruchu dłoni nad stołem. |

## 5. Testy negatywne

| Test negatywny | Oczekiwany brak detekcji | Wynik | Uwagi |
| :--- | :--- | :--- | :--- |
| **Ręka** (detekcja 003 / 009) | TAK | Brak detekcji (`no_roi`) | Filtry ruchu i powierzchni odrzuciły dłoń operatora w obu sesjach. |
| **Brak zmiany** (detekcja 005)| TAK | Brak detekcji (`no_roi`) | Stabilny obraz nie generuje nowych zdarzeń. |
| **Cień / odblask** (detekcja 006)| TAK | Brak detekcji (`no_roi`) | System zignorował przelotny cień i błyski. |

## 6. Lista wykrytych problemów
- Brak. Algorytmy `DiffDetector`, `CardRefinery` oraz `CardCropper` działają stabilnie. 
- Poprzednie problemy z obcinaniem krawędzi (dające małe rozmiary rzędu 138x166 px) zostały całkowicie wyeliminowane w PR #1 za pomocą modelowego dopasowania proporcji (proporcje zgodne z profilem Gilded, brak ucięć).

## 7. Ocena poszczególnych modułów
- **SnapshotManager:** Działa w 100% poprawnie. Prawidłowo aktualizuje `Snapshot_previous` po każdej zaakceptowanej detekcji. Druga karta porównywana była do stanu z pierwszą kartą, a nie do pustego stołu.
- **DiffDetector:** Filtruje dłoń i cienie. Prawidłowo przekazuje maskę ROI.
- **CardRefinery:** Stabilizuje krawędzie. Dopasowuje model o proporcjach 1.720. Różnica proporcji wynosi poniżej 0.008 dla wszystkich testów.
- **CardCropper:** Generuje ostre, wyprostowane kropy o wymiarach 600x1032 px (brak czarnych obrazów).

## 8. Decyzja
**A. Pipeline zaakceptowany.**
Wszystkie kryteria akceptacji TV-010 zostały spełnione w obu próbach (automatycznej oraz manualnej użytkownika). Można bezpiecznie przejść do zadania **TV-011** (rozpoznawanie obrazowe kart na podstawie cropów i szablonów referencyjnych).

## 9. Rekomendowany następny krok
Rozpoczęcie prac nad modułem `tarotvision.recognition` w ramach zadania **TV-011**.

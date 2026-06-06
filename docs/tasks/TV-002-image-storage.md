# Zadanie: TV-002

## ID zadania:
TV-002

## Nazwa zadania:
Utwórz moduł zapisu zdjęć testowych

## Cel:
Zbudowanie modułu odpowiedzialnego za zapisywanie przechwyconych z kamery klatek na dysku w zorganizowanej strukturze katalogów wyjściowych (z datą i czasem).

## Kontekst projektu:
Zadanie stanowi część warstwy TarotVision Core (moduł `storage`). Pozwala na archiwizację surowych klatek wideo z sesji do późniejszej analizy off-line.

## Zakres:
1. Utworzenie struktury katalogów `output/captures/` w projekcie.
2. Napisanie modułu obsługującego bezpieczny zapis obrazów na dysk (`cv2.imwrite`).
3. Generowanie nazw plików na podstawie znacznika czasu (timestamp), np. `capture_20260606_173000.png`.
4. Zarządzanie ścieżkami w sposób niezależny od systemu operacyjnego (użycie biblioteki `pathlib`).

## Poza zakresem:
* Pobieranie obrazu z kamery (wykorzystujemy moduł z TV-001).
* Przetwarzanie graficzne obrazów (zakres TV-003).

## Pliki do utworzenia lub zmiany:
* `src/tarotvision/storage/writer.py` (moduł zapisu)
* `test_image_storage.py` (skrypt testowy)

## Wymagania techniczne:
* Użycie biblioteki standardowej `pathlib`.
* Automatyczne tworzenie brakujących katalogów na dysku.

## Interfejs wejścia:
* Obiekt obrazu NumPy (klatka BGR).
* Opcjonalna nazwa pliku lub katalog docelowy.

## Interfejs wyjścia:
* Ścieżka (String lub Path) do zapisanego pliku na dysku lub status błędu (False/wyjątek).

## Kryteria akceptacji:
* Skrypt tworzy katalog `output/captures/` jeśli nie istnieje.
* Przekazany obraz jest zapisywany w formacie PNG lub JPG pod wygenerowaną, unikalną nazwą.
* Brak błędów zapisu (uprawnienia zapisu do folderu projektu).

## Test ręczny:
* Uruchom skrypt `test_image_storage.py`, który pobierze obraz z kamery (używając TV-001) i wywoła moduł zapisu.
* Sprawdź, czy w folderze `output/captures/` pojawił się nowy plik ze zdjęciem Twojego stołu.

## Uwagi integracyjne:
* Moduł ten będzie używany przez wszystkie skrypty testowe i procesy nagrywania w celu zapisywania klatek referencyjnych i diagnostycznych.

---

## Wynik testu
*   **Data testu:** 2026-06-06
*   **System:** Microsoft Windows (Build 22000)
*   **Ścieżka projektu:** `E:\Antigravity\Projekty\TarotVision`

Wynik:
*   Pomyślnie zintegrowano pobieranie obrazu z kamery (`CameraCapture`) i zapis na dysku (`ImageWriter`).
*   Zaimplementowano autodetekcję nazwy kamery przy użyciu `pygrabber`, co pozwoliło na automatyczne wykrycie fizycznej kamery `"AnkerWork C310 Webcam"` na indeksie `4`.
*   Utworzono automatycznie katalog `output/captures/`.
*   Skrypt testowy zapisał rzeczywisty plik obrazu PNG (o rozdzielczości **1920x1080**, rozmiar **2 773 494 bajty**) pod unikalną nazwą wygenerowaną na podstawie timestampu.
*   Zasoby systemowe zostały prawidłowo zwolnione.

**Status:**
Zadanie TV-002 zaakceptowane i zakończone.




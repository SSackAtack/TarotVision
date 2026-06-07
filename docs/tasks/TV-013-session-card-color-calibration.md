# TV-013: Session Card Color Calibration

Status: Zakończone

## 1. Cel zadania
Dodanie kalibracji barwnej (Session Card Color Calibration) w celu wyrównania różnic w jasności, kontraście i balansie kolorów pomiędzy klatkami przechwytywanymi z kamery live a referencyjnymi skanami talii kart tarota. Poprawi to skuteczność image matchingu (TV-011).

## 2. Problem różnicy obrazowej
Fizyczne karty w rozkładzie live wyglądają inaczej na obrazie z kamery niż na referencyjnych skanach wczytanych ze skanera płaskiego. Wpływają na to parametry sensora kamery, oświetlenie zewnętrzne, odbicia światła, a także cienie. ImageMatcher porównujący surowe klatki z kamery ze skanami ma przez to niższy wskaźnik dopasowania (confidence) i jest bardziej podatny na błędy.

## 3. Rozwiązanie (Workflow Operatora)
1. Preflight i kalibracja tła (Snapshot_0).
2. Uruchomienie kalibracji koloru: operator kładzie znaną kartę kalibracyjną (np. `Gilded_38`).
3. System wykrywa kartę, wycina crop 600x1032 px i porównuje go z referencyjnym skanem tej samej karty.
4. Obliczany jest sesyjny profil barwny LAB i zapisywany w `session_color_profile.json`.
5. Operator zdejmuje kartę kalibracyjną. System powraca do pustego stołu. Karta ta nie zmienia na stałe stanu stołu `Snapshot_previous`.
6. Podczas właściwej sesji każdy nowo wycięty crop przed matchingiem podlega korekcji barw przy użyciu obliczonego profilu.

## 4. Algorytm kalibracji koloru (LAB mean/std transfer)
Dla cropa z kamery ($C_{cam}$) i skanu referencyjnego ($C_{ref}$):
1. Resize obu obrazów do wymiaru 600x1032 px.
2. Konwersja przestrzeni barw BGR → LAB.
3. Wyznaczenie średnich ($\mu$) i odchyleń standardowych ($\sigma$) dla każdego kanału L, A, B niezależnie.
4. Zapis parametrów do profilu sesji.
5. Korekcja nowo wczytanego cropa z kamery:
   $$x_{corr} = (x_{cam} - \mu_{cam}) \cdot \frac{\sigma_{ref}}{\sigma_{cam} + \epsilon} + \mu_{ref}$$
6. Przycięcie wartości do przedziału `[0, 255]`.
7. Konwersja LAB → BGR.

## 5. Wyniki Realizacji i Weryfikacji Offline
Test weryfikacyjny `test_session_color_calibration.py` został pomyślnie uruchomiony. Zasymulowano zniekształcony obraz z kamery (przyciemnienie, zmiana kontrastu oraz przesunięcie balansu bieli na kanałach BGR) względem skanu `Gilded_38.png`.

### Wyniki wskaźników z testu:
- **MAE przed korekcją (BGR):** **25.12**
- **MAE po korekcji (BGR):** **3.88** (znaczące zmniejszenie błędu barwnego o ponad 84%)
- **Brightness Delta:** **25.58 px**
- **BGR Gains:** `[2.4127 (B), 1.7327 (G), 1.0687 (R)]`
- **Score przed korekcją (znormalizowany grayscale):** `0.9975`
- **Score po korekcji (znormalizowany grayscale):** `0.9858` (bardzo wysokie podobieństwo do wzorca)
- **Status jakości profilu:** **accepted**

Korekcja barwna LAB w pełni odtworzyła oryginalną kolorystykę, jasność oraz kontrast zniekształconego obrazu, sprowadzając średni błąd piksela (MAE) z poziomu 25.12 do 3.88.

Profil testowy oraz obrazy kalibracji zostały pomyślnie zapisane w katalogu `output/test/`.

## 6. Kryteria akceptacji
- [x] Istnieje konfiguracja `config/session_color_calibration.json`.
- [x] Istnieje moduł `SessionColorCalibrator` implementujący LAB mean/std transfer.
- [x] System oblicza profil różnicy i zapisuje `session_color_profile.json`.
- [x] Istnieje funkcja korekcji `apply_color_profile()`.
- [x] Test offline `test_session_color_calibration.py` przechodzi bez błędów.
- [x] Matcher opcjonalnie stosuje profil korekcji, jeśli istnieje. Brak profilu nie psuje jego dotychczasowego działania.
- [x] Skrypt live `test_session_color_calibration_live.py` poprawnie przeprowadza kalibrację z zapytaniem operatora i cofa stan stołu do pustego tła.
- [x] Dotychczasowe testy (TV-011 i TV-012) przechodzą bez błędów.

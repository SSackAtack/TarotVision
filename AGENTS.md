# AGENTS.md — Instrukcja pracy dla agentów AI w projekcie TarotVision

## 1. Cel pliku

Ten plik jest obowiązkowym punktem startowym dla każdego agenta AI pracującego nad projektem TarotVision.

Przed wykonaniem jakiegokolwiek zadania agent powinien zapoznać się z tym plikiem oraz wskazanymi dokumentami w katalogu docs/.

Projekt TarotVision jest rozwijany metodą VibeCodingu przez wielu agentów AI. Z tego powodu najważniejsze są: modularność, kontrola zakresu, czytelna struktura kodu oraz zgodność z dokumentacją projektu.

---

## 2. Dokumenty obowiązkowe do przeczytania

Przed rozpoczęciem pracy agent powinien przeczytać:

*   [docs/01_wizja_biznesowa.md](file:///e:/Antigravity/Projekty/TarotVision/docs/01_wizja_biznesowa.md)
*   [docs/02_strategia_techniczna.md](file:///e:/Antigravity/Projekty/TarotVision/docs/02_strategia_techniczna.md)
*   [docs/03_metoda_pracy_i_architektura_modularna.md](file:///e:/Antigravity/Projekty/TarotVision/docs/03_metoda_pracy_i_architektura_modularna.md)

Jeżeli agent realizuje konkretne zadanie z katalogu docs/tasks/, musi dodatkowo przeczytać odpowiedni plik zadania, np.:

*   [docs/tasks/TV-001-camera-capture.md](file:///e:/Antigravity/Projekty/TarotVision/docs/tasks/TV-001-camera-capture.md)

---

## 3. Główna zasada projektu

TarotVision nie może być budowany jako monolit.

Każdy moduł powinien mieć jedną główną odpowiedzialność i powinien być możliwy do testowania niezależnie od reszty systemu.

Nie należy mieszać w jednym pliku:
*   obsługi kamery,
*   detekcji kart,
*   rozpoznawania kart,
*   zapisu plików,
*   overlay,
*   logiki portalu,
*   streamingu,
*   montażu wideo.

---

## 4. Zakaz samowolnego rozszerzania zakresu

Agent nie powinien dodawać funkcji, które nie są opisane w aktualnym zadaniu.

Jeżeli zadanie dotyczy pobierania obrazu z kamery, agent nie powinien dodawać:
*   rozpoznawania kart,
*   overlay,
*   streamingu,
*   WebRTC,
*   portalu,
*   bazy danych,
*   automatycznego montażu.

Każde zadanie ma być wykonane dokładnie w określonym zakresie.

---

## 5. Metoda pracy

Każde zadanie powinno być realizowane według schematu:
1.  Przeczytaj `AGENTS.md`.
2.  Przeczytaj dokumenty główne w `docs/`.
3.  Przeczytaj konkretny plik zadania w `docs/tasks/`.
4.  Zidentyfikuj zakres i ograniczenia zadania.
5.  Utwórz lub zmień wyłącznie pliki wskazane w zadaniu.
6.  Zachowaj modularność.
7.  Dodaj prosty sposób testowania modułu.
8.  Na końcu opisz:
    *   co zostało zrobione,
    *   jakie pliki zmieniono,
    *   jak przetestować wynik,
    *   czego celowo nie ruszano.

---

## 6. Preferowana struktura projektu

Docelowa struktura projektu powinna być zgodna z dokumentacją:

```text
TarotVision/
├── README.md
├── AGENTS.md
├── docs/
│   ├── 01_wizja_biznesowa.md
│   ├── 02_strategia_techniczna.md
│   ├── 03_metoda_pracy_i_architektura_modularna.md
│   └── tasks/
│       ├── TV-000-template-task.md
│       ├── TV-001-camera-capture.md
│       ├── TV-002-image-storage.md
│       └── TV-003-card-rectangle-detection.md
├── src/
│   └── tarotvision/
│       ├── camera/
│       ├── vision/
│       ├── recognition/
│       ├── overlay/
│       ├── storage/
│       ├── config/
│       └── utils/
├── tests/
├── assets/
│   ├── card_templates/
│   └── sample_images/
├── output/
│   ├── captures/
│   ├── processed/
│   └── sessions/
├── requirements.txt
└── .gitignore
```

Na wczesnym etapie projektu nie należy tworzyć pustych katalogów bez potrzeby. Strukturę kodu należy rozwijać stopniowo, zgodnie z aktualnymi zadaniami.

---

## 7. Standard nazewnictwa zadań

Zadania dla agentów powinny mieć numerację:
*   TV-001
*   TV-002
*   TV-003

Pliki zadań powinny znajdować się w:
*   `docs/tasks/`

Przykład:
*   [docs/tasks/TV-001-camera-capture.md](file:///e:/Antigravity/Projekty/TarotVision/docs/tasks/TV-001-camera-capture.md)

---

## 8. Format odpowiedzi agenta po wykonaniu zadania

Po wykonaniu zadania agent powinien zwrócić raport w formacie:

```text
Wykonane:
- ...

Zmienione pliki:
- ...

Jak przetestować:
- ...

Poza zakresem — nie ruszano:
- ...

Uwagi:
- ...
```

---

## 9. Priorytety techniczne projektu

Priorytety są następujące:
1.  Stabilny rdzeń techniczny.
2.  Modularna struktura.
3.  Czytelne interfejsy między modułami.
4.  Proste testowanie.
5.  Dopiero później efekty wizualne, overlay, Studio i Portal.

Pierwszy główny cel techniczny:
> Wykryć prawdziwą kartę tarota na obrazie z kamery lub zdjęcia, określić jej pozycję i zapisać wynik w prostym formacie danych.

---

## 10. Czego nie robić bez osobnego zadania

Bez osobnego, wyraźnego zadania agent nie powinien tworzyć ani modyfikować:
*   portalu klienta,
*   systemu płatności,
*   WebRTC,
*   streamingu RTMP,
*   aplikacji Electron,
*   automatycznego montażu wideo,
*   dużej bazy danych,
*   systemu logowania użytkowników,
*   interpretacji znaczenia kart przez AI.

TarotVision ma wspierać wizualną prezentację prawdziwego czytania tarota, a nie zastępować osobę wykonującą czytanie.

---

## 11. Zasada końcowa

Jeżeli agent ma wątpliwość, powinien wybrać rozwiązanie:
*   prostsze,
*   bardziej modułowe,
*   łatwiejsze do przetestowania,
*   zgodne z aktualnym zadaniem,
*   bez rozszerzania zakresu projektu.

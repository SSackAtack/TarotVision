# TarotVision — Metoda Pracy i Zasady Architektury Modularnej

## 1. Cel dokumentu

Ten dokument określa sposób pracy nad projektem TarotVision oraz podstawowe zasady projektowania architektury systemu.

TarotVision ma być rozwijany jako projekt modułowy, skalowalny i możliwy do budowania etapami. Każdy element systemu powinien być zaprojektowany tak, aby można go było rozwijać, testować, wymieniać lub usuwać bez destabilizowania całej aplikacji.

Dokument nie opisuje szczegółowej implementacji konkretnych funkcji. Jego celem jest ustalenie zasad, według których będą przygotowywane zadania, moduły, dokumentacja oraz struktura kodu.

---

## 2. Podstawowe założenie projektowe

TarotVision nie będzie tworzony jako jedna monolityczna aplikacja.

Projekt ma być budowany jako zestaw niezależnych modułów, które komunikują się ze sobą przez jasno określone wejścia i wyjścia.

Główna zasada:

> Jeden moduł powinien mieć jedną główną odpowiedzialność.

Przykład:

Moduł kamery odpowiada wyłącznie za obsługę obrazu z kamery. Nie powinien jednocześnie rozpoznawać kart, generować overlay, obsługiwać portalu, zapisywać sesji ani wykonywać montażu wideo.

---

## 3. Metoda pracy: VibeCoding + agenci AI

Projekt TarotVision będzie rozwijany metodą VibeCodingu przy użyciu wyspecjalizowanych agentów AI.

Do pracy mogą być wykorzystywani między innymi:

* Codex,
* Gemini,
* ChatGPT,
* Opus.

Każdy agent będzie otrzymywał konkretne, wydzielone zadania. Z tego powodu projekt musi być opisany w sposób jednoznaczny, modularny i odporny na chaos wynikający z równoległej pracy różnych narzędzi.

Nie zakładamy jednego konkretnego środowiska IDE jako centrum pracy. Kluczowe znaczenie mają:

* repozytorium projektu,
* struktura katalogów,
* dokumentacja,
* opis interfejsów między modułami,
* testy,
* kryteria akceptacji,
* spójne zasady nazewnictwa,
* kontrola zakresu zadań.

---

## 4. Zasada delegowania zadań agentom

Agentom AI nie należy zlecać zadań ogólnych typu:

> Zbuduj TarotVision.

Zadania powinny być małe, technicznie konkretne i możliwe do niezależnego wykonania.

Przykłady poprawnych zadań:

* TV-001: Utwórz moduł pobierania obrazu z kamery.
* TV-002: Utwórz moduł zapisu zdjęć testowych.
* TV-003: Utwórz moduł wykrywania prostokątów kart.
* TV-004: Utwórz moduł prostowania perspektywy pojedynczej karty.
* TV-005: Utwórz prototyp lokalnego overlay HTML odbierającego dane JSON.
* TV-006: Utwórz strukturę danych opisującą wykrytą kartę.
* TV-007: Utwórz moduł zapisu wyników analizy do pliku JSON.

Każde zadanie powinno mieć ograniczony zakres i jasno określony rezultat.

---

## 5. Standard opisu zadania dla agenta

Każde zadanie przekazywane agentowi powinno być opisane według jednego schematu.

### Struktura zadania

```text
ID zadania:
Nazwa zadania:
Cel:
Kontekst projektu:
Zakres:
Poza zakresem:
Pliki do utworzenia lub zmiany:
Wymagania techniczne:
Interfejs wejścia:
Interfejs wyjścia:
Kryteria akceptacji:
Test ręczny:
Uwagi integracyjne:
```

### Znaczenie poszczególnych sekcji

**ID zadania**
Unikalny numer zadania, np. `TV-001`.

**Nazwa zadania**
Krótka nazwa techniczna zadania.

**Cel**
Opisuje, co ma zostać osiągnięte.

**Kontekst projektu**
Wyjaśnia, gdzie dany moduł mieści się w architekturze TarotVision.

**Zakres**
Lista rzeczy, które agent ma wykonać.

**Poza zakresem**
Lista rzeczy, których agent nie powinien ruszać.

**Pliki do utworzenia lub zmiany**
Konkretne pliki, na których agent może pracować.

**Wymagania techniczne**
Biblioteki, standardy, założenia techniczne.

**Interfejs wejścia**
Jakie dane moduł przyjmuje.

**Interfejs wyjścia**
Jakie dane moduł zwraca.

**Kryteria akceptacji**
Warunki, które muszą być spełnione, aby uznać zadanie za wykonane.

**Test ręczny**
Prosty opis, jak człowiek może sprawdzić, czy moduł działa.

**Uwagi integracyjne**
Informacje potrzebne do połączenia modułu z resztą systemu.

---

## 6. Zasady architektury kodu

Kod TarotVision powinien być projektowany zgodnie z następującymi zasadami:

1. Jeden plik nie powinien zawierać całej logiki aplikacji.
2. Jeden moduł powinien mieć jedną główną odpowiedzialność.
3. Każdy moduł powinien dać się testować niezależnie.
4. Konfiguracja nie powinna być wpisywana na sztywno w wielu miejscach kodu.
5. Ścieżki do katalogów powinny być zarządzane centralnie.
6. Dane wejściowe i wyjściowe modułów powinny mieć jasny format.
7. Logika techniczna nie powinna być mieszana z logiką interfejsu użytkownika.
8. Moduły powinny komunikować się przez proste struktury danych.
9. Nie należy dodawać kolejnej funkcji, dopóki obecna nie działa stabilnie.
10. Najpierw budujemy stabilny rdzeń, potem interfejsy, efekty i automatyzacje.

---

## 7. Proponowana struktura repozytorium

Docelowa struktura projektu może wyglądać następująco:

```text
TarotVision/
│
├── docs/
│   ├── 01_wizja_biznesowa.md
│   ├── 02_strategia_techniczna.md
│   ├── 03_metoda_pracy_i_architektura_modularna.md
│   │
│   └── tasks/
│       ├── TV-001-camera-capture.md
│       ├── TV-002-image-storage.md
│       ├── TV-003-card-rectangle-detection.md
│       ├── TV-004-card-perspective-correction.md
│       └── TV-005-overlay-prototype.md
│
├── src/
│   └── tarotvision/
│       ├── camera/
│       ├── vision/
│       ├── recognition/
│       ├── overlay/
│       ├── storage/
│       ├── config/
│       └── utils/
│
├── tests/
│
├── assets/
│   ├── card_templates/
│   └── sample_images/
│
├── output/
│   ├── captures/
│   ├── processed/
│   └── sessions/
│
├── requirements.txt
├── README.md
└── .gitignore
```

---

## 8. Główne warstwy systemu

Projekt powinien być rozwijany w warstwach.

### 8.1. TarotVision Core

Rdzeń systemu odpowiedzialny za analizę obrazu.

Zakres:

* pobieranie obrazu,
* analiza klatek lub zdjęć,
* wykrywanie kart,
* korekcja perspektywy,
* rozpoznawanie kart,
* przygotowanie danych wynikowych.

Core powinien działać niezależnie od tego, czy dane zostaną później wysłane do overlay, aplikacji desktopowej, OBS, portalu czy systemu montażu wideo.

---

### 8.2. TarotVision Overlay

Warstwa wizualna odpowiedzialna za prezentację wyników.

Zakres:

* wyświetlanie ramek,
* wyświetlanie nazw kart,
* prezentacja miniatur kart,
* panel boczny z listą kart,
* animacje,
* przygotowanie widoku do przechwycenia przez OBS lub inne narzędzie produkcyjne.

---

### 8.3. TarotVision Studio

Docelowa aplikacja produkcyjna dla osoby prowadzącej sesję.

Zakres przyszły:

* zarządzanie kamerami,
* zarządzanie mikrofonem,
* podgląd sceny,
* nagrywanie,
* streaming,
* automatyczny montaż,
* eksport materiałów.

Ta warstwa nie jest priorytetem pierwszego MVP.

---

### 8.4. TarotVision Portal

Docelowa platforma dla klientów.

Zakres przyszły:

* rezerwacje,
* płatności,
* pokój sesji online,
* archiwum nagrań,
* interaktywna prezentacja kart dla klienta.

Ta warstwa nie jest częścią pierwszych prototypów technicznych.

---

## 9. Kolejność budowy systemu

Projekt powinien być rozwijany od najniższej warstwy technicznej do warstw produktowych.

### Etap 1 — Core: obraz i karta

Cel:

* uzyskać obraz z kamery lub pliku,
* wykryć kartę jako prostokąt,
* zapisać wynik analizy.

Zakres:

* kamera,
* zdjęcia testowe,
* wykrywanie konturów,
* zapis obrazów wynikowych.

---

### Etap 2 — Core: geometria i jakość

Cel:

* poprawnie wycinać kartę,
* prostować perspektywę,
* oceniać jakość obrazu.

Zakres:

* korekcja perspektywy,
* ocena ostrości,
* ocena jasności,
* wykrywanie zasłonięć.

---

### Etap 3 — Core: rozpoznawanie kart

Cel:

* rozpoznawać konkretne karty.

Zakres:

* baza wzorców,
* porównywanie obrazu karty ze wzorcami,
* rozpoznawanie pozycji normalnej i odwróconej.

---

### Etap 4 — Overlay lokalny

Cel:

* pokazać wykryte karty w czytelnej formie wizualnej.

Zakres:

* lokalna strona HTML,
* dane JSON,
* ramki,
* podpisy,
* miniatury,
* panel boczny.

---

### Etap 5 — Produkcja wideo

Cel:

* połączyć system z procesem nagrywania lub transmisji.

Zakres:

* OBS lub alternatywny mechanizm przechwytywania,
* sceny,
* overlay,
* zapis materiału.

---

### Etap 6 — Studio i Portal

Cel:

* rozbudować projekt do pełnego ekosystemu.

Zakres:

* aplikacja desktopowa,
* automatyczny montaż,
* portal klienta,
* sesje online,
* płatności,
* archiwum.

---

## 10. Czego nie robimy na początku

Na pierwszych etapach nie budujemy:

* pełnej aplikacji desktopowej,
* portalu klienta,
* płatności,
* WebRTC,
* automatycznego montażu,
* streamingu RTMP,
* skomplikowanego interfejsu graficznego,
* pełnej automatyzacji produkcji wideo.

Pierwszym celem jest udowodnienie, że system potrafi stabilnie zobaczyć i zlokalizować kartę na prawdziwym stole.

---

## 11. Format danych między modułami

Moduły powinny wymieniać dane w prostym, przewidywalnym formacie.

Przykładowa struktura wykrytej karty:

```json
{
  "id": "card_001",
  "name": null,
  "confidence": null,
  "position": {
    "x": 420,
    "y": 280
  },
  "size": {
    "width": 120,
    "height": 210
  },
  "angle": -4.5,
  "reversed": false,
  "corners": [
    [360, 180],
    [480, 175],
    [490, 390],
    [355, 395]
  ]
}
```

Na początku pola `name`, `confidence` i `reversed` mogą być puste lub ustawione jako `null`. Najpierw najważniejsze jest wykrycie pozycji i kształtu karty.

---

## 12. Zasada pracy na dokumentach

Dokumentacja projektu powinna być rozwijana razem z kodem.

Minimalny zestaw dokumentów:

```text
docs/
├── 01_wizja_biznesowa.md
├── 02_strategia_techniczna.md
├── 03_metoda_pracy_i_architektura_modularna.md
└── tasks/
    ├── TV-001-camera-capture.md
    ├── TV-002-image-storage.md
    └── TV-003-card-rectangle-detection.md
```

Każdy większy moduł powinien mieć własny opis zadania w katalogu `docs/tasks/`.

---

## 13. Zasada kontroli zakresu

Największym ryzykiem projektu jest zbyt szybkie dokładanie zbyt wielu funkcji.

Dlatego obowiązuje zasada:

> Nie rozszerzamy zakresu modułu, dopóki jego podstawowa funkcja nie działa stabilnie.

Przykład:

Zanim zaczniemy rozpoznawać nazwy kart, system musi stabilnie wykrywać prostokąty kart.

Zanim zaczniemy budować overlay, system musi zwracać przewidywalne dane o położeniu kart.

Zanim zaczniemy budować portal, lokalny przepływ obrazu i danych musi być sprawdzony.

---

## 14. Zasada integracji

Każdy moduł powinien być możliwy do uruchomienia niezależnie albo przez prosty skrypt testowy.

Przykład:

```text
test_camera_capture.py
test_card_detection.py
test_overlay_payload.py
```

Dzięki temu w razie problemów można sprawdzić konkretny moduł bez uruchamiania całego systemu.

---

## 15. Podsumowanie

TarotVision będzie rozwijany jako system modułowy, budowany etapami i zarządzany przez precyzyjnie opisane zadania dla agentów AI.

Najważniejsze zasady:

* najpierw rdzeń techniczny,
* potem overlay,
* dopiero później Studio i Portal,
* każdy moduł ma jedną odpowiedzialność,
* każdy agent otrzymuje konkretne zadanie,
* każdy moduł ma jasne wejście i wyjście,
* dokumentacja rozwija się razem z kodem,
* nie budujemy monolitu,
* nie rozszerzamy zakresu przed stabilizacją podstawowej funkcji.

Pierwszy realny cel techniczny projektu:

> Wykryć prawdziwą kartę tarota na obrazie z kamery lub zdjęcia, określić jej pozycję i zapisać wynik w prostym formacie danych.

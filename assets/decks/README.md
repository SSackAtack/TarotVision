# TarotVision — biblioteka talii

Ten katalog przechowuje profile i skany referencyjne talii używanych przez TarotVision.

Na tym etapie biblioteka talii służy przede wszystkim do pobrania geometrii kart:

- proporcji szerokości do wysokości,
- kanonicznego rozmiaru cropa,
- modelu pełnej ramki karty,
- danych potrzebnych do stabilizacji `CardRefinery`.

Rozpoznawanie nazw kart, znaczeń, figur, numerów i wariantów językowych jest poza zakresem aktualnego etapu.

## Struktura

```text
assets/decks/
└── gilded/
    ├── README.md
    ├── deck_profile.json
    └── reference_scans/
        └── .gitkeep
```

## Ważne założenie

Nazwa pliku skanu referencyjnego nie musi odpowiadać nazwie karty tarota. Na etapie geometrii plik jest traktowany wyłącznie jako obraz fizycznej karty danej talii.

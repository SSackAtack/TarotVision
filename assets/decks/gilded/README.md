# Talia: Gilded

Ten katalog przechowuje profil i skany referencyjne talii `Gilded` używanej w projekcie TarotVision.

## Cel na obecnym etapie

Na etapie TV-007 skany referencyjne są używane wyłącznie do pobrania geometrii fizycznej karty:

- szerokość obrazu skanu w pikselach,
- wysokość obrazu skanu w pikselach,
- proporcja wysokość/szerokość,
- kanoniczny rozmiar cropa,
- model ramki karty dla `CardRefinery`.

## Jak dodać pierwszy skan

Wgraj jeden skan prawdziwej karty do katalogu:

```text
assets/decks/gilded/reference_scans/
```

Przykładowa nazwa:

```text
scan_001.png
```

Nazwa pliku może być losowa. Na tym etapie nie mapujemy nazw plików na konkretne karty tarota.

## Poza zakresem

Na tym etapie nie wykonujemy:

- rozpoznawania nazw kart,
- OCR,
- klasyfikacji talii,
- mapowania plików na figury tarota,
- interpretacji znaczenia kart.

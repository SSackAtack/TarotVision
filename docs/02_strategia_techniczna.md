# Strategia Techniczna: TarotVision

*Uwaga: Ten dokument definiuje docelową architekturę techniczną systemu oraz określa ramy prototypowania (MVP).*

---

## 1. Architektura Docelowa (Warstwy Systemu)

System będzie składał się z trzech niezależnych komponentów:

### A. TarotVision Core (Wspólny Rdzeń)
*   **Detekcja Kart (AI/CV):** Moduł przetwarzania obrazu wykrywający obecność i położenie kart na stole.
*   **Baza Referencyjna Kart:**
    *   Nazwa karty.
    *   Grafika wzorcowa (obraz referencyjny).
    *   Wariant językowy.
    *   Miniatura do nakładek (overlay).
    *   Dane techniczne do rozpoznawania obrazu (np. deskryptory cech ORB/SIFT).
*   **Baza Opisów i Znaczeń:**
    *   Opcjonalny moduł tekstowy zawierający znaczenia kart.
    *   **Ważne:** Baza ta służy wyłącznie celom informacyjnym (np. wyświetlanie ściągawki wróżbicie lub opisu klientowi). System **nie wykonuje** automatycznej interpretacji rozkładu ani nie wróży samoczynnie.

### B. TarotVision Studio (Lokalna Aplikacja)
*   Wielokamerowe przechwytywanie wideo (twarz wróżbity + stół z kartami).
*   Składanie wideo w czasie rzeczywistym (nakładanie grafik z bazy referencyjnej).
*   Streaming RTMP na YouTube / serwer WebRTC.
*   Moduł automatycznego montażu (FFmpeg) łączący nagranie z intro/outro i muzyką.

### C. TarotVision Portal (System w Chmurze)
*   System rezerwacji terminów i płatności online.
*   Wirtualny Pokój Wróżb WebRTC (wideo o niskim opóźnieniu + dynamiczne overlay dla klienta).
*   Panel Klienta z historią i archiwum nagrań.

---

## 2. Podział na Etapy Wdrożenia

### A. MVP 1 (Obecny Krok)
Skupiamy się wyłącznie na technicznym potwierdzeniu możliwości detekcji kształtów kart na fizycznym stole w kontrolowanych warunkach sprzętowych. Szczegółowy zakres opisuje dokument `docs/tasks/TV-001-camera-capture.md` i kolejne zadania w folderze `docs/tasks/`.

### B. Czego teraz NIE robimy (Poza zakresem MVP 1):
*   Aplikacja Electron (brak GUI na tym etapie).
*   Portal klienta, płatności i rezerwacje.
*   Transmisje wideo na żywo (brak WebRTC, WebSockets, RTMP).
*   Automatyczny montaż wideo (brak integracji z FFmpeg).
*   Pełne rozpoznawanie tożsamości kart (nie dopasowujemy jeszcze grafik referencyjnych).
*   Baza opisów i znaczeń kart.

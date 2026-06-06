import cv2
import os
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SnapshotManager:
    """Klasa odpowiedzialna za zarządzanie klatkami kluczowymi (snapshotami) sesji z optymalizacją dyskową."""

    def __init__(self, base_dir: str = "output/sessions/current"):
        """
        Inicjalizacja menedżera snapshotów.

        :param base_dir: Katalog zapisu snapshotów.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Przechowywanie klatek w pamięci RAM
        self.snapshot_0 = None
        self.snapshot_last = None
        self.snapshot_current = None
        
        # Próba wczytania Snapshot_0 przy starcie
        self._load_existing_snapshot_0()

    def _load_existing_snapshot_0(self):
        """Wczytuje Snapshot_0 z dysku do pamięci RAM, jeśli plik istnieje."""
        path = self.base_dir / "snapshot_0.png"
        if path.exists():
            img = cv2.imread(str(path))
            if img is not None:
                self.snapshot_0 = img
                logger.info(f"Wczytano istniejący Snapshot_0 z dysku: {path}")

    def save_snapshot_0(self, frame) -> Path:
        """Zapisuje Snapshot_0 (pustą matę) na dysk i do RAM."""
        if frame is None:
            raise ValueError("Ramka nie może być pusta.")
            
        path = self.base_dir / "snapshot_0.png"
        cv2.imwrite(str(path), frame)
        self.snapshot_0 = frame.copy()
        logger.info(f"Zapisano referencyjny Snapshot_0 (pusta mata): {path}")
        return path

    def save_snapshot_current(self, frame) -> Path:
        """
        Zapisuje aktualny snapshot po ustaniu ruchu.
        Automatycznie przenosi poprzedni snapshot 'current' do 'last' (tylko w RAM).
        """
        if frame is None:
            raise ValueError("Ramka nie może być pusta.")
            
        # Przesunięcie w pamięci RAM
        if self.snapshot_current is not None:
            self.snapshot_last = self.snapshot_current.copy()
            
        self.snapshot_current = frame.copy()
        
        # Zapis na dysku (zawsze nadpisujemy ten sam plik, aby oszczędzać miejsce)
        path = self.base_dir / "snapshot_current.png"
        cv2.imwrite(str(path), frame)
        logger.info(f"Zapisano/Nadpisano snapshot_current.png na dysku: {path}")
        return path

    def has_snapshot_0(self) -> bool:
        """Sprawdza czy Snapshot_0 jest dostępny."""
        return self.snapshot_0 is not None or (self.base_dir / "snapshot_0.png").exists()

    def get_snapshot_0(self):
        """Zwraca referencyjny Snapshot_0."""
        if self.snapshot_0 is None:
            self._load_existing_snapshot_0()
        return self.snapshot_0

    def get_snapshot_last(self):
        """Zwraca poprzedni stan stołu (RAM)."""
        return self.snapshot_last

    def get_snapshot_current(self):
        """Zwraca aktualny stan stołu."""
        return self.snapshot_current

    def clear(self):
        """Czyści pamięć RAM (pliki na dysku pozostają)."""
        self.snapshot_0 = None
        self.snapshot_last = None
        self.snapshot_current = None
        self._load_existing_snapshot_0()

import cv2
import logging
from pathlib import Path

logger = logging.getLogger(__name__)

class SnapshotManager:
    """Zarządza kluczowymi snapshotami sesji bez przechowywania pełnej historii."""

    def __init__(self, base_dir: str = "output/sessions/current"):
        """
        Inicjalizacja menedżera snapshotów.

        :param base_dir: Katalog zapisu snapshotów.
        """
        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        
        # Przechowywanie jawnych ról snapshotów w pamięci RAM.
        self.snapshot_0 = None
        self.snapshot_previous = None
        self.snapshot_current = None
        
        self._load_existing_snapshots()

    def _load_image(self, filename: str):
        """Wczytuje obraz z katalogu sesji, jeśli istnieje."""
        path = self.base_dir / filename
        if not path.exists():
            return None

        img = cv2.imread(str(path))
        if img is None:
            logger.warning(f"Nie można wczytać snapshotu z dysku: {path}")
            return None

        logger.info(f"Wczytano snapshot z dysku: {path}")
        return img

    def _save_image(self, filename: str, frame) -> Path:
        """Zapisuje snapshot na dysk i zwraca ścieżkę."""
        path = self.base_dir / filename
        success = cv2.imwrite(str(path), frame)
        if not success:
            raise IOError(f"Błąd podczas zapisu snapshotu: {path}")
        return path

    def _load_existing_snapshots(self):
        """Wczytuje istniejące snapshoty z dysku do RAM."""
        self.snapshot_0 = self._load_image("snapshot_0.png")
        self.snapshot_previous = self._load_image("snapshot_previous.png")
        self.snapshot_current = self._load_image("snapshot_current.png")

        if self.snapshot_previous is None and self.snapshot_0 is not None:
            self.snapshot_previous = self.snapshot_0.copy()

    def save_snapshot_0(self, frame) -> Path:
        """Zapisuje Snapshot_0 i ustawia go jako ostatni zaakceptowany stan."""
        if frame is None:
            raise ValueError("Ramka nie może być pusta.")
            
        self.snapshot_0 = frame.copy()
        self.snapshot_previous = frame.copy()

        path = self._save_image("snapshot_0.png", self.snapshot_0)
        self._save_image("snapshot_previous.png", self.snapshot_previous)

        logger.info(f"Zapisano referencyjny Snapshot_0 (pusta mata): {path}")
        return path

    def save_snapshot_current(self, frame) -> Path:
        """
        Zapisuje aktualny snapshot po ustaniu ruchu.
        Nie aktualizuje snapshot_previous, dopóki detekcja nie zostanie zaakceptowana.
        """
        if frame is None:
            raise ValueError("Ramka nie może być pusta.")
            
        self.snapshot_current = frame.copy()
        
        path = self._save_image("snapshot_current.png", self.snapshot_current)
        logger.info(f"Zapisano/Nadpisano snapshot_current.png na dysku: {path}")
        return path

    def accept_current_as_previous(self) -> Path:
        """Akceptuje aktualny snapshot jako nowy ostatni zaakceptowany stan stołu."""
        if self.snapshot_current is None:
            raise ValueError("Brak snapshot_current do zaakceptowania.")

        self.snapshot_previous = self.snapshot_current.copy()
        path = self._save_image("snapshot_previous.png", self.snapshot_previous)
        logger.info(f"Zaakceptowano snapshot_current jako snapshot_previous: {path}")
        return path

    def has_snapshot_0(self) -> bool:
        """Sprawdza czy Snapshot_0 jest dostępny."""
        return self.snapshot_0 is not None or (self.base_dir / "snapshot_0.png").exists()

    def get_snapshot_0(self):
        """Zwraca referencyjny Snapshot_0."""
        if self.snapshot_0 is None:
            self.snapshot_0 = self._load_image("snapshot_0.png")
        return self.snapshot_0

    def get_snapshot_previous(self):
        """Zwraca ostatni zaakceptowany stan stołu."""
        if self.snapshot_previous is None:
            self.snapshot_previous = self._load_image("snapshot_previous.png")
            if self.snapshot_previous is None and self.get_snapshot_0() is not None:
                self.snapshot_previous = self.snapshot_0.copy()
        return self.snapshot_previous

    def get_snapshot_last(self):
        """Kompatybilny alias dla poprzedniego zaakceptowanego stanu stołu."""
        return self.get_snapshot_previous()

    def get_snapshot_current(self):
        """Zwraca aktualny stan stołu."""
        if self.snapshot_current is None:
            self.snapshot_current = self._load_image("snapshot_current.png")
        return self.snapshot_current

    def clear(self):
        """Czyści pamięć RAM (pliki na dysku pozostają)."""
        self.snapshot_0 = None
        self.snapshot_previous = None
        self.snapshot_current = None
        self._load_existing_snapshots()

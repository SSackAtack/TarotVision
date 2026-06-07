import json
import shutil
from datetime import datetime
from pathlib import Path

import cv2


class DetectionDiagnosticsRecorder:
    """Zapisuje ograniczony ślad diagnostyczny prób detekcji w sesji testowej."""

    def __init__(self, base_dir: str = "output/sessions/current/detections", max_records: int = 20):
        if max_records < 1:
            raise ValueError("max_records musi być większe od 0.")

        self.base_dir = Path(base_dir)
        self.base_dir.mkdir(parents=True, exist_ok=True)
        self.max_records = max_records
        self.session_log_path = self.base_dir.parent / "session.log"
        self.attempt_index = self._find_last_attempt_index()

    def _find_last_attempt_index(self) -> int:
        indexes = []
        for path in self.base_dir.glob("detection_*"):
            if not path.is_dir():
                continue
            try:
                indexes.append(int(path.name.split("_", 1)[1]))
            except (IndexError, ValueError):
                continue
        return max(indexes, default=0)

    def _write_image(self, path: Path, image):
        if image is None:
            return
        success = cv2.imwrite(str(path), image)
        if not success:
            raise IOError(f"Nie udało się zapisać pliku diagnostycznego: {path}")

    def _append_session_log(self, attempt: int, status: str, metadata_count: int):
        timestamp = datetime.now().isoformat(timespec="seconds")
        with open(self.session_log_path, "a", encoding="utf-8") as handle:
            handle.write(f"{timestamp} detection_{attempt:03d} status={status} cards={metadata_count}\n")

    def _prune_old_records(self):
        records = sorted(
            (path for path in self.base_dir.glob("detection_*") if path.is_dir()),
            key=lambda path: path.name,
        )
        while len(records) > self.max_records:
            shutil.rmtree(records.pop(0))

    def record_attempt(
        self,
        previous,
        current,
        mask,
        result_image=None,
        metadata=None,
        status: str = "unknown",
    ) -> Path:
        """Zapisuje jedną próbę detekcji i zwraca katalog rekordu."""
        self.attempt_index += 1
        record_dir = self.base_dir / f"detection_{self.attempt_index:03d}"
        record_dir.mkdir(parents=True, exist_ok=False)

        metadata = metadata or []

        self._write_image(record_dir / "previous.png", previous)
        self._write_image(record_dir / "current.png", current)
        self._write_image(record_dir / "mask.png", mask)
        self._write_image(record_dir / "result.png", result_image)

        payload = {
            "attempt": self.attempt_index,
            "timestamp": datetime.now().isoformat(timespec="seconds"),
            "status": status,
            "metadata": metadata,
        }
        with open(record_dir / "metadata.json", "w", encoding="utf-8") as handle:
            json.dump(payload, handle, indent=2, ensure_ascii=False)

        self._append_session_log(self.attempt_index, status, len(metadata))
        self._prune_old_records()
        return record_dir

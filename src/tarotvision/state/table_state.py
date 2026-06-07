import os
import json
import logging
from datetime import datetime, timezone
from pathlib import Path
from dataclasses import dataclass, asdict, field

logger = logging.getLogger(__name__)

@dataclass
class TableCard:
    card_instance_id: str
    detection_id: str
    sequence_index: int
    timestamp: str
    status: str
    deck_id: str | None = None
    reference_id: str | None = None
    recognized_card: dict | None = None
    recognized_special: dict | None = None
    mapping_status: str = "unmapped"
    confidence: float | None = None
    method: str | None = None
    best_rotation: int | None = None
    removed_at: str | None = None
    removal_detection_id: str | None = None
    removal_confidence: float | None = None
    position: dict = field(default_factory=lambda: {
        "bbox_px": [0, 0, 0, 0],
        "center_px": [0, 0],
        "corners_px": [],
        "center_norm": None,
        "bbox_norm": None
    })
    files: dict = field(default_factory=lambda: {
        "crop_path": None,
        "metadata_path": None,
        "mask_path": None,
        "result_path": None
    })
    diagnostics: dict = field(default_factory=lambda: {
        "score_breakdown": {},
        "geometry_ambiguous": False,
        "session_color_profile_used": False
    })

    def to_dict(self) -> dict:
        return asdict(self)

    @classmethod
    def from_dict(cls, data: dict) -> "TableCard":
        return cls(**data)


class TableState:
    def __init__(self, session_dir: str = "output/sessions/current"):
        self.session_dir = Path(session_dir)
        self.state_file = self.session_dir / "table_state.json"
        
        self.schema_version = "table_state_v1"
        self.session_id = self.session_dir.name
        self.created_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        self.updated_at = self.created_at
        
        self.table = {
            "coordinate_system": "corrected_table_image",
            "image_width": None,
            "image_height": None
        }
        self.active_decks = []
        self.cards: list[TableCard] = []
        self.history: list[dict] = []
        
        # Progowanie duplikatów geometrycznych
        self.duplicate_center_threshold_px = 30.0

    def load(self) -> None:
        """Wczytuje stan stołu z pliku table_state.json, jeśli istnieje."""
        if not self.state_file.exists():
            logger.info(f"Plik stanu {self.state_file} nie istnieje. Tworzenie nowej instancji stanu.")
            return
            
        try:
            with open(self.state_file, "r", encoding="utf-8") as f:
                data = json.load(f)
                
            self.schema_version = data.get("schema_version", "table_state_v1")
            self.session_id = data.get("session_id", self.session_id)
            self.created_at = data.get("created_at", self.created_at)
            self.updated_at = data.get("updated_at", self.updated_at)
            self.table = data.get("table", self.table)
            self.active_decks = data.get("active_decks", [])
            self.history = data.get("history", [])
            
            self.cards = []
            for c_data in data.get("cards", []):
                self.cards.append(TableCard.from_dict(c_data))
                
            logger.info(f"Pomyślnie załadowano stan stołu ({len(self.cards)} kart) z: {self.state_file}")
        except Exception as e:
            logger.error(f"Błąd podczas ładowania stanu stołu: {e}")

    def save(self) -> None:
        """Zapisuje bieżący stan stołu do pliku table_state.json."""
        try:
            self.session_dir.mkdir(parents=True, exist_ok=True)
            self.updated_at = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
            
            data = {
                "schema_version": self.schema_version,
                "session_id": self.session_id,
                "created_at": self.created_at,
                "updated_at": self.updated_at,
                "table": self.table,
                "active_decks": list(set(self.active_decks)),
                "cards_count": len(self.cards),
                "cards": [c.to_dict() for c in self.cards],
                "history": self.history
            }
            
            with open(self.state_file, "w", encoding="utf-8") as f:
                json.dump(data, f, indent=2, ensure_ascii=False)
                
            logger.info(f"Zapisano stan stołu w: {self.state_file}")
        except Exception as e:
            logger.error(f"Błąd podczas zapisu stanu stołu: {e}")

    def is_duplicate(self, detection_id: str, position: dict) -> bool:
        """
        Sprawdza, czy karta o podanym detection_id lub o bardzo zbliżonej pozycji
        geometrycznej już istnieje w stanie stołu.
        """
        # 1. Twarda ochrona po detection_id
        for card in self.cards:
            if card.detection_id == detection_id:
                logger.warning(f"Odrzucono próbę dodania karty - detection_id '{detection_id}' już istnieje w stanie.")
                return True
                
        # 2. Opcjonalna ochrona po pozycji geometrycznej
        new_center = position.get("center_px")
        if new_center and len(new_center) == 2:
            for card in self.cards:
                old_center = card.position.get("center_px")
                if old_center and len(old_center) == 2:
                    dist = ((new_center[0] - old_center[0])**2 + (new_center[1] - old_center[1])**2)**0.5
                    if dist < self.duplicate_center_threshold_px:
                        logger.warning(
                            f"Odrzucono próbę dodania karty - geometrycznie zbyt blisko "
                            f"istniejącej karty (dystans: {dist:.1f}px, próg: {self.duplicate_center_threshold_px}px)."
                        )
                        return True
        return False

    def add_card(self, card: TableCard) -> TableCard:
        """Dodaje bezpośrednio obiekt TableCard do stanu i zapisuje zdarzenie w historii."""
        self.cards.append(card)
        
        # Rejestracja zdarzenia w historii
        event = {
            "event_id": f"event_{len(self.history) + 1:03d}",
            "timestamp": card.timestamp,
            "event_type": "card_added",
            "card_instance_id": card.card_instance_id,
            "detection_id": card.detection_id,
            "reference_id": card.reference_id
        }
        self.history.append(event)
        
        if card.deck_id and card.deck_id not in self.active_decks:
            self.active_decks.append(card.deck_id)
            
        return card

    def add_card_from_recognition(
        self,
        detection_id: str,
        recognition_result: dict,
        position: dict,
        files: dict | None = None,
        diagnostics: dict | None = None,
    ) -> TableCard | None:
        """
        Tworzy obiekt TableCard na podstawie wyników rozpoznawania i pozycji geometrycznej,
        a następnie dodaje go do stanu stołu.
        """
        # Sprawdzenie duplikatów
        if self.is_duplicate(detection_id, position):
            return None
            
        # Generowanie card_instance_id i sequence_index
        seq_idx = len(self.cards) + 1
        instance_id = f"card_{seq_idx:03d}"
        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        
        # Wyznaczenie statusu
        mapping_status = recognition_result.get("mapping_status", "unmapped")
        best_ref_id = recognition_result.get("best_reference_id")
        
        if mapping_status == "mapped":
            status = "recognized"
        elif mapping_status == "deck_back":
            status = "deck_back"
        elif not best_ref_id:
            status = "unrecognized"
        else:
            status = "unrecognized"
            
        if recognition_result.get("ambiguous", False):
            status = "ambiguous"
            
        # Podział na recognized_card i recognized_special
        recognized_card = None
        recognized_special = None
        
        if status == "recognized":
            recognized_card = recognition_result.get("recognized_card")
        elif status == "deck_back":
            # Dane specjalne dla rewersu
            spec = recognition_result.get("recognized_special")
            if spec:
                recognized_special = spec
            else:
                recognized_special = {
                    "entry_type": "deck_back",
                    "display_name": "Gilded Back",
                    "is_deck_back": True
                }
                
        # Wyliczenie współrzędnych normalizowanych
        w_width = self.table.get("image_width")
        w_height = self.table.get("image_height")
        
        center_px = position.get("center_px")
        bbox_px = position.get("bbox_px") # [x, y, w, h]
        
        center_norm = None
        bbox_norm = None
        
        if w_width is not None and w_height is not None and w_width > 0 and w_height > 0:
            if center_px and len(center_px) == 2:
                center_norm = [round(center_px[0] / w_width, 4), round(center_px[1] / w_height, 4)]
            if bbox_px and len(bbox_px) == 4:
                bbox_norm = [
                    round(bbox_px[0] / w_width, 4),
                    round(bbox_px[1] / w_height, 4),
                    round(bbox_px[2] / w_width, 4),
                    round(bbox_px[3] / w_height, 4)
                ]
        else:
            logger.warning("Rozmiar stołu nie jest poprawnie ustawiony w TableState. Współrzędne znormalizowane nie zostaną wyliczone (center_norm=None, bbox_norm=None).")
                
        pos_data = {
            "bbox_px": bbox_px or [0, 0, 0, 0],
            "center_px": center_px or [0, 0],
            "corners_px": position.get("corners_px") or [],
            "center_norm": center_norm,
            "bbox_norm": bbox_norm
        }
        
        # Przygotowanie plików diagnostycznych
        file_data = {
            "crop_path": None,
            "metadata_path": None,
            "mask_path": None,
            "result_path": None
        }
        if files:
            file_data.update(files)
            
        # Przygotowanie diagnostyki matchera
        diag_data = {
            "score_breakdown": {},
            "geometry_ambiguous": False,
            "session_color_profile_used": False
        }
        if diagnostics:
            diag_data.update(diagnostics)
            
        # Obsługa score_breakdown, jeśli nie przekazano go wprost
        if not diag_data["score_breakdown"] and "candidates" in recognition_result:
            cands = recognition_result["candidates"]
            if cands and len(cands) > 0 and "score_breakdown" in cands[0]:
                diag_data["score_breakdown"] = cands[0]["score_breakdown"]
                
        # Stworzenie obiektu TableCard
        card = TableCard(
            card_instance_id=instance_id,
            detection_id=detection_id,
            sequence_index=seq_idx,
            timestamp=timestamp,
            status=status,
            deck_id=recognition_result.get("recognized_deck"),
            reference_id=best_ref_id,
            recognized_card=recognized_card,
            recognized_special=recognized_special,
            mapping_status=mapping_status,
            confidence=recognition_result.get("confidence"),
            method=recognition_result.get("method"),
            best_rotation=recognition_result.get("best_rotation"),
            position=pos_data,
            files=file_data,
            diagnostics=diag_data
        )
        
        self.add_card(card)
        return card

    def get_cards(self) -> list[dict]:
        """Zwraca listę wszystkich kart w stanie w postaci słowników."""
        return [c.to_dict() for c in self.cards]

    def get_card_by_instance_id(self, instance_id: str) -> TableCard | None:
        """Wyszukuje kartę na stole po jej card_instance_id."""
        for card in self.cards:
            if card.card_instance_id == instance_id:
                return card
        return None

    def mark_card_removed(
        self,
        card_instance_id: str,
        detection_id: str,
        confidence: float,
    ) -> TableCard | None:
        """
        Oznacza kartę jako usuniętą w stanie stołu, aktualizuje status i pola removal_*
        oraz dodaje zdarzenie usunięcia do historii.
        """
        card = self.get_card_by_instance_id(card_instance_id)
        if not card:
            logger.warning(f"Nie znaleziono karty {card_instance_id} do oznaczenia jako usunięta.")
            return None

        timestamp = datetime.now(timezone.utc).isoformat().replace("+00:00", "Z")
        card.status = "removed"
        card.removed_at = timestamp
        card.removal_detection_id = detection_id
        card.removal_confidence = confidence

        event = {
            "event_id": f"event_{len(self.history) + 1:03d}",
            "timestamp": timestamp,
            "event_type": "card_removed",
            "card_instance_id": card_instance_id,
            "detection_id": detection_id,
            "removal_confidence": confidence
        }
        self.history.append(event)
        logger.info(f"Oznaczono kartę {card_instance_id} jako usuniętą (detekcja: {detection_id}, pewność: {confidence:.2f}).")
        return card

    def get_active_cards(self) -> list[TableCard]:
        """Zwraca listę kart, których status nie jest 'removed'."""
        return [c for c in self.cards if c.status != "removed"]

    def set_table_size(self, width: int, height: int) -> None:
        """
        Ustawia rozmiar wyprostowanego stołu z walidacją parametrów.

        :param width: Szerokość obrazu (> 0).
        :param height: Wysokość obrazu (> 0).
        """
        if width is None or height is None:
            raise ValueError("Szerokość i wysokość stołu nie mogą być None.")
        if not isinstance(width, int) or isinstance(width, bool) or not isinstance(height, int) or isinstance(height, bool):
            raise TypeError("Szerokość i wysokość stołu muszą być typu int.")
        if width <= 0 or height <= 0:
            raise ValueError("Szerokość i wysokość stołu muszą być większe niż 0.")

        self.table["image_width"] = width
        self.table["image_height"] = height
        logger.info(f"Ustawiono rozmiar stołu w TableState: {width}x{height}")


    def to_dict(self) -> dict:
        """Zwraca pełen słownik reprezentujący stan stołu (analogiczny do pliku JSON)."""
        return {
            "schema_version": self.schema_version,
            "session_id": self.session_id,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "table": self.table,
            "active_decks": self.active_decks,
            "cards_count": len(self.cards),
            "cards": [c.to_dict() for c in self.cards],
            "history": self.history
        }

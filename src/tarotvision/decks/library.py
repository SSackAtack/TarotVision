import os
import json
import logging
from pathlib import Path
from tarotvision.decks.profile import DeckProfile

logger = logging.getLogger(__name__)

class DeckLibrary:
    """Klasa zarządzająca biblioteką profili talii w TarotVision."""

    def __init__(self, base_dir: str = "assets/decks"):
        """
        Inicjalizacja biblioteki talii.

        :param base_dir: Główny katalog, w którym znajdują się podkatalogi z profilami talii.
        """
        self.base_dir = Path(base_dir)
        self.profiles = {}

    def load_all_profiles(self) -> dict[str, DeckProfile]:
        """
        Wyszukuje i ładuje wszystkie profile talii znajdujące się w podkatalogach base_dir.

        :return: Słownik {deck_id: DeckProfile}
        """
        if not self.base_dir.exists():
            logger.warning(f"Katalog bazowy biblioteki talii nie istnieje: {self.base_dir}")
            return {}

        self.profiles = {}
        # Przeszukujemy rekurencyjnie podkatalogi w poszukiwaniu deck_profile.json
        for path in self.base_dir.glob("**/deck_profile.json"):
            try:
                profile = DeckProfile.load(str(path))
                self.profiles[profile.deck_id] = profile
                logger.info(f"Załadowano profil talii z biblioteki: {profile.deck_id} ({profile.deck_name})")
            except Exception as e:
                logger.error(f"Nie udało się załadować profilu z {path}: {e}")

        return self.profiles

    def load_active_profiles(self, active_ids: list[str] = None) -> list[DeckProfile]:
        """
        Zwraca profile talii aktywne w danej sesji.
        Jeśli active_ids jest podany, używa go. W przeciwnym razie wczytuje active_decks.json.

        :param active_ids: Opcjonalna lista identyfikatorów talii.
        :return: Lista aktywnych obiektów DeckProfile.
        """
        # Ładujemy najpierw wszystkie dostępne profile, aby upewnić się, że mamy pełną bazę
        self.load_all_profiles()

        if active_ids is None:
            # Próbujemy wczytać plik active_decks.json
            active_json_path = self.base_dir / "active_decks.json"
            if active_json_path.exists():
                try:
                    with open(active_json_path, "r", encoding="utf-8") as f:
                        config = json.load(f)
                    active_ids = config.get("active_decks", [])
                except Exception as e:
                    logger.error(f"Błąd odczytu active_decks.json: {e}")
                    active_ids = []
            else:
                active_ids = []

        # Jeśli lista aktywnych jest nadal pusta, stosujemy fallback na "gilded"
        if not active_ids:
            logger.warning("Brak zdefiniowanych aktywnych talii. Stosuję fallback na: gilded")
            active_ids = ["gilded"]

        active_profiles = []
        for d_id in active_ids:
            if d_id in self.profiles:
                active_profiles.append(self.profiles[d_id])
            else:
                # Jeśli profilu nie ma w słowniku (np. nie został znaleziony w assets/decks/),
                # spróbujmy wczytać go bezpośrednio ze znanej ścieżki
                fallback_path = self.base_dir / d_id / "deck_profile.json"
                if fallback_path.exists():
                    try:
                        profile = DeckProfile.load(str(fallback_path))
                        self.profiles[profile.deck_id] = profile
                        active_profiles.append(profile)
                    except Exception as e:
                        logger.error(f"Nie udało się załadować profilu fallback dla {d_id}: {e}")
                else:
                    logger.error(f"Talia o ID '{d_id}' nie została znaleziona w bibliotece ani w ścieżce fallback.")

        # W ostateczności, jeśli lista aktywnych profili jest pusta, stwórzmy awaryjny profil syntetyczny
        if not active_profiles:
            logger.error("Brak jakichkolwiek aktywnych profili. Tworzę syntetyczny profil awaryjny.")
            awaryjny_data = {
                "deck_id": "gilded",
                "deck_name": "Gilded (Awaryjny Fallback)",
                "geometry_source": "fallback_code",
                "reference_scan_dir": "assets/decks/gilded/reference_scans",
                "card_width_px": 700,
                "card_height_px": 1200,
                "aspect_ratio_height_to_width": 1.714
            }
            active_profiles.append(DeckProfile(awaryjny_data))

        return active_profiles

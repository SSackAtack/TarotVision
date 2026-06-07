import cv2
import numpy as np
import logging

logger = logging.getLogger(__name__)

class CardCropper:
    """Klasa odpowiedzialna za wycinanie i prostowanie perspektywy pojedynczej karty do jej wymiarów kanonicznych."""

    @staticmethod
    def order_points(pts) -> np.ndarray:
        """
        Porządkuje 4 punkty narożne w stałej kolejności:
        [top-left, top-right, bottom-right, bottom-left]

        :param pts: Lista lub NumPy array 4 punktów [x, y].
        :return: NumPy array (4x2) z uporządkowanymi współrzędnymi float32.
        """
        pts = np.array(pts, dtype=np.float32)
        rect = np.zeros((4, 2), dtype=np.float32)

        # Suma współrzędnych (x + y)
        # top-left ma najmniejszą sumę, bottom-right ma największą sumę
        s = pts.sum(axis=1)
        rect[0] = pts[np.argmin(s)]
        rect[2] = pts[np.argmax(s)]

        # Różnica współrzędnych (y - x)
        # top-right ma najmniejszą różnicę (duży x, mały y), bottom-left największą (mały x, duży y)
        diff = np.diff(pts, axis=1).flatten()
        rect[1] = pts[np.argmin(diff)]
        rect[3] = pts[np.argmax(diff)]

        return rect

    def crop_card(self, image, card_metadata: dict, deck_profile=None) -> dict | None:
        """
        Wycina pojedynczą kartę z wyprostowanego obrazu stołu, prostuje perspektywę i skaluje do wymiarów kanonicznych.

        :param image: Wyprostowany obraz stołu BGR.
        :param card_metadata: Słownik metadanych karty zwrócony przez CardRefinery (musi zawierać 'corners').
        :param deck_profile: Opcjonalny profil talii (DeckProfile) używany do odczytu wymiarów docelowych.
        :return: Słownik z wyciętym obrazem i metadanymi transformacji lub None.
        """
        if image is None or card_metadata is None:
            logger.warning("Brak obrazu stołu lub metadanych karty do wykonania cropa.")
            return None

        corners = card_metadata.get("corners")
        if not corners or len(corners) != 4:
            logger.error("Błąd cropowania: metadane karty nie zawierają poprawnych 4 narożników.")
            return None

        # Ustalenie wymiarów docelowych (kanonicznych)
        width = 600
        height = 1032
        profile_id = "unknown"

        if deck_profile is not None:
            profile_id = deck_profile.deck_id
            if deck_profile.canonical_width_px and deck_profile.canonical_height_px:
                width = deck_profile.canonical_width_px
                height = deck_profile.canonical_height_px
            elif deck_profile.card_width_px and deck_profile.card_height_px:
                width = deck_profile.card_width_px
                height = deck_profile.card_height_px
        else:
            logger.debug("Brak profilu talii w Cropperze. Używam domyślnych wymiarów kanonicznych 600x1032.")

        try:
            # 1. Uporządkowanie narożników źródłowych
            src_pts = self.order_points(corners)

            # 2. Punkty docelowe (kolejność: TL, TR, BR, BL)
            dst_pts = np.array([
                [0, 0],
                [width - 1, 0],
                [width - 1, height - 1],
                [0, height - 1]
            ], dtype=np.float32)

            # 3. Obliczenie macierzy rzutowania i transformacja
            M = cv2.getPerspectiveTransform(src_pts, dst_pts)
            warped = cv2.warpPerspective(image, M, (width, height))

            result = {
                "success": True,
                "crop_image": warped,
                "canonical_width_px": width,
                "canonical_height_px": height,
                "source_geometry_profile": profile_id,
                "transform_source": "card_refinery_corners",
                "corners_used": src_pts.tolist()
            }
            logger.info(f"Pomyślnie wycięto i wyprostowano kartę do wymiaru {width}x{height} px.")
            return result

        except Exception as e:
            logger.error(f"Wyjątek podczas transformacji perspektywicznej karty: {e}")
            return None

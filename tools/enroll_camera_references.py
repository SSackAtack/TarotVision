import sys
import os
import time
import json
import logging
import argparse
from pathlib import Path
from datetime import datetime
import cv2
import numpy as np

# Dodanie src i katalogu głównego do path
root_dir = Path(__file__).resolve().parent.parent
sys.path.append(str(root_dir))
sys.path.append(str(root_dir / "src"))

from tarotvision.recognition.card_mapping import CardMappingLoader
from tarotvision.recognition.index_loader import ReferenceIndexLoader
from tarotvision.recognition.indexed_matcher import IndexedImageMatcher
from tools.physical_recognition_calibration_wizard import (
    ExistingVisionCapturePipeline,
    crop_quality_check,
    assess_empty_baseline,
    build_session_dir
)

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")
logger = logging.getLogger("enroll_camera_references")

def load_camera_profile_name() -> str:
    settings_path = root_dir / "config" / "camera_settings.json"
    if settings_path.exists():
        try:
            with open(settings_path, "r", encoding="utf-8") as f:
                data = json.load(f)
                return data.get("camera_profile_name", "unknown")
        except Exception:
            pass
    return "unknown"

def save_enrollment_manifest(deck_id: str, results: dict, camera_profile: str, 
                             crop_source: str, resolution: list, plan_ids: list):
    manifest_path = root_dir / "assets" / "decks" / deck_id / "camera_references" / "enrollment_manifest.json"
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    
    missing = [ref_id for ref_id in plan_ids if ref_id not in results]
    
    manifest_data = {
        "deck_id": deck_id,
        "created_at": datetime.now().isoformat(),
        "camera_profile_name": camera_profile,
        "parameters": {
            "crop_source": crop_source,
            "resolution": resolution
        },
        "results": results,
        "missing_references": missing
    }
    
    try:
        with open(manifest_path, "w", encoding="utf-8") as f:
            json.dump(manifest_data, f, indent=2, ensure_ascii=False)
    except Exception as e:
        logger.error(f"Nie udało się zapisać manifestu enrollmentu: {e}")

def main():
    parser = argparse.ArgumentParser(description="Narzędzie do enrollmentu (przechwytywania z kamery) referencji kart talii.")
    parser.add_argument("--deck", default="gilded", help="Identyfikator talii (np. 'gilded').")
    parser.add_argument("--camera-index", type=int, default=0, help="Indeks kamery.")
    parser.add_argument("--samples", type=int, default=3, help="Liczba próbek pobieranych dla każdej karty w celu wyboru najlepszej.")
    parser.add_argument("--resume", action="store_true", help="Pomiń karty, które mają już przechwycone i zapisane referencje PNG.")
    
    args = parser.parse_args()
    
    deck_id = args.deck
    camera_index = args.camera_index
    num_samples = args.samples
    resume_mode = args.resume
    
    # 1. Załadowanie planu (lista plików z reference_scans)
    scans_dir = root_dir / "assets" / "decks" / deck_id / "reference_scans"
    if not scans_dir.exists():
        logger.error(f"Katalog referencyjny {scans_dir} nie istnieje.")
        sys.exit(1)
        
    valid_extensions = {".png", ".jpg", ".jpeg", ".bmp", ".tiff"}
    plan_ids = sorted([entry.stem for entry in scans_dir.iterdir() 
                       if entry.is_file() and entry.suffix.lower() in valid_extensions and not entry.name.startswith(".")])
    
    if not plan_ids:
        logger.error(f"Brak plików referencyjnych w {scans_dir}.")
        sys.exit(1)
        
    # 2. Załadowanie mapowania semantycznego
    mapping_loader = CardMappingLoader(base_decks_dir=str(root_dir / "assets" / "decks"))
    mapping = mapping_loader.load_mapping(deck_id)
    
    # 3. Załadowanie indeksu skanowego do kontroli tożsamości
    index_loader = ReferenceIndexLoader(base_decks_dir=str(root_dir / "assets" / "decks"))
    index = index_loader.load_index(deck_id)
    matcher = None
    if index:
        # Sprawdzamy, czy to indeks ze skanów (aby nie sprawdzać tożsamości indeksu kamerowego za pomocą samego siebie)
        if index.get("manifest", {}).get("source_domain", "scan") == "scan":
            matcher = IndexedImageMatcher(index)
            logger.info("Załadowano indeks skanowy do kontroli tożsamości kart.")
        else:
            logger.info("Załadowany indeks to indeks kamerowy. Kontrola tożsamości będzie pominięta.")
            
    # Wczytujemy profil kamery i tworzymy katalog sesji diagnostycznej
    camera_profile = load_camera_profile_name()
    session_dir = build_session_dir(root_dir / "output" / "enrollment_runs")
    logger.info(f"Rozpoczęto sesję enrollmentu. Diagnostyka w: {session_dir}")
    
    # Zczytanie istniejących wyników enrollmentu (jeśli plik istnieje)
    manifest_path = root_dir / "assets" / "decks" / deck_id / "camera_references" / "enrollment_manifest.json"
    enrollment_results = {}
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                old_manifest = json.load(f)
                enrollment_results = old_manifest.get("results", {})
        except Exception:
            pass

    # 4. Inicjalizacja kamery i pipeline
    pipeline = ExistingVisionCapturePipeline(camera_index=camera_index)
    logger.info("Otwieranie kamery...")
    if not pipeline.open():
        logger.error("Błąd krytyczny: Nie można otworzyć kamery.")
        sys.exit(1)
        
    try:
        # KROK A: Kalibracja tła
        print("\n=== KROK A: Kalibracja tła (pusta mata) ===")
        print("Usuń z obszaru stołu wszystkie karty. Pozostaw czysty stół.")
        input("Wciśnij Enter, aby przechwycić tło stołu...")
        
        empty_frame = pipeline._read_warped_frame(fresh=True)
        guard = assess_empty_baseline(empty_frame)
        if not guard["is_valid"]:
            print("\n[UWAGA] Tło stołu może nie być czyste:")
            for reason in guard["reasons"]:
                print(f" - {reason}")
            confirm = input("Czy na pewno chcesz kontynuować z tym tłem? (y/n): ")
            if confirm.strip().lower() != 'y':
                logger.info("Przerwano na życzenie operatora.")
                sys.exit(0)
                
        pipeline.empty_reference = empty_frame
        logger.info("Kalibracja tła zakończona pomyślnie.")
        
        warped_shape = [empty_frame.shape[1], empty_frame.shape[0]] # [width, height]
        resolution = [1920, 1080] # natywna
        
        # 5. Główna pętla enrollmentu po kartach z planu
        camera_refs_dir = root_dir / "assets" / "decks" / deck_id / "camera_references"
        camera_refs_dir.mkdir(parents=True, exist_ok=True)
        
        total_cards = len(plan_ids)
        for idx, ref_id in enumerate(plan_ids, start=1):
            best_crop_path = camera_refs_dir / f"{ref_id}.png"
            
            # Weryfikacja trybu resume
            if resume_mode and best_crop_path.exists() and ref_id in enrollment_results:
                logger.info(f"[{idx}/{total_cards}] Pomijam kartę {ref_id} (już istnieje).")
                continue
                
            card_entry = mapping_loader.get_card_by_reference_id(deck_id, ref_id) if mapping else None
            display_name = card_entry.get("display_name", ref_id) if card_entry else ref_id
            
            while True:
                print(f"\n========================================")
                print(f"[{idx}/{total_cards}] Karta: '{display_name}' ({ref_id})")
                print(f"========================================")
                print("Instrukcja: Połóż kartę PIONOWO, awersem, w orientacji 'góra karty od siebie'.")
                choice = input("Wciśnij Enter, aby przechwycić kartę (lub 'q' aby przerwać): ")
                if choice.strip().lower() == 'q':
                    logger.info("Przerwano enrollment na życzenie operatora.")
                    return
                    
                print(f"Pobieram {num_samples} próbek...")
                samples = []
                for s in range(num_samples):
                    try:
                        frame = pipeline._read_warped_frame(fresh=True)
                        roi_rect, diff_mask, _ = pipeline.diff_detector.detect_change_roi_with_debug(frame, empty_frame)
                        if roi_rect is None:
                            logger.warning(f"  Próbka {s+1}: Brak wykrytego ROI.")
                            samples.append(None)
                            time.sleep(0.1)
                            continue
                            
                        card_data = pipeline.refinery.refine_card(frame, roi_rect, diff_mask=diff_mask)
                        if card_data is None:
                            logger.warning(f"  Próbka {s+1}: Błąd precyzyjnego dopasowania.")
                            samples.append(None)
                            time.sleep(0.1)
                            continue
                            
                        # Wycięcie cropa z oryginalnej klatki (TV-018C)
                        crop_img = None
                        crop_source = "legacy_scaled_frame"
                        try:
                            crop_img = pipeline._crop_from_changed_frame(frame, empty_frame)
                            crop_source = getattr(pipeline, "_last_crop_source", "legacy_scaled_frame")
                        except Exception as e:
                            logger.warning(f"  Próbka {s+1}: Błąd crop_from_changed_frame ({e})")
                            
                        if crop_img is None:
                            # fallback do legacy
                            crop_res = pipeline.cropper.crop_card(frame, card_data)
                            if crop_res and crop_res.get("success"):
                                crop_img = crop_res["crop_image"]
                                crop_source = "legacy_scaled_frame"
                                
                        if crop_img is not None:
                            quality = crop_quality_check(crop_img)
                            samples.append({
                                "crop_image": crop_img,
                                "quality": quality,
                                "crop_source": crop_source
                            })
                            logger.info(f"  Próbka {s+1}: Ostrość={quality['metrics'].get('blur_score')}, Valid={quality['is_valid']}")
                        else:
                            samples.append(None)
                    except Exception as e:
                        logger.warning(f"  Próbka {s+1}: Wyjątek: {e}")
                        samples.append(None)
                    time.sleep(0.1)
                    
                valid_samples = [s for s in samples if s is not None]
                if not valid_samples:
                    print("\n[BŁĄD] Nie udało się przechwycić żadnej poprawnej próbki. Spróbuj ponownie.")
                    continue
                    
                # Wybór najlepszej próbki
                best_sample = max(valid_samples, key=lambda s: (s["quality"]["is_valid"], s["quality"]["metrics"].get("blur_score", 0.0)))
                
                # Kontrola tożsamości
                if matcher is not None:
                    match_res = matcher.match_card(best_sample["crop_image"], session_color_profile=None)
                    best_ref_id = match_res.get("best_reference_id")
                    if best_ref_id != ref_id:
                        print(f"\n[UWAGA] Kontrola tożsamości wykryła niezgodność!")
                        print(f"  Oczekiwano: {ref_id} ({display_name})")
                        print(f"  Wykryto:   {best_ref_id}")
                        confirm = input("  Czy na pewno chcesz zapisać tę próbkę? (y/n): ")
                        if confirm.strip().lower() != 'y':
                            print("  Odrzucono próbkę. Spróbuj ponownie położyć poprawną kartę.")
                            continue
                            
                # Zapis wybranej próbki
                cv2.imwrite(str(best_crop_path), best_sample["crop_image"])
                logger.info(f"Zapisano referencję: {best_crop_path}")
                
                # Zapis diagnostyki pozostałych próbek
                case_diagnostics_dir = session_dir / "diagnostics" / ref_id
                case_diagnostics_dir.mkdir(parents=True, exist_ok=True)
                for s_idx, s in enumerate(samples, start=1):
                    if s is None:
                        continue
                    cv2.imwrite(str(case_diagnostics_dir / f"sample_{s_idx}.png"), s["crop_image"])
                    with open(case_diagnostics_dir / f"sample_{s_idx}_quality.json", "w", encoding="utf-8") as f:
                        json.dump({
                            "sample_index": s_idx,
                            "is_best": (s is best_sample),
                            "quality": s["quality"],
                            "crop_source": s["crop_source"]
                        }, f, indent=2, ensure_ascii=False)
                
                # Zapis do manifestu
                enrollment_results[ref_id] = {
                    "reference_id": ref_id,
                    "display_name": display_name,
                    "timestamp": datetime.now().isoformat(),
                    "best_sample_metrics": best_sample["quality"]["metrics"],
                    "best_sample_reasons": best_sample["quality"]["reasons"],
                    "best_sample_is_valid": best_sample["quality"]["is_valid"],
                    "crop_source": best_sample["crop_source"]
                }
                
                save_enrollment_manifest(
                    deck_id=deck_id,
                    results=enrollment_results,
                    camera_profile=camera_profile,
                    crop_source=best_sample["crop_source"],
                    resolution=resolution,
                    plan_ids=plan_ids
                )
                break
                
        logger.info("Enrollment ukończony pomyślnie!")
        
    finally:
        pipeline.close()

if __name__ == "__main__":
    main()

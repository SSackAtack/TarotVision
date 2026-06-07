import sys
import os
import cv2
import numpy as np
import json
import time
from pathlib import Path

# Dodanie src do path
sys.path.append(os.path.join(os.path.dirname(__file__), "src"))

from tarotvision.camera.capture import CameraCapture
from tarotvision.camera.motion import MotionDetector
from tarotvision.storage.diagnostics import DetectionDiagnosticsRecorder
from tarotvision.storage.snapshots import SnapshotManager
from tarotvision.vision.perspective import TablePerspectiveCorrector
from tarotvision.vision.diff import DiffDetector
from tarotvision.vision.refinery import CardRefinery
from tarotvision.decks.profile import DeckProfile
from tarotvision.vision.cropper import CardCropper
from tarotvision.recognition.reference_loader import ReferenceLoader
from tarotvision.recognition.image_matcher import ImageMatcher
from tarotvision.recognition.index_loader import ReferenceIndexLoader
from tarotvision.recognition.indexed_matcher import IndexedImageMatcher
from tarotvision.recognition.card_mapping import enrich_recognition_with_card_mapping
from tarotvision.state.table_state import TableState

def run_diff_detection():
    print("--- TarotVision: Test Detekcji Kart za pomocą Różnicy Snapshotów ---")
    
    # 1. Inicjalizacja komponentów
    output_dir = Path("output/processed")
    output_dir.mkdir(parents=True, exist_ok=True)
    
    # Wczytanie profilu talii (Gilded)
    try:
        deck_profile = DeckProfile.load("assets/decks/gilded/deck_profile.json")
    except Exception as e:
        print(f"Ostrzeżenie: Nie udało się wczytać profilu talii: {e}")
        deck_profile = None
        
    corrector = TablePerspectiveCorrector()
    motion_detector = MotionDetector(threshold=1.2, stabilization_time=0.5)
    snapshot_manager = SnapshotManager(base_dir="output/sessions/current")
    diagnostics = DetectionDiagnosticsRecorder(base_dir="output/sessions/current/detections", max_records=20)
    diff_detector = DiffDetector(diff_threshold=25, min_area=10000, max_area=150000)
    refinery = CardRefinery(margin=20)
    cropper = CardCropper()
    
    # Inicjalizacja TableState
    table_state = TableState(session_dir="output/sessions/current")
    table_state.load()
    
    # Inicjalizacja matchera kart
    deck_id = "gilded"
    loader = ReferenceLoader()
    references = loader.load_references(deck_id)
    
    profile_path = Path("output/sessions/current/session_color_profile.json")
    profile = None
    if profile_path.exists():
        try:
            with open(profile_path, "r", encoding="utf-8") as f:
                profile = json.load(f)
        except Exception:
            pass
            
    index_loader = ReferenceIndexLoader()
    index = index_loader.load_index(deck_id)
    if index:
        matcher = IndexedImageMatcher(index)
        use_indexed = True
    else:
        matcher = ImageMatcher(session_color_profile=profile)
        use_indexed = False
    
    # Inicjalizacja kamery (CameraCapture automatycznie wykryje sprawny port nie-czarny)
    print("Inicjalizacja kamery...")
    with CameraCapture(camera_index=None, width=1920, height=1080, enable_preflight=True) as cam:
        if cam.cap is None or not cam.cap.isOpened():
            print("Błąd krytyczny: Nie udało się otworzyć żadnej sprawnej kamery.")
            sys.exit(1)
            
        print("\n=== Raport Camera Preflight ===")
        if cam.preflight_data:
            metrics = cam.preflight_data["metrics"]
            status = cam.preflight_data["status"]
            quality = cam.preflight_data["quality_status"]
            
            # Funkcja pomocnicza do oceny metryk na podstawie progów
            def eval_metric(val, min_val=None, max_val=None, is_higher_better=False):
                if is_higher_better:
                    if val < min_val * 0.6: return "ERROR"
                    if val < min_val: return "WARNING"
                    return "OK"
                else:
                    if max_val is not None and val > max_val * 2.5: return "ERROR"
                    if max_val is not None and val > max_val: return "WARNING"
                    if min_val is not None and val < min_val * 0.8: return "ERROR"
                    if min_val is not None and val < min_val: return "WARNING"
                    return "OK"
            
            b_status = eval_metric(metrics.get("brightness_mean"), 50, 190)
            s_status = eval_metric(metrics.get("laplacian_variance"), 80, is_higher_better=True)
            o_status = eval_metric(metrics.get("overexposed_ratio"), max_val=0.02)
            u_status = eval_metric(metrics.get("underexposed_ratio"), max_val=0.05)
            st_status = eval_metric(metrics.get("frame_delta_mean"), max_val=3.0)
            
            print(f"- brightness: {b_status} ({metrics.get('brightness_mean')} px)")
            print(f"- sharpness: {s_status} ({metrics.get('laplacian_variance')})")
            print(f"- overexposure: {o_status} ({metrics.get('overexposed_ratio')*100:.2f}%)")
            print(f"- underexposure: {u_status} ({metrics.get('underexposed_ratio')*100:.2f}%)")
            print(f"- stability: {st_status} ({metrics.get('frame_delta_mean')} px)")
            print(f"- auto exposure lock: {status.get('auto_exposure', 'unknown')}")
            print(f"- autofocus lock: {status.get('auto_focus', 'unknown')}")
            print(f"- white balance lock: {status.get('auto_white_balance', 'unknown')}")
            print(f"Jakość ogólna: {quality.upper()}")
            
            if quality == "rejected":
                print("\n[OSTRZEŻENIE] Jakość obrazu jest zła! Popraw oświetlenie / ostrość / ustawienie kamery przed Snapshot_0.\n")
            elif quality == "warning":
                print("\n[OSTRZEŻENIE] Wykryto drobne odchylenia jakości obrazu w preflightcie.\n")
            else:
                print("\n[OK] Jakość obrazu w preflightcie spełnia wymagania.\n")
        else:
            print("Brak danych preflightu kamery.")
            
        print("=== Instrukcja obsługi ===")
        if snapshot_manager.has_snapshot_0():
            print("-> Wykryto zapisany Snapshot_0 (pusta mata) na dysku.")
            print("-> Wciśnij SPACJĘ w oknie wideo, aby zrobić NOWY Snapshot_0.")
            print("-> Wciśnij DOWOLNY INNY KLAWISZ (np. Enter), aby pominąć i użyć zapisanego.")
        else:
            print("-> Brak Snapshot_0. Uporządkuj stół (pusta mata).")
            print("-> Snapshot_0 musi zostać zatwierdzony ręcznie.")
            print("-> Gdy stół jest pusty i stabilny, wciśnij SPACJĘ.")
        print("-> Wciśnij ESC w oknie wideo, aby wyjść z programu.")
        print("==========================\n")
        
        has_snapshot_0 = snapshot_manager.has_snapshot_0()
        
        # Zmienne dla informacyjnego preflightu. Stabilność jest tylko podpowiedzią,
        # zapis Snapshot_0 zawsze wymaga świadomej akcji operatora.
        stable_start_time = None
        preflight_duration = 3.0 # Wymagany czas bezruchu dla autokalibracji
        
        # Pętla kalibracji / oczekiwania na Snapshot_0
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            # Prostujemy obraz na bieżąco
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            
            # Kopia do wyświetlania
            display_frame = frame.copy()
            
            if warped is not None:
                cv2.imshow("Wyprostowany Stol (Warped)", warped)
                cv2.putText(display_frame, "Stol wykryty poprawnie", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 255, 0), 2)
                
                # Informacyjna stabilizacja pustej maty (bez automatycznego zapisu).
                if not has_snapshot_0:
                    is_moving, _ = motion_detector.update(warped)
                    current_time = time.time()
                    
                    if is_moving:
                        # Ruch resetuje licznik stabilności
                        stable_start_time = None
                        cv2.putText(display_frame, "Auto-Preflight: Wykryto ruch...", (30, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 0, 255), 2)
                    else:
                        if stable_start_time is None:
                            stable_start_time = current_time
                        
                        elapsed = current_time - stable_start_time
                        progress = min(1.0, elapsed / preflight_duration)
                        cv2.putText(display_frame, f"Stabilnosc pustej maty: {progress*100:.0f}%", (30, 120),
                                    cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 165, 0), 2)
                                    
                        if elapsed >= preflight_duration:
                            cv2.putText(display_frame, "Stol stabilny - nacisnij SPACJE, aby zatwierdzic Snapshot_0", (30, 150),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (0, 255, 255), 2)
            else:
                cv2.putText(display_frame, "BLAD: Nie wykryto 4 markerow ArUco!", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.8, (0, 0, 255), 2)
                stable_start_time = None # Brak stołu resetuje preflight
                            
            cv2.putText(display_frame, "SPACJA: Zapisz Snapshot_0 | ESC: Wyjdz", (30, 80), 
                        cv2.FONT_HERSHEY_SIMPLEX, 0.6, (255, 255, 255), 2)
                        
            cv2.imshow("Podglad Live (Kamera)", display_frame)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27: # ESC
                print("Anulowano przez operatora.")
                cv2.destroyAllWindows()
                return
            elif key == 32: # SPACJA
                if warped is not None:
                    snapshot_manager.save_snapshot_0(warped)
                    has_snapshot_0 = True
                    print("-> ZAPISANO SNAPSHOT_0 (PUSTA MATA) RĘCZNIE i ustawiono Snapshot_previous. Przechodzę do detekcji.")
                    break
                else:
                    print("Nie można wykonać Snapshot_0 - brak widocznych 4 markerów ArUco na stole!")
            elif has_snapshot_0 and key != 255:
                # Każdy inny klawisz, jeśli mamy Snapshot_0 na dysku
                print("-> Używam istniejącego Snapshot_0 z dysku jako aktualnego Snapshot_previous.")
                break
                
        # Reset detektora ruchu po preflighcie, aby zacząć od świeżego stanu
        motion_detector.reset()
        
        # Główna pętla detekcji
        print("\nRozpoczynam automatyczną detekcję na podstawie różnic obrazów...")
        print("Połóż kartę na stole i zabierz rękę.")
        
        cv2.destroyWindow("Podglad Live (Kamera)")
        
        while True:
            success, frame = cam.get_frame()
            if not success or frame is None:
                continue
                
            warped, _ = corrector.get_warped_table(frame, crop_to_markers=True)
            if warped is None:
                cv2.imshow("Wyprostowany Stol (Warped)", frame)
                cv2.waitKey(1)
                continue
                
            # 2. Aktualizacja detektora ruchu
            is_moving, is_stabilized = motion_detector.update(warped)
            
            display_warped = warped.copy()
            
            # Wyświetlanie statusu ruchu
            if is_moving:
                cv2.putText(display_warped, "STATUS: RUCH NA STOLE...", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
            else:
                cv2.putText(display_warped, "STATUS: STABILNIE", (30, 40), 
                            cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 255, 0), 2)
            
            # 3. Jeśli ruch ustał -> Wykrycie karty!
            if is_stabilized:
                print("\nWykryto ustabilizowanie obrazu. Aktualizuję snapshot stołu...")
                snapshot_manager.save_snapshot_current(warped)
                snapshot_current = snapshot_manager.get_snapshot_current()
                
                # Pobranie ostatniego zaakceptowanego stanu jako referencji rolling comparison
                snapshot_previous = snapshot_manager.get_snapshot_previous()
                if snapshot_previous is None:
                    print("-> Błąd: Brak Snapshot_previous. Najpierw zatwierdź Snapshot_0.")
                    continue
                
                # Detekcja zmiany (ROI)
                roi_rect, debug_mask = diff_detector.detect_change_roi(snapshot_current, snapshot_previous)
                cv2.imwrite(str(output_dir / "debug_diff_mask.png"), debug_mask)
                
                if roi_rect is not None:
                    # Precyzyjne dopasowanie karty w ROI
                    card_data = refinery.refine_card(warped, roi_rect, diff_mask=debug_mask, deck_profile=deck_profile)
                    
                    if card_data is not None:
                        # Generowanie i zapis cropa karty
                        crops_dir = Path("output/processed/crops")
                        crops_dir.mkdir(parents=True, exist_ok=True)
                        crop_res = cropper.crop_card(warped, card_data, deck_profile)
                        
                        if crop_res and crop_res["success"]:
                            # Przygotowanie metadanych JSON
                            cards_metadata = [{
                                "id": "card_001",
                                "name": None,
                                "confidence": None,
                                "position": {
                                    "x": card_data["center"][0],
                                    "y": card_data["center"][1]
                                },
                                "size": {
                                    "width": card_data["size"][0] if card_data["size"][0] < card_data["size"][1] else card_data["size"][1],
                                    "height": card_data["size"][1] if card_data["size"][0] < card_data["size"][1] else card_data["size"][0]
                                },
                                "angle": round(card_data["angle"], 2),
                                "reversed": None,
                                "corners": card_data["corners"]
                            }]
                            
                            # Zapis metadanych JSON
                            with open(output_dir / "detected_cards.json", "w", encoding="utf-8") as f:
                                json.dump(cards_metadata, f, indent=2, ensure_ascii=False)
                                
                            # Narysowanie zielonego prostokąta
                            box = np.intp(card_data["corners"])
                            cv2.drawContours(display_warped, [box], -1, (0, 255, 0), 3)
                            cv2.circle(display_warped, card_data["center"], 7, (0, 0, 255), -1)
                            cv2.putText(display_warped, "card_001", (card_data["center"][0] - 25, card_data["center"][1] - 15),
                                        cv2.FONT_HERSHEY_SIMPLEX, 0.7, (0, 0, 255), 2)
                                        
                            # Zapisz obraz wynikowy
                            cv2.imwrite(str(output_dir / "table_detected_diff.png"), display_warped)
                            
                            record_dir = diagnostics.record_attempt(
                                previous=snapshot_previous,
                                current=snapshot_current,
                                mask=debug_mask,
                                result_image=display_warped,
                                metadata=cards_metadata,
                                status="accepted",
                            )
                            
                            crop_img = crop_res["crop_image"]
                            # Zapis centralny z indeksem próby
                            cv2.imwrite(str(crops_dir / f"card_crop_{diagnostics.attempt_index:03d}.png"), crop_img)
                            # Zapis lokalny w katalogu diagnostyki
                            cv2.imwrite(str(record_dir / "crop.png"), crop_img)
                            print(f"-> Zapisano crop karty w: {record_dir / 'crop.png'}")
                            
                            # Ustawienie rozmiaru stołu w TableState przed dodaniem karty
                            table_state.table["image_width"] = warped.shape[1]
                            table_state.table["image_height"] = warped.shape[0]
                            
                            # Rozpoznawanie karty
                            if use_indexed:
                                match_res = matcher.match_card(crop_img, session_color_profile=profile)
                            else:
                                match_res = matcher.match_card(crop_img, references, deck_id)
                                
                            match_res = enrich_recognition_with_card_mapping(match_res, deck_id)
                            
                            best_ref_id = match_res.get("best_reference_id")
                            mapping_status = match_res.get("mapping_status")
                            confidence = match_res.get("confidence", 0.0)
                            
                            if mapping_status == "mapped":
                                card_name = match_res["recognized_card"]["display_name"]
                                print(f"-> [Matcher] Rozpoznano kartę: {card_name} ({best_ref_id}), confidence: {confidence:.4f}")
                            elif mapping_status == "deck_back":
                                print(f"-> [Matcher] Rozpoznano rewers: Gilded Back ({best_ref_id}), confidence: {confidence:.4f}")
                            else:
                                print(f"-> [Matcher] Karta nierozpoznana / brak mapowania (best_ref_id: {best_ref_id})")
                                
                            # Przygotowanie danych pozycji dla TableState przy użyciu cv2.boundingRect
                            bx, by, bw, bh = cv2.boundingRect(np.intp(card_data["corners"]))
                            position_data = {
                                "bbox_px": [int(bx), int(by), int(bw), int(bh)],
                                "center_px": [int(card_data["center"][0]), int(card_data["center"][1])],
                                "corners_px": [[int(pt[0]), int(pt[1])] for pt in card_data["corners"]]
                            }
                            
                            file_paths = {
                                "crop_path": str(record_dir / "crop.png"),
                                "metadata_path": str(record_dir / "metadata.json"),
                                "mask_path": str(output_dir / "debug_diff_mask.png"),
                                "result_path": str(output_dir / "table_detected_diff.png")
                            }
                            
                            detection_id = f"detection_{diagnostics.attempt_index:03d}"
                            added_card = table_state.add_card_from_recognition(
                                detection_id=detection_id,
                                recognition_result=match_res,
                                position=position_data,
                                files=file_paths
                            )
                            
                            if added_card:
                                table_state.save()
                                if mapping_status == "mapped":
                                    print(f"[TableState] Dodano {added_card.card_instance_id}: {added_card.recognized_card['display_name']} / {added_card.reference_id}, confidence={added_card.confidence:.4f}")
                                elif mapping_status == "deck_back":
                                    print(f"[TableState] Dodano {added_card.card_instance_id}: deck_back / {added_card.reference_id}")
                                else:
                                    print(f"[TableState] Dodano {added_card.card_instance_id}: unrecognized / {added_card.reference_id}")
                                    
                            # Dopiero po udanym cropie, rozpoznaniu, dodaniu do TableState i table_state.save()
                            # akceptujemy aktualny stan stołu jako poprzedni
                            snapshot_manager.accept_current_as_previous()
                            print(f"-> Sukces! Zapisano obraz wynikowy w: {output_dir / 'table_detected_diff.png'}")
                            print(f"-> Zapisano JSON w: {output_dir / 'detected_cards.json'}")
                            
                        else:
                            # Crop się nie powiódł
                            diagnostics.record_attempt(
                                previous=snapshot_previous,
                                current=snapshot_current,
                                mask=debug_mask,
                                result_image=display_warped,
                                metadata=[],
                                status="crop_failed",
                            )
                            print("-> Błąd: Wycięcie cropa karty nie powiodło się (crop_failed).")
                            
                    else:
                        diagnostics.record_attempt(
                            previous=snapshot_previous,
                            current=snapshot_current,
                            mask=debug_mask,
                            result_image=display_warped,
                            metadata=[],
                            status="refinery_failed",
                        )
                        print("-> Błąd: Precyzyjne dopasowanie karty w ROI nie powiodło się.")
                else:
                    diagnostics.record_attempt(
                        previous=snapshot_previous,
                        current=snapshot_current,
                        mask=debug_mask,
                        result_image=display_warped,
                        metadata=[],
                        status="no_roi",
                    )
                    print("-> Błąd: Detektor różnicowy nie wykrył obszaru zmian.")
            
            # W oknie Warped wyświetlamy nakładki
            cv2.imshow("Wyprostowany Stol (Warped)", display_warped)
            
            key = cv2.waitKey(1) & 0xFF
            if key == 27: # ESC
                print("Zakończono test.")
                break
                
        cv2.destroyAllWindows()

if __name__ == "__main__":
    run_diff_detection()

import logging

logger = logging.getLogger(__name__)

def apply_recognition_decision(
    match_result: dict,
    min_recognition_score: float = 0.82,
    min_score_margin: float = 0.04,
) -> dict:
    """
    Stosuje formalną warstwę decyzyjną na wynikach rozpoznawania kart.
    
    :param match_result: Słownik wyniku z matchera zawierający klucz 'candidates'.
    :param min_recognition_score: Minimalny score dla uznania karty (domyślnie 0.82).
    :param min_score_margin: Minimalny margines między top1 a top2 (domyślnie 0.04).
    :return: Zaktualizowany słownik wyniku.
    """
    result = dict(match_result)
    candidates = result.get("candidates", [])
    
    top1_ref = None
    top1_score = 0.0
    top2_ref = None
    top2_score = 0.0
    
    if candidates and len(candidates) > 0:
        top1_ref = candidates[0].get("reference_id")
        top1_score = float(candidates[0].get("score", 0.0))
        if len(candidates) > 1:
            top2_ref = candidates[1].get("reference_id")
            top2_score = float(candidates[1].get("score", 0.0))
            
    score_margin = round(top1_score - top2_score, 4)
    
    if top1_score >= min_recognition_score:
        if score_margin >= min_score_margin:
            decision = "recognized"
            ambiguous = False
        else:
            decision = "ambiguous"
            ambiguous = True
    else:
        decision = "unrecognized"
        ambiguous = False
        
    result.update({
        "top1_reference_id": top1_ref,
        "top1_score": round(top1_score, 4),
        "top2_reference_id": top2_ref,
        "top2_score": round(top2_score, 4),
        "score_margin": score_margin,
        "recognition_decision": decision,
        "ambiguous": ambiguous
    })
    
    if candidates and len(candidates) > 0:
        result["decision_thresholds"] = {
            "min_recognition_score": min_recognition_score,
            "min_score_margin": min_score_margin
        }
        
    return result

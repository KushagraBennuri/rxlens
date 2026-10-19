"""matcher.py - check what the reader found against the medicine dataset.

Final confidence = LLM confidence x match score. Anything below the threshold is flagged.
"""
import re

try:
    from rapidfuzz import fuzz, process
    HAVE_RAPIDFUZZ = True
except ImportError:          # only so the code can be tested without installing; real runs use rapidfuzz
    import difflib
    HAVE_RAPIDFUZZ = False

DEFAULT_THRESHOLD = 0.6
# Words like "Tab" or "Syrup" are not part of the medicine name
FORM_WORDS = r"\b(tablets?|tabs?|capsules?|caps?|syrup|syp|injection|inj|ointment|cream|drops?|gel|suspension|susp)\b\.?"


def normalize(name):
    """'Tab. Dolo-650' -> 'dolo 650'."""
    n = str(name).lower()
    n = re.sub(FORM_WORDS, " ", n)
    n = re.sub(r"[^a-z0-9. ]", " ", n)
    return re.sub(r"\s+", " ", n).strip()


def build_index(names):
    """Pre-compute normalised names once (slow part), return (names, normalised_names)."""
    return names, [normalize(n) for n in names]


def match_name(raw_name, index, top_n=3):
    """Return up to top_n [(dataset_name, score 0-1)], best first."""
    names, norm_names = index
    query = normalize(raw_name)
    if not query or query == "unclear":
        return []
    if HAVE_RAPIDFUZZ:
        hits = process.extract(query, norm_names, scorer=fuzz.WRatio, limit=top_n * 4)
        pairs = [(names[i], score / 100.0) for _, score, i in hits]
    else:
        close = difflib.get_close_matches(query, norm_names, n=top_n * 4, cutoff=0.0)
        pairs = [(names[norm_names.index(c)], difflib.SequenceMatcher(None, query, c).ratio()) for c in close]
    unique, seen = [], set()
    for name, score in pairs:          # the dataset can contain the same name twice
        if name not in seen:
            seen.add(name)
            unique.append((name, round(score, 3)))
    return unique[:top_n]


def final_confidence(llm_confidence, match_score):
    """LLM confidence x match score. Missing LLM confidence counts as 0.5."""
    if llm_confidence is None:
        llm_confidence = 0.5
    return round(float(llm_confidence) * float(match_score), 3)


def is_flagged(confidence, threshold=DEFAULT_THRESHOLD):
    return confidence < threshold


def build_row(medicine, index, threshold=DEFAULT_THRESHOLD):
    """Take one medicine dict from the reader and add match info to it."""
    suggestions = match_name(medicine.get("name", ""), index)
    best_name, best_score = suggestions[0] if suggestions else ("", 0.0)
    conf = final_confidence(medicine.get("confidence"), best_score)
    return {**medicine, "suggestions": suggestions, "matched_name": best_name,
            "match_score": best_score, "final_conf": conf, "flagged": is_flagged(conf, threshold)}

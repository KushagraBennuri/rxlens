import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import matcher

INDEX = matcher.build_index(["Dolo 650 Tablet", "Crocin 500 Tablet", "Augmentin 625 Duo Tablet", "Pantop 40 Tablet"])


def test_normalize():
    assert matcher.normalize("Tab. Dolo-650") == "dolo 650"


def test_exact_match_is_top():
    assert matcher.match_name("Dolo 650", INDEX)[0][0] == "Dolo 650 Tablet"


def test_typo_still_matches():
    assert matcher.match_name("Augmentn 625", INDEX)[0][0] == "Augmentin 625 Duo Tablet"


def test_unclear_gives_no_match():
    assert matcher.match_name("unclear", INDEX) == []


def test_final_confidence_and_flag():
    assert matcher.final_confidence(0.9, 0.5) == 0.45
    assert matcher.is_flagged(0.45, 0.6) and not matcher.is_flagged(0.7, 0.6)


def test_unclear_row_is_flagged():
    row = matcher.build_row({"name": "unclear", "confidence": 0.0}, INDEX)
    assert row["flagged"] and row["matched_name"] == ""

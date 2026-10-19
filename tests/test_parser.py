import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(__file__)))
import reader, schedule


def test_llm_json_with_code_fence():
    text = '```json\n{"medicines": [{"name": "Dolo 650", "dose": "650 mg", "frequency": "1-0-1", "duration": "5 days", "confidence": 0.9}]}\n```'
    meds = reader.parse_llm_json(text)
    assert meds[0]["name"] == "Dolo 650" and meds[0]["confidence"] == 0.9


def test_llm_json_unclear_name_gets_zero_confidence():
    meds = reader.parse_llm_json('{"medicines": [{"name": "unclear", "confidence": 0.8}]}')
    assert meds[0]["confidence"] == 0.0


def test_llm_json_garbage_raises():
    try:
        reader.parse_llm_json("sorry, I cannot read this")
        assert False
    except ValueError:
        pass


def test_ocr_parser():
    lines = [("Tab Dolo 650 mg", 0.9), ("1-0-1 after food x 5 days", 0.8), ("Cap Omez 20", 0.7)]
    meds = reader.parse_ocr_lines(lines)
    assert meds[0]["name"] == "Dolo" and meds[0]["frequency"] == "1-0-1" and meds[0]["duration"] == "x 5 days"
    assert meds[1]["name"] == "Omez"


def test_frequency_patterns():
    assert schedule.parse_frequency("1-0-1")["slots"] == {"morning": 1, "night": 1}
    assert set(schedule.parse_frequency("TDS")["slots"]) == {"morning", "afternoon", "night"}
    assert schedule.parse_frequency("BD after food")["food"] == "after food"
    assert schedule.parse_frequency("OD")["slots"] == {"morning": 1}
    assert not schedule.parse_frequency("unclear")["understood"]


def test_duration():
    assert schedule.parse_duration("2 weeks") == 14 and schedule.parse_duration("unclear") is None


def test_ics_has_alarm_and_crlf():
    plan = [{"name": "Dolo 650", "dose": "650 mg", "days": 3, "schedule": schedule.parse_frequency("BD")}]
    ics = schedule.build_ics(plan)
    assert ics.count("BEGIN:VEVENT") == 2 and "BEGIN:VALARM" in ics and "\r\n" in ics

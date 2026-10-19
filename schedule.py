"""schedule.py - turn "1-0-1", "BD", "TDS" ... into a daily timetable and a .ics file."""
import re
import uuid
from datetime import date, datetime, timedelta

SLOTS = ["morning", "afternoon", "evening", "night"]
SLOT_TIME = {"morning": (8, 0), "afternoon": (14, 0), "evening": (18, 0), "night": (21, 0)}
SLOT_LABEL = {"morning": "Morning", "afternoon": "Afternoon", "evening": "Evening", "night": "Night"}


def slot_time_text(slot):
    h, m = SLOT_TIME[slot]
    return "%d:%02d %s" % (h % 12 or 12, m, "AM" if h < 12 else "PM")


def parse_frequency(text):
    """Return {"slots": {slot: how_many}, "food": str|None, "as_needed": bool, "understood": bool}."""
    t = (text or "").lower().strip()
    out = {"slots": {}, "food": None, "as_needed": False, "understood": False}

    # Food instructions
    if re.search(r"after (food|meals?)|\bpc\b", t):
        out["food"] = "after food"
    elif re.search(r"before (food|meals?)|empty stomach|\bac\b", t):
        out["food"] = "before food"
    elif re.search(r"with (food|meals?)", t):
        out["food"] = "with food"

    if re.search(r"\bsos\b|\bprn\b|as needed|if needed|when required|if required", t):
        out["as_needed"] = True

    # 1) Pattern like 1-0-1 (morning-afternoon-night) or 1-0-0-1 (morning-afternoon-evening-night)
    m = re.search(r"(\d)\s*[-–]\s*(\d)\s*[-–]\s*(\d)(?:\s*[-–]\s*(\d))?", t)
    if m:
        nums = [int(x) for x in m.groups() if x is not None]
        names = SLOTS if len(nums) == 4 else ["morning", "afternoon", "night"]
        for slot, n in zip(names, nums):
            if n > 0:
                out["slots"][slot] = n
    else:
        # 2) Words like "morning and night" win over abbreviations
        if "morning" in t or re.search(r"\bam\b", t):
            out["slots"]["morning"] = 1
        if "afternoon" in t or "noon" in t:
            out["slots"]["afternoon"] = 1
        if "evening" in t:
            out["slots"]["evening"] = 1
        if re.search(r"night|bedtime|\bhs\b", t):
            out["slots"]["night"] = 1
        # 3) Abbreviations
        if not out["slots"]:
            if re.search(r"\bqid\b|\bq\.?i\.?d\b|four times|4 times|every 6", t):
                out["slots"] = {s: 1 for s in SLOTS}
            elif re.search(r"\btds\b|\btid\b|thrice|three times|3 times|every 8", t):
                out["slots"] = {"morning": 1, "afternoon": 1, "night": 1}
            elif re.search(r"\bbd\b|\bbid\b|twice|two times|2 times|every 12", t):
                out["slots"] = {"morning": 1, "night": 1}
            elif re.search(r"\bod\b|\bqd\b|once|every 24|daily", t):
                out["slots"] = {"morning": 1}

    out["understood"] = bool(out["slots"]) or out["as_needed"]
    return out


def parse_duration(text):
    """'5 days' -> 5, '2 weeks' -> 14, '1 month' -> 30. Returns None if unknown."""
    t = (text or "").lower()
    m = re.search(r"(\d+)\s*(day|days|d)\b", t)
    if m:
        return int(m.group(1))
    m = re.search(r"(\d+)\s*(week|weeks|wk|wks|w)\b", t)
    if m:
        return int(m.group(1)) * 7
    m = re.search(r"(\d+)\s*(month|months|mo)\b", t)
    if m:
        return int(m.group(1)) * 30
    return None


def build_timetable(plan):
    """plan = list of {name, dose, schedule(dict from parse_frequency)}.
    Returns {slot: [{"name", "dose", "count", "food"}]} plus nothing for empty slots."""
    table = {s: [] for s in SLOTS}
    for item in plan:
        for slot, count in item["schedule"]["slots"].items():
            table[slot].append({"name": item["name"], "dose": item.get("dose", ""),
                                "count": count, "food": item["schedule"]["food"]})
    return table


def _fold(line):
    """iCalendar lines should be max 75 characters; continuation lines start with a space."""
    out, first = [], True
    while len(line) > 74:
        out.append(line[:74] if first else " " + line[:74])
        line, first = line[74:], False
    out.append(line if first else " " + line)
    return out


def _esc(text):
    return str(text).replace("\\", "\\\\").replace(";", "\\;").replace(",", "\\,").replace("\n", "\\n")


def build_ics(plan, start=None, default_days=7):
    """Return the text of a .ics calendar file with one repeating, alarmed event per medicine per time slot."""
    start = start or date.today()
    now = datetime.utcnow().strftime("%Y%m%dT%H%M%SZ")
    lines = ["BEGIN:VCALENDAR", "VERSION:2.0", "PRODID:-//RxLens//Medicine Plan//EN", "CALSCALE:GREGORIAN"]
    for item in plan:
        days = item.get("days") or default_days
        for slot, count in item["schedule"]["slots"].items():
            h, mi = SLOT_TIME[slot]
            begin = datetime(start.year, start.month, start.day, h, mi)
            end = begin + timedelta(minutes=15)
            what = "Take %s" % item["name"]
            if item.get("dose"):
                what += " (%s)" % item["dose"]
            if count > 1:
                what += " x%d" % count
            note = item["schedule"]["food"] or ""
            lines += ["BEGIN:VEVENT", "UID:%s@rxlens" % uuid.uuid4(), "DTSTAMP:" + now,
                      "DTSTART:" + begin.strftime("%Y%m%dT%H%M%S"), "DTEND:" + end.strftime("%Y%m%dT%H%M%S"),
                      "RRULE:FREQ=DAILY;COUNT=%d" % min(days, 365)]
            lines += _fold("SUMMARY:" + _esc(what))
            lines += _fold("DESCRIPTION:" + _esc((note + ". " if note else "") + "Informational only, not medical advice."))
            lines += ["BEGIN:VALARM", "ACTION:DISPLAY", "TRIGGER:PT0M"]
            lines += _fold("DESCRIPTION:" + _esc(what))
            lines += ["END:VALARM", "END:VEVENT"]
    lines.append("END:VCALENDAR")
    return "\r\n".join(lines) + "\r\n"

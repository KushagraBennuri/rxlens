"""reader.py - read a prescription photo.

Plan A: a vision LLM (Google Gemini free tier).  Plan B: EasyOCR + a simple parser.
Images are handled as bytes in memory. Nothing is written to disk.

To use a different LLM provider, only change call_vision_llm().
"""
import base64
import io
import json
import os
import re
import time

import requests

try:                       # optional: lets you keep GEMINI_API_KEY in a .env file
    from dotenv import load_dotenv
    load_dotenv()
except ImportError:
    pass

# Google retires model names often (the old default gemini-2.5-flash was scheduled to shut down in Oct 2026).
# If you get "HTTP 404", run  python tests/list_models.py  and set GEMINI_MODEL to a name it prints.
GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-3.6-flash")
# Backup models, tried in order if the main one is overloaded (503) or out of quota (429). Comma separated.
GEMINI_FALLBACKS = [m.strip() for m in os.environ.get("GEMINI_FALLBACK_MODELS", "gemini-3.1-flash-lite").split(",") if m.strip()]

PROMPT = """You are reading a photo of a doctor's prescription.
Return ONLY valid JSON, with no other text and no markdown, in exactly this shape:
{"medicines": [{"name": "...", "dose": "...", "frequency": "...", "duration": "...", "confidence": 0.0}]}

Rules:
- "name" is the medicine name as written (brand or generic). Leave out words like Tab, Cap, Syp.
- "dose" is the strength, like "650 mg". "frequency" is exactly as written, like "1-0-1", "BD", "TDS", "after food".
- "duration" is like "5 days".
- If you cannot read a field, write "unclear". NEVER guess.
- "confidence" is a number from 0 to 1: how sure you are about the NAME.
- Only list medicines that are really on the page. Give no medical advice.
- If there are no medicines, return {"medicines": []}."""


class ReaderError(Exception):
    """An error we can show to the user. `kind` says what went wrong."""
    def __init__(self, kind, friendly):
        super().__init__(friendly)
        self.kind = kind
        self.friendly = friendly


# ---------- Plan A: vision LLM ----------

def _call_gemini(model, key, body):
    """One request to one model. Returns text or raises ReaderError."""
    url = "https://generativelanguage.googleapis.com/v1beta/models/%s:generateContent" % model
    try:
        r = requests.post(url, headers={"x-goog-api-key": key}, json=body, timeout=40)
    except requests.RequestException:
        raise ReaderError("network", "Could not reach the Gemini API. Check your internet connection.")
    if r.status_code == 429:
        raise ReaderError("rate_limit", "Gemini free-tier limit reached (429). Wait a minute and try again.")
    if r.status_code in (400, 403) and "API key" in r.text:
        raise ReaderError("bad_key", "Gemini rejected the API key. Check GEMINI_API_KEY.")
    if r.status_code == 404:
        raise ReaderError("bad_model", "Gemini model '%s' was not found (it may have been retired). "
                                       "Run python tests/list_models.py and set GEMINI_MODEL." % model)
    if r.status_code in (500, 502, 503, 504):
        raise ReaderError("busy", "Gemini is overloaded right now (HTTP %d). This is temporary: try again in a minute." % r.status_code)
    if r.status_code != 200:
        raise ReaderError("api_error", "Gemini returned an error (HTTP %d)." % r.status_code)
    try:
        return r.json()["candidates"][0]["content"]["parts"][0]["text"]
    except (KeyError, IndexError, ValueError):
        raise ReaderError("bad_response", "Gemini sent an answer we could not understand.")


def call_vision_llm(image_bytes, mime_type):
    """THE ONE FUNCTION TO CHANGE if you swap providers. Returns the model's raw text.
    Retries a busy server twice, then tries the backup models."""
    key = os.environ.get("GEMINI_API_KEY")
    if not key:
        raise ReaderError("no_key", "No Gemini API key found. Set the GEMINI_API_KEY environment variable "
                                    "(see README), or use Demo mode.")
    body = {
        "contents": [{"parts": [
            {"text": PROMPT},
            {"inline_data": {"mime_type": mime_type or "image/jpeg",
                             "data": base64.b64encode(image_bytes).decode()}}]}],
        "generationConfig": {"temperature": 0, "responseMimeType": "application/json"},
    }
    errors = []
    for model in [GEMINI_MODEL] + [m for m in GEMINI_FALLBACKS if m != GEMINI_MODEL]:
        for attempt in range(3):                       # 1 try + 2 retries, only for "busy"
            try:
                return _call_gemini(model, key, body)
            except ReaderError as err:
                if err.kind == "busy" and attempt < 2:
                    time.sleep(1.5 * (attempt + 1))
                    continue
                errors.append(err)
                break
        if errors[-1].kind in ("no_key", "bad_key", "network"):
            break                                      # another model will not fix these
    # Show the most useful error: prefer one that is not just "model not found" on a backup model
    raise next((e for e in errors if e.kind != "bad_model"), errors[0])


def parse_llm_json(text):
    """Turn the model's text into a clean list of medicine dicts. Raises ValueError if hopeless."""
    cleaned = re.sub(r"```(?:json)?", "", text or "").strip()        # remove code fences
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1:
        start, end = cleaned.find("["), cleaned.rfind("]")           # maybe a bare list
    if start == -1 or end == -1:
        raise ValueError("no JSON found")
    data = json.loads(cleaned[start:end + 1])
    items = data.get("medicines", []) if isinstance(data, dict) else data
    medicines = []
    for item in items:
        if not isinstance(item, dict) or not str(item.get("name", "")).strip():
            continue
        try:
            conf = max(0.0, min(1.0, float(item.get("confidence", 0.5))))
        except (TypeError, ValueError):
            conf = 0.5
        name = str(item["name"]).strip()
        if name.lower() == "unclear":
            conf = 0.0
        medicines.append({"name": name, "dose": str(item.get("dose", "unclear")),
                          "frequency": str(item.get("frequency", "unclear")),
                          "duration": str(item.get("duration", "unclear")), "confidence": conf})
    return medicines


# ---------- Plan B: EasyOCR ----------

DOSE_RE = re.compile(r"\d+(?:\.\d+)?\s*(?:mg|mcg|g|ml|iu)\b", re.I)
FREQ_RE = re.compile(r"\d\s*[-–]\s*\d\s*[-–]\s*\d(?:\s*[-–]\s*\d)?|\b(?:OD|BD|BID|TDS|TID|QID|HS|SOS)\b", re.I)
DUR_RE = re.compile(r"(?:x\s*)?\d+\s*(?:days?|weeks?|months?|d)\b", re.I)
PREFIX_RE = re.compile(r"^\s*(?:tab(?:let)?|cap(?:sule)?|syp|syrup|inj(?:ection)?)\b\.?\s*", re.I)


def parse_ocr_lines(lines):
    """lines = [(text, ocr_confidence)]. Very simple: a line starting with Tab/Cap/Syp/Inj is a medicine."""
    medicines = []
    for i, (text, conf) in enumerate(lines):
        if not PREFIX_RE.match(text):
            continue
        rest = PREFIX_RE.sub("", text)
        nxt = lines[i + 1][0] if i + 1 < len(lines) and not PREFIX_RE.match(lines[i + 1][0]) else ""
        both = text + " " + nxt                                        # frequency is often on the next line
        name = re.split(r"\d|\b(?:OD|BD|TDS|QID|HS)\b", rest, flags=re.I)[0].strip(" .-,")
        if not name:
            continue
        dose = DOSE_RE.search(both)
        freq = FREQ_RE.search(both)
        dur = DUR_RE.search(both)
        medicines.append({"name": name, "dose": dose.group(0) if dose else "unclear",
                          "frequency": freq.group(0) if freq else "unclear",
                          "duration": dur.group(0) if dur else "unclear",
                          "confidence": round(float(conf) * 0.8, 3)})     # OCR is less trustworthy than the LLM
    return medicines


_ocr = None


def read_with_easyocr(image_bytes):
    global _ocr
    try:
        import easyocr
    except ImportError:
        raise ReaderError("no_ocr", "EasyOCR is not installed (pip install -r requirements-ocr.txt).")
    if _ocr is None:
        _ocr = easyocr.Reader(["en"], gpu=False, verbose=False)      # first call downloads models
    results = _ocr.readtext(image_bytes)                              # accepts bytes: no file is written
    lines = [(text, conf) for _, text, conf in results]
    return parse_ocr_lines(lines)


# ---------- Helpers + the one function the app calls ----------

def blur_score(image_bytes):
    """Higher = sharper. Below about 100 usually means a blurry photo."""
    import numpy as np
    from PIL import Image
    img = Image.open(io.BytesIO(image_bytes)).convert("L")
    img.thumbnail((1000, 1000))
    g = np.asarray(img, dtype=float)
    lap = -4 * g[1:-1, 1:-1] + g[:-2, 1:-1] + g[2:, 1:-1] + g[1:-1, :-2] + g[1:-1, 2:]
    return float(lap.var())


def read_prescription(image_bytes, mime_type="image/jpeg", use_fallback=True):
    """Returns {"medicines": [...], "source": "gemini" | "easyocr", "notes": [friendly messages]}."""
    notes = []
    try:
        if blur_score(image_bytes) < 100:
            notes.append("This photo looks blurry. Results may be wrong. A sharper, well-lit photo helps.")
    except Exception:
        raise ReaderError("bad_image", "We could not open that image. Please upload a JPG or PNG photo.")

    try:
        text = call_vision_llm(image_bytes, mime_type)
        try:
            return {"medicines": parse_llm_json(text), "source": "gemini", "notes": notes}
        except (ValueError, json.JSONDecodeError):
            raise ReaderError("bad_response", "The AI answer was not valid JSON.")
    except ReaderError as err:
        if not use_fallback:
            raise
        notes.append(err.friendly + " Trying the offline OCR fallback instead.")
    try:
        return {"medicines": read_with_easyocr(image_bytes), "source": "easyocr", "notes": notes}
    except ReaderError as err:
        raise ReaderError(err.kind, " ".join(notes) + " " + err.friendly)

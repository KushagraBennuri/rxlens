"""db.py - load the medicine CSV into SQLite once, then look medicines up.

The CSV can have different column names depending on where it came from, so we
detect columns by name patterns. Missing columns are fine: the answer is simply
"Ask your doctor or pharmacist".
"""
import ast
import re
import sqlite3
from pathlib import Path

import pandas as pd

ROOT = Path(__file__).parent
DB_PATH = ROOT / "data" / "rxlens.db"
ASK = "Ask your doctor or pharmacist"
SCHEMA = "v2"   # bump this if the table layout changes, so old databases are rebuilt

# For each field we keep, regex patterns for the (normalised) column names.
# Normalised = lowercase, only letters and digits. "sideEffect12" -> "sideeffect12".
# Numbered columns (use0, use1, ...) are all joined together.
FIELD_PATTERNS = {
    "name":        [r"^name$", r"^medicinename$", r"^productname$", r"^drugname$", r"^brandname$"],
    "composition": [r"^composition$", r"^saltcomposition$", r"^genericname$", r"^shortcomposition\d*$", r"^primaryingredient$"],
    "uses":        [r"^uses?\d*$", r"^indications?\d*$", r"^purpose$", r"^medicinedesc$"],
    "how_to_take": [r"^howtouse$", r"^howtotake$", r"^directions?$", r"^dosage$"],
    "cautions":    [r"^sideeffects?\d*$", r"^warnings?\d*$", r"^precautions?\d*$"],
    "habit":       [r"^habitforming$"],
    "active":      [r"^activeingredients$"],      # python-style list of {name, strength}
    "strength":    [r"^primarystrength$"],
    "drug_class":  [r"^therapeuticclass$", r"^class$"],
    "discontinued": [r"^isdiscontinued$"],
}


def _norm(col):
    return re.sub(r"[^a-z0-9]", "", str(col).lower())


def find_csv():
    """Return the dataset path. Falls back to the tiny sample file for testing."""
    for name in ["medicines.csv", "medicines.csv.gz"]:
        p = ROOT / "data" / name
        if p.exists():
            return p, False
    return ROOT / "data" / "medicines_sample.csv", True


def detect_columns(columns):
    """Map each field to the list of real column names that match it."""
    found = {field: [] for field in FIELD_PATTERNS}
    for col in columns:
        n = _norm(col)
        for field, patterns in FIELD_PATTERNS.items():
            if any(re.match(p, n) for p in patterns):
                found[field].append(col)
                break
    return found


def _join(record, cols, sep="; "):
    """Join the non-empty values of several columns of one row (record is a dict of strings)."""
    values = [record[c].strip() for c in cols if record[c] and record[c].strip()]
    return sep.join(values)


def _ingredients(record, cols):
    """'Amoxycillin 500mg + Clavulanic Acid 125mg' from the active-ingredients list, else the primary ingredient."""
    if cols["active"]:
        try:
            items = ast.literal_eval(record[cols["active"][0]])
            text = " + ".join(("%s %s" % (i.get("name", ""), i.get("strength", ""))).strip() for i in items)
            if text:
                return text
        except (ValueError, SyntaxError, AttributeError):
            pass
    text = _join(record, cols["composition"], " + ")
    strength = _join(record, cols["strength"])
    return (text + " " + strength).strip() if text else ""


def build_db(csv_path, db_path=DB_PATH):
    """Read the CSV in chunks and write a clean SQLite table. Returns row count."""
    if db_path.exists():
        db_path.unlink()
    con = sqlite3.connect(db_path)
    con.execute(
        "CREATE TABLE medicines (id INTEGER PRIMARY KEY, name TEXT, name_lower TEXT, composition TEXT,"
        " drug_class TEXT, uses TEXT, how_to_take TEXT, cautions TEXT)"
    )
    total = 0
    for chunk in pd.read_csv(csv_path, dtype=str, chunksize=20000, encoding="utf-8", encoding_errors="replace"):
        cols = detect_columns(chunk.columns)
        if not cols["name"]:
            raise ValueError("Could not find a medicine NAME column. Columns are: %s" % list(chunk.columns))
        rows = []
        for r in chunk.fillna("").to_dict("records"):
            name = _join(r, cols["name"][:1])
            if not name:
                continue
            cautions = _join(r, cols["cautions"])
            if cols["habit"] and _join(r, cols["habit"]).lower() == "yes":
                cautions = ("Habit forming. " + cautions).strip()
            if cols["discontinued"] and _join(r, cols["discontinued"]).lower() == "true":
                cautions = (cautions + " Listed as discontinued in the dataset.").strip()
            rows.append((name, name.lower(), _ingredients(r, cols), _join(r, cols["drug_class"]),
                         _join(r, cols["uses"]), _join(r, cols["how_to_take"], " "), cautions))
        con.executemany(
            "INSERT INTO medicines (name, name_lower, composition, drug_class, uses, how_to_take, cautions)"
            " VALUES (?,?,?,?,?,?,?)", rows)
        total += len(rows)
    con.execute("CREATE INDEX idx_name ON medicines(name_lower)")
    con.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    con.execute("INSERT INTO meta VALUES ('csv', ?)", (_stamp(csv_path),))
    con.commit()
    con.close()
    return total


def _stamp(csv_path):
    return "%s:%d:%s" % (csv_path.name, int(csv_path.stat().st_mtime), SCHEMA)


def init_db():
    """Build the database if it is missing or the CSV changed. Returns (rows, using_sample)."""
    csv_path, using_sample = find_csv()
    stamp = _stamp(csv_path)
    if DB_PATH.exists():
        try:
            con = sqlite3.connect(DB_PATH)
            saved = con.execute("SELECT value FROM meta WHERE key='csv'").fetchone()
            count = con.execute("SELECT COUNT(*) FROM medicines").fetchone()[0]
            con.close()
            if saved and saved[0] == stamp:
                return count, using_sample
        except sqlite3.Error:
            pass  # broken DB file: rebuild below
    return build_db(csv_path), using_sample


def get_names():
    """All medicine names, used by the matcher."""
    con = sqlite3.connect(DB_PATH)
    names = [r[0] for r in con.execute("SELECT name FROM medicines")]
    con.close()
    return names


def lookup(name):
    """Return purpose / how to take / cautions for one exact dataset name.
    Anything missing becomes "Ask your doctor or pharmacist"."""
    con = sqlite3.connect(DB_PATH)
    row = con.execute(
        "SELECT name, composition, uses, how_to_take, cautions, drug_class FROM medicines"
        " WHERE name_lower = ? LIMIT 1", (name.lower(),)).fetchone()
    con.close()
    if row is None:
        return {"name": name, "composition": ASK, "medicine_type": ASK, "purpose": ASK, "how_to_take": ASK, "cautions": ASK, "in_dataset": False}
    return {"name": row[0], "composition": row[1] or ASK, "medicine_type": (row[5] or ASK).capitalize(), "purpose": row[2] or ASK,
            "how_to_take": row[3] or ASK, "cautions": row[4] or ASK, "in_dataset": True}

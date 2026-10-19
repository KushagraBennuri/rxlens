# RxLens: prescription photo to plain-language medicine plan

Informational only, not medical advice. Use dummy or sample prescriptions only.
Uploaded images are processed in memory and never saved.

## How the code is organised
`app.py` UI, `reader.py` Gemini call (`call_vision_llm` is the one function to swap) + EasyOCR fallback, `matcher.py` fuzzy match + confidence, `schedule.py` frequency parsing + timetable + .ics, `db.py` CSV to SQLite + lookup. Dataset columns are found by name pattern (e.g. `use0..use4`, `sideEffect0..41`, `Habit Forming`); missing ones show "Ask your doctor or pharmacist".

## Dataset note
The bundled `data/medicines.csv.gz` has name, ingredients, therapeutic class, price and manufacturer, but NO uses / side-effects / how-to-take columns. So the Plan tab shows "Contains" and "Medicine type" from the dataset, and "Ask your doctor or pharmacist" for purpose, how to take and cautions. To fill those, use a dataset that has such columns (the app detects `use0..`, `sideEffect0..`, `how_to_use`, `warnings`, etc.).

## Known limitations
- Only Gemini + EasyOCR; handwriting accuracy has NOT been measured on real handwriting yet.
- English only. The slide's Hindi goal is not built.
- Medical text comes only from your CSV. If it has no "how to take" column (many don't), the app says "Ask your doctor or pharmacist".
- "Cautions" are the dataset's side-effect and habit-forming fields, not dose-specific warnings. No interaction or allergy checks.
- Under 15 s is realistic with Gemini; EasyOCR on a free CPU is slower, especially on first load.
- Reminders: on-screen timetable and .ics only. Telegram/email alerts are NOT built. Slot times are fixed (8:00, 14:00, 18:00, 21:00). Unclear durations default to 7 days in the .ics.
- Nothing is saved between sessions (no profiles or saved schedules), by design.
- The free tier may use submitted images to improve Google products. Use dummy prescriptions only.

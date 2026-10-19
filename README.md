# RxLens: prescription photo to plain-language medicine plan

Informational only, not medical advice. Use dummy or sample prescriptions only.
Uploaded images are processed in memory and never saved.

## Setup in 5 steps
1. Install Python 3.10+.
2. `pip install -r requirements.txt`  (optional offline OCR fallback: `pip install -r requirements-ocr.txt`)
3. Put your medicine CSV at `data/medicines.csv` (`.csv.gz` also works). Until you do, the app uses a 14-row SAMPLE file for testing only.
4. Copy `.env.example` to `.env` and paste your Gemini key (next section).
5. `streamlit run app.py`  (first start loads the CSV into SQLite; this takes a while for 2.5 lakh rows, then it is instant).

## Get the free Gemini key
1. Go to https://aistudio.google.com and sign in with a Google account.
2. Click "Get API key" then "Create API key".
3. Paste it into `.env` as `GEMINI_API_KEY=...`. Model names and free-tier limits change often (the old `gemini-2.5-flash` was due to shut down in October 2026). Default is `gemini-3.6-flash`. If you get HTTP 404, run `python tests/list_models.py` and set `GEMINI_MODEL` in `.env` (or in Streamlit Secrets). Free daily request limits for newer Flash models may be low (reports range from about 20 to 1,500 per day), so check AI Studio's rate-limit page and use Demo mode when you run out.

## Run
- `streamlit run app.py`, then use the tabs Scan, Review, Plan, Caregiver.
- Tick "Demo mode" in the sidebar to use cached results with no internet or API key.
- Tests: `python tests/run_tests.py` (or `python -m pytest`).

## Evaluate (the real accuracy number for the slide)
1. Put your test images in `samples/` and list the correct medicine names in `samples/answers.json`. The 3 included images are dummy PRINTED text. Add handwritten dummy prescriptions for a fair number.
2. `python tests/evaluate.py`  (calls Gemini, waits 7 s between images for the free-tier limit).
3. Read "Name accuracy, verified". `--save-cache` stores the real model output as the new demo cache. Do not quote `--demo` numbers.

## Deploy free
**Streamlit Community Cloud (easiest):** push this folder to GitHub, create an app at share.streamlit.io pointing to `app.py`, and add `GEMINI_API_KEY` under Advanced settings > Secrets. Do not install EasyOCR there (too big); the app skips the fallback politely.
**Render:** new Web Service, build `pip install -r requirements.txt`, start `streamlit run app.py --server.port $PORT --server.address 0.0.0.0`, add `GEMINI_API_KEY` as an environment variable. The free plan sleeps when idle.
**Big dataset:** GitHub files over 100 MB are rejected. Keep only the useful columns, gzip it (`medicines.csv.gz`), or use Git LFS. The database is rebuilt on each fresh deploy.

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

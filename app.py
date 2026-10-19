"""app.py - RxLens Streamlit UI.  Run with:  streamlit run app.py"""
import html as htmllib
import json
import time
from pathlib import Path

import streamlit as st

import db
import matcher
import reader
import schedule

ROOT = Path(__file__).parent
SAMPLES = ROOT / "samples"
ASK = db.ASK
TYPE_OWN = "None of these: I will type the name"

st.set_page_config(page_title="RxLens", page_icon="💊", layout="wide")


@st.cache_resource(show_spinner="Loading medicine database (first run can take a minute)...")
def load_index():
    """Load the CSV into SQLite (once) and build the matching index."""
    rows, using_sample = db.init_db()
    return matcher.build_index(db.get_names()), rows, using_sample


index, db_rows, using_sample = load_index()
if "scan_id" not in st.session_state:
    st.session_state.scan_id = 0

# ---------------- Sidebar ----------------
st.sidebar.title("RxLens")
demo_mode = st.sidebar.checkbox("Demo mode (cached results, works offline)")
threshold = st.sidebar.slider("Flag medicines below confidence", 0.3, 0.9, matcher.DEFAULT_THRESHOLD, 0.05)
st.sidebar.caption("Medicine database: %d rows%s" % (db_rows, " (SAMPLE file: add data/medicines.csv)" if using_sample else ""))

# ---------------- Always-visible disclaimer ----------------
st.title("💊 RxLens")
st.warning("Informational only, not medical advice. Always follow your doctor's instructions.")
tab_scan, tab_review, tab_plan, tab_care = st.tabs(["1. Scan", "2. Review", "3. Plan", "4. Caregiver"])


def run_scan(image_bytes, mime, demo_choice):
    """Read -> verify. Stores the result in session_state."""
    start = time.perf_counter()
    notes, source = [], "demo cache"
    try:
        if demo_mode:
            cache = json.loads((SAMPLES / "demo_cache.json").read_text())
            meds = cache[demo_choice]["medicines"]
        else:
            result = reader.read_prescription(image_bytes, mime)
            meds, source, notes = result["medicines"], result["source"], result["notes"]
    except reader.ReaderError as err:
        st.error(err.friendly)
        return
    if not meds:
        st.warning("No medicines found. Try a clearer, well-lit photo that shows the whole prescription.")
        for n in notes:
            st.info(n)
        return
    st.session_state.rows = [matcher.build_row(m, index, threshold) for m in meds]
    st.session_state.scan_id += 1
    st.session_state.plan = None
    st.session_state.elapsed = time.perf_counter() - start
    st.session_state.source = source
    st.session_state.notes = notes
    st.success("Done in %.1f seconds. Go to the 'Review' tab." % st.session_state.elapsed)
    for n in notes:
        st.info(n)


# ---------------- Tab 1: Scan ----------------
with tab_scan:
    image_bytes, mime, demo_choice = None, None, None
    if demo_mode:
        cache_names = list(json.loads((SAMPLES / "demo_cache.json").read_text()).keys())
        demo_choice = st.selectbox("Sample prescription", cache_names)
        st.image(str(SAMPLES / demo_choice), width=500)
        ready = True
    else:
        st.caption("Use dummy or sample prescriptions only. Images are processed in memory and never saved.")
        upload = st.file_uploader("Upload a prescription photo", type=["jpg", "jpeg", "png"])
        camera = st.camera_input("...or take a photo")
        pic = camera or upload
        ready = pic is not None
        if pic is not None:
            st.image(pic, width=500)
            image_bytes, mime = pic.getvalue(), pic.type
    if st.button("Read prescription", type="primary", disabled=not ready):
        with st.spinner("Reading..."):
            run_scan(image_bytes, mime, demo_choice)

# ---------------- Tab 2: Review ----------------
with tab_review:
    rows = st.session_state.get("rows")
    if not rows:
        st.info("Scan a prescription first.")
    else:
        sid = st.session_state.scan_id
        st.caption("Read by: %s. Red = low confidence: pick the right name or type it before continuing." % st.session_state.source)
        for i, row in enumerate(rows):
            flagged = matcher.is_flagged(row["final_conf"], threshold)
            color = "red" if flagged else "green"
            with st.container(border=True):
                st.markdown(":%s[**%s**] (read as: *%s*)" % (color, row["matched_name"] or "No match", row["name"]))
                st.caption("Match score %.0f%%  |  Reader confidence %.0f%%  |  **Final confidence %.0f%%**"
                           % (row["match_score"] * 100, row["confidence"] * 100, row["final_conf"] * 100))
                options = [n for n, _ in row["suggestions"]] + [TYPE_OWN]
                st.radio("Which medicine is this?", options, index=None if flagged else 0, key="pick_%d_%d" % (sid, i))
                if st.session_state.get("pick_%d_%d" % (sid, i)) == TYPE_OWN:
                    st.text_input("Type the medicine name", key="own_%d_%d" % (sid, i))
                c1, c2, c3 = st.columns(3)
                c1.text_input("Dose", row["dose"], key="dose_%d_%d" % (sid, i))
                c2.text_input("How often (e.g. 1-0-1, BD, TDS)", row["frequency"], key="freq_%d_%d" % (sid, i))
                c3.text_input("For how long", row["duration"], key="dur_%d_%d" % (sid, i))
                st.checkbox("Remove this medicine", key="rm_%d_%d" % (sid, i))

        if st.button("Confirm and build my plan", type="primary"):
            plan, problems = [], []
            for i, row in enumerate(rows):
                get = lambda k: st.session_state.get("%s_%d_%d" % (k, sid, i))
                if get("rm"):
                    continue
                pick = get("pick")
                if pick is None:
                    problems.append(row["name"])
                    continue
                if pick == TYPE_OWN:
                    typed = (get("own") or "").strip()
                    found = matcher.match_name(typed, index, 1)
                    pick = found[0][0] if found and found[0][1] >= threshold else typed
                if not pick:
                    problems.append(row["name"])
                    continue
                info = db.lookup(pick)
                plan.append({"name": info["name"], "dose": get("dose"), "info": info,
                             "schedule": schedule.parse_frequency(get("freq")),
                             "days": schedule.parse_duration(get("dur"))})
            if problems:
                st.error("Please choose or type a name for: " + ", ".join(problems))
            elif not plan:
                st.warning("Nothing left in the plan.")
            else:
                st.session_state.plan = plan
                st.success("Plan ready. Open the 'Plan' tab.")

# ---------------- Tab 3: Plan ----------------
with tab_plan:
    plan = st.session_state.get("plan")
    if not plan:
        st.info("Confirm your medicines in the Review tab to see the plan.")
    else:
        if st.session_state.get("elapsed") is not None:
            st.metric("Time from photo to schedule (reading + checking)", "%.1f s" % st.session_state.elapsed,
                      help="Target: under 15 seconds. Time you spend reviewing is not counted.")
        table = schedule.build_timetable(plan)
        st.subheader("Daily timetable")
        cols = st.columns(4)
        for col, slot in zip(cols, schedule.SLOTS):
            with col:
                st.markdown("**%s**  \n%s" % (schedule.SLOT_LABEL[slot], schedule.slot_time_text(slot)))
                for item in table[slot]:
                    extra = ", ".join(x for x in [item["dose"] if item["dose"] != "unclear" else "", item["food"] or ""] if x)
                    st.write("💊 %s%s%s" % (item["name"], " x%d" % item["count"] if item["count"] > 1 else "", " (%s)" % extra if extra else ""))
                if not table[slot]:
                    st.caption("nothing")
        for item in plan:
            if item["schedule"]["as_needed"]:
                st.info("%s: take only when needed." % item["name"])
            if not item["schedule"]["understood"]:
                st.warning("%s: we could not understand how often to take it. Ask your doctor or pharmacist." % item["name"])
        st.download_button("📅 Download reminders (.ics calendar file)", schedule.build_ics(plan),
                           file_name="rxlens_reminders.ics", mime="text/calendar")
        if any(not it["days"] for it in plan):
            st.caption("Where the duration was unclear, calendar reminders repeat for 7 days.")

        st.subheader("About your medicines")
        for item in plan:
            info = item["info"]
            with st.expander(item["name"], expanded=True):
                if not info["in_dataset"]:
                    st.warning("Not found in our medicine database. Ask your doctor or pharmacist.")
                st.markdown("**Contains:** %s" % info["composition"])
                st.markdown("**Medicine type:** %s" % info["medicine_type"])
                st.markdown("**What it is for:** %s" % info["purpose"])
                st.markdown("**How to take it:** %s" % info["how_to_take"])
                st.markdown("**Cautions and side effects:** %s" % info["cautions"])
        st.caption("This text comes only from the medicine dataset. It is not generated by AI.")

# ---------------- Tab 4: Caregiver ----------------
with tab_care:
    plan = st.session_state.get("plan")
    if not plan:
        st.info("Build the plan first.")
    else:
        table = schedule.build_timetable(plan)
        icons = {"morning": "🌅", "afternoon": "☀️", "evening": "🌇", "night": "🌙"}
        html = ""
        for slot in schedule.SLOTS:
            if not table[slot]:
                continue
            html += "<div style='font-size:2.2rem;font-weight:700;margin-top:1.2rem;border-bottom:3px solid gray'>%s %s, %s</div>" % (
                icons[slot], schedule.SLOT_LABEL[slot], schedule.slot_time_text(slot))
            for item in table[slot]:
                note = " (%s)" % item["food"] if item["food"] else ""
                dose = " %s" % item["dose"] if item["dose"] and item["dose"] != "unclear" else ""
                count = " x%d" % item["count"] if item["count"] > 1 else ""
                html += "<div style='font-size:1.9rem;margin:0.4rem 0 0.4rem 1rem'>💊 %s%s%s%s</div>" % (htmllib.escape(item["name"]), htmllib.escape(dose), count, htmllib.escape(note))
        st.markdown(html or "No scheduled medicines.", unsafe_allow_html=True)
        st.caption("Informational only, not medical advice.")

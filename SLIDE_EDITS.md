# Slide edits so the deck matches what was built

**Slide 3 Objective:** "EN + HI / Simple English and Hindi" -> "Plain English" (Hindi is not built; keep it on Future Scope). Fill 85%+ and <15s with measured values from `tests/evaluate.py` and the on-screen timer.

**Slide 4 Solution**
- Drug-DB check: "Verifies names, fixes OCR errors" -> "Matches names to a medicine dataset, flags doubtful reads"
- Smart reminders: "Daily schedule + caregiver alerts" -> "Daily timetable, calendar reminders (.ics), caregiver view"

**Slide 6 Tech Stack**
- AI / ML: "Gemini vision LLM (free tier)" / "EasyOCR fallback" / "RapidFuzz name matching"
- Backend & Data: "Python + Streamlit" / "SQLite" / "Public medicine dataset (~2.5 lakh rows)"
- Web & Cloud: "Streamlit mobile-friendly web app" / "Calendar (.ics) reminders, no SMS" / "Streamlit Community Cloud / Render hosting"

**Slide 7 Workflow**
- Step 2 "Clean image + OCR" -> "Vision LLM reads (OCR fallback)". Image cleaning is not built, only a blur warning.
- Step 5 "Schedule + caregiver alerts" -> "Schedule + .ics + caregiver view"
- Data layer "Drug dataset · User profiles · Saved schedules" -> "Medicine dataset (SQLite). No images or profiles stored"

**Slide 8 Feasibility**
- Resources: "Pretrained vision LLM (free tier) + EasyOCR fallback + public drug data, no training"
- Timeline label "OCR + DB" -> "Reader + DB"
- Risk -> Plan: add "unclear is never guessed; low confidence goes to manual edit / top-3 suggestions"

**Also:** Slide 11 "React UI · APIs" -> "Streamlit UI · Reader". Slide 1 and 11 still have placeholders for team name, members and contacts.

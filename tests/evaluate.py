"""Measure name accuracy on samples/ using samples/answers.json.

  python tests/evaluate.py              live: calls Gemini for every image
  python tests/evaluate.py --demo       uses samples/demo_cache.json (no internet)
  python tests/evaluate.py --save-cache live run, then SAVES the real model output as the new demo cache

Two numbers are printed:
  raw read      the name the reader returned, compared with the answer
  verified      the dataset name chosen by the matcher, compared with the answer
Use the 'verified' number on the slide ONLY with real (ideally handwritten) test prescriptions.
"""
import json, os, sys, time
ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)
import db, matcher, reader

SAMPLES = os.path.join(ROOT, "samples")


def same_medicine(predicted, expected):
    a, b = matcher.normalize(predicted), matcher.normalize(expected)
    if not a or not b:
        return False
    return a == b or a.startswith(b) or b.startswith(a) or " ".join(a.split()[:2]) == " ".join(b.split()[:2])


def main():
    demo, save = "--demo" in sys.argv, "--save-cache" in sys.argv
    db.init_db()
    index = matcher.build_index(db.get_names())
    answers = json.load(open(os.path.join(SAMPLES, "answers.json")))
    cache_path = os.path.join(SAMPLES, "demo_cache.json")
    cache = json.load(open(cache_path)) if demo else {}
    new_cache, total, raw_ok, ver_ok, times = 0, 0, 0, 0, []

    for fname, expected in answers.items():
        start = time.perf_counter()
        if demo:
            meds = cache[fname]["medicines"]
        else:
            data = open(os.path.join(SAMPLES, fname), "rb").read()
            try:
                result = reader.read_prescription(data, "image/png", use_fallback=False)
            except reader.ReaderError as err:
                print("%s: SKIPPED - %s" % (fname, err.friendly)); continue
            meds = result["medicines"]
            if save:
                cache[fname] = {"medicines": meds}
            time.sleep(7)                      # stay under the free-tier requests-per-minute limit
        rows = [matcher.build_row(m, index) for m in meds]
        times.append(time.perf_counter() - start)
        print("\n%s  (%.1fs)" % (fname, times[-1]))
        for exp in expected:
            total += 1
            raw = any(same_medicine(r["name"], exp) for r in rows)
            ver = any(same_medicine(r["matched_name"], exp) for r in rows)
            raw_ok += raw; ver_ok += ver
            print("  %-16s raw read: %-4s verified: %s" % (exp, "OK" if raw else "MISS", "OK" if ver else "MISS"))

    if save and cache:
        json.dump(cache, open(cache_path, "w"), indent=2)
        print("\nSaved real model output to samples/demo_cache.json")
    if demo:
        print("\n*** DEMO MODE: cached answers, NOT a real accuracy number. Do not put this on a slide. ***")
    if total:
        print("\nImages: %d   Medicines: %d" % (len(times), total))
        print("Name accuracy, raw read : %d/%d = %.1f%%" % (raw_ok, total, 100.0 * raw_ok / total))
        print("Name accuracy, verified : %d/%d = %.1f%%   (target 85%%+)" % (ver_ok, total, 100.0 * ver_ok / total))
        print("Average time per image  : %.1fs  (target under 15s)" % (sum(times) / len(times)))
    else:
        print("Nothing was evaluated.")


if __name__ == "__main__":
    main()

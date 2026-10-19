"""Print the Gemini models your API key can use for image reading.  python tests/list_models.py"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
import requests
import reader  # loads .env

key = os.environ.get("GEMINI_API_KEY")
if not key:
    sys.exit("Set GEMINI_API_KEY first (see README).")
r = requests.get("https://generativelanguage.googleapis.com/v1beta/models?pageSize=200", headers={"x-goog-api-key": key}, timeout=30)
if r.status_code != 200:
    sys.exit("HTTP %d: %s" % (r.status_code, r.text[:300]))
for m in r.json().get("models", []):
    if "generateContent" in m.get("supportedGenerationMethods", []):
        print(m["name"].replace("models/", ""))
print("\nPut one of the 'flash' names in .env as GEMINI_MODEL=... (flash-lite is cheaper/faster but weaker at handwriting).")

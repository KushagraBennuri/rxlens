"""Run all tests without pytest:  python tests/run_tests.py   (pytest also works: python -m pytest)"""
import importlib, os, sys
sys.path.insert(0, os.path.dirname(__file__))
failed = 0
for mod_name in ["test_matcher", "test_parser"]:
    mod = importlib.import_module(mod_name)
    for name in dir(mod):
        if name.startswith("test_"):
            try:
                getattr(mod, name)(); print("PASS", mod_name, name)
            except Exception as e:
                failed += 1; print("FAIL", mod_name, name, repr(e))
print("%d failed" % failed); sys.exit(1 if failed else 0)

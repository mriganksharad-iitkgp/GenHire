"""Local backend launcher: python dev.py [--check] [--no-reload]."""
import argparse
import os
import runpy
from core.runtime import ensure_local_runtime, select_runtime


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--check", action="store_true", help="Check dependencies without loading credentials or connecting to services")
    parser.add_argument("--no-reload", action="store_true", help="Run once without the development reloader")
    args = parser.parse_args()
    if args.check:
        status = select_runtime()
        print("Python: " + status["version"] + " (" + status["executable"] + ")")
        print("Dependencies: " + ("ready" if status["ready"] else "incomplete"))
        if status["missing"]:
            print("Missing: " + ", ".join(status["missing"]))
        return 0 if status["ready"] else 1
    ensure_local_runtime()
    if args.no_reload:
        os.environ["GENHIRE_DEV_RELOAD"] = "0"
    os.chdir(os.path.dirname(os.path.abspath(__file__)))
    runpy.run_path("app.py", run_name="__main__")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

"""Standard-library-only checks for the local backend interpreter."""
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import subprocess
import sys
import socket

BACKEND = Path(__file__).resolve().parents[1]
SUPPORTED = {(3, 11), (3, 12)}


def runtime_status():
    missing = []
    for line in (BACKEND / "requirements.txt").read_text(encoding="utf-8").splitlines():
        match = re.match(r"([A-Za-z0-9_.-]+)==", line.strip())
        if not match:
            continue
        name = match.group(1)
        try:
            metadata.version(name)
        except metadata.PackageNotFoundError:
            # Local OpenCV wheels share the cv2 module; never install two variants.
            if name == "opencv-python-headless" and importlib.util.find_spec("cv2"):
                continue
            missing.append(name)
    supported = sys.version_info[:2] in SUPPORTED
    return {"executable": sys.executable, "version": sys.version.split()[0],
            "supported": supported, "missing": missing, "ready": supported and not missing}


def select_runtime():
    current = runtime_status()
    if current["ready"]:
        return current
    for candidate in (BACKEND / "venv", BACKEND / ".venv", BACKEND.parent / ".venv-backend", BACKEND.parent / ".venv"):
        executable = candidate / ("Scripts/python.exe" if os.name == "nt" else "bin/python")
        if not executable.is_file() or executable.resolve() == Path(sys.executable).resolve():
            continue
        try:
            probe = subprocess.run([str(executable), str(Path(__file__)), "--json"],
                                   capture_output=True, text=True, timeout=15, check=True)
            result = json.loads(probe.stdout)
            if result["ready"]:
                return result
        except (OSError, subprocess.SubprocessError, ValueError):
            continue
    return current


def ensure_local_runtime():
    current = runtime_status()
    selected = select_runtime()
    if not selected["ready"]:
        reason = "Python 3.11 or 3.12 is required for the pinned backend dependencies."
        if selected["missing"]:
            reason += " Missing packages: " + ", ".join(selected["missing"]) + "."
        raise SystemExit(reason + "\nFrom python-backend, create an environment with `py -3.12 -m venv venv`, "
                         "then run `venv/Scripts/python.exe -m pip install -r requirements.txt`. "
                         "Run `python dev.py --check` to verify it.")
    if Path(selected["executable"]).resolve() != Path(current["executable"]).resolve():
        print("[GenHire] Using backend Python " + selected["version"] + ": " + selected["executable"], flush=True)
        replace_process(selected["executable"], sys.argv)


def run_foreground(executable, arguments):
    """Wait for the child on Windows so Git Bash retains output and exit status."""
    with subprocess.Popen([str(executable), *arguments]) as process:
        try:
            return process.wait()
        except KeyboardInterrupt:
            # The console delivers Ctrl+C to the child too. Allow its finally
            # blocks to stop jobs before terminating only this child if needed.
            try:
                process.wait(timeout=5)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait()
            return 130


def replace_process(executable, arguments):
    if os.name == "nt":
        raise SystemExit(run_foreground(executable, arguments))
    os.execv(str(executable), [str(executable), *arguments])


def check_local_port(port):
    if not 1 <= port <= 65535:
        raise SystemExit("PORT must be between 1 and 65535.")
    with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as probe:
        try:
            probe.bind(("0.0.0.0", port))
        except OSError as error:
            raise SystemExit(
                f"GenHire cannot start: port {port} is already in use or unavailable. "
                "Stop the earlier backend with Ctrl+C, then run python app.py again. "
                "To use another port, set PORT and update REACT_APP_API_URL/API_BASE."
            ) from error


if __name__ == "__main__":
    print(json.dumps(runtime_status()))

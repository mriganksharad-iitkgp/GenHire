"""Process-level bootstrap side effects.

Must be imported before any heavy (TF/MediaPipe-adjacent) import anywhere in
the app: forces UTF-8 stdout/stderr on Windows and silences the TF/glog/absl
log firehose. Moved verbatim from the top of app.py; safe to import multiple
times.
"""

import io
import logging
import os
import sys
import warnings

# Force UTF-8 encoding for standard output/error to prevent crash on printing emojis in Windows
if hasattr(sys.stdout, 'reconfigure'):
    sys.stdout.reconfigure(encoding='utf-8')
if hasattr(sys.stderr, 'reconfigure'):
    sys.stderr.reconfigure(encoding='utf-8')
elif hasattr(sys.stdout, 'buffer'):
    sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')
    sys.stderr = io.TextIOWrapper(sys.stderr.buffer, encoding='utf-8')

# Suppress pydantic warnings
warnings.filterwarnings("ignore", category=UserWarning, module="pydantic")

# ── Silence all TF / MediaPipe / glog noise before any import triggers them ──
# TF C++ backend: 0=DEBUG 1=INFO 2=WARNING 3=ERROR(only)
os.environ["TF_CPP_MIN_LOG_LEVEL"] = "3"
# glog (Google Logging used by MediaPipe/TFLite): 0=INFO 1=WARNING 2=ERROR 3=FATAL
os.environ["GLOG_minloglevel"] = "2"
# abseil-py
os.environ["ABSL_MIN_LOG_LEVEL"] = "3"
# suppress Python-level TF / tf_keras / absl loggers
logging.getLogger("tensorflow").setLevel(logging.ERROR)
logging.getLogger("tf_keras").setLevel(logging.ERROR)
logging.getLogger("absl").setLevel(logging.ERROR)
logging.getLogger("mediapipe").setLevel(logging.ERROR)
# suppress absl-py programmatic API if available
try:
    import absl.logging as _absl_log
    _absl_log.set_verbosity(_absl_log.ERROR)
except Exception:
    pass
warnings.filterwarnings("ignore", category=UserWarning)
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tensorflow")
warnings.filterwarnings("ignore", category=DeprecationWarning, module="tf_keras")

"""GenHire backend entrypoint.

The composition root lives in core/factory.py (create_app); this module stays
as the stable target for both deployment commands:

    gunicorn ... app:app          (Cloud Run / start_server.sh)
    python app.py                 (local dev server with reloader)
"""

import contextlib
import io
import os

if __name__ == "__main__":
    from core.runtime import ensure_local_runtime
    ensure_local_runtime()
    from config.env_loader import load_environment
    from core.runtime import check_local_port
    load_environment()
    if os.environ.get("WERKZEUG_RUN_MAIN") != "true":
        try:
            check_local_port(int(os.getenv("PORT", "5000")))
        except ValueError as error:
            raise SystemExit("PORT must be an integer between 1 and 65535.") from error

_local_development = os.getenv("FLASK_ENV", "development").strip().lower() != "production"
_dev_reloader = _local_development and os.environ.get("GENHIRE_DEV_RELOAD", "1") != "0"

# `python app.py` with the Werkzeug auto-reloader always runs this module
# TWICE per process generation: once as a disposable "watcher" process (which
# builds a throwaway Flask app — connecting to Mongo, registering blueprints,
# running the wallet bootstrap, printing every boot log — then hands off to a
# reloaded subprocess and never serves) and once for real in that subprocess
# (WERKZEUG_RUN_MAIN=true). gunicorn workers (__name__ != "__main__") are
# unaffected either way. create_app() itself can't be skipped in the watcher
# pass — socketio.run() unconditionally dereferences socketio.server.eio
# (set by socketio.init_app() inside create_app()) before it even checks
# whether a reloader is in play, so a stub Flask() app would crash on the
# very first call. Instead:
#   - the heavy imports (core.bootstrap, core.factory) AND the create_app()
#     call are both done with sys.stdout/sys.stderr swapped to throwaway
#     io.StringIO() sinks via contextlib.redirect_stdout/redirect_stderr, so
#     the watcher's boot logs don't print at all. This has to wrap the
#     IMPORTS themselves, not just the create_app() call: core/factory.py's
#     `logging.StreamHandler()` binds to whatever sys.stderr IS at the moment
#     that module is first imported, and a later reassignment of sys.stderr
#     wouldn't touch an already-bound handler — so the redirect must already
#     be active before `from core.factory import create_app` runs. An
#     earlier version of this fix used os.dup2 on the real OS file
#     descriptors instead, which is NOT safe here: dup2'ing fd 1/2 away from
#     a real Windows console handle and back doesn't reliably restore the
#     console's write mode, and a subsequent print() can fail with
#     `OSError: [WinError 1] Incorrect function`. contextlib.redirect_stdout/
#     redirect_stderr only swap the Python-level sys.stdout/sys.stderr
#     attribute, never touching the underlying OS handle, so it's safe to
#     restore even against a real interactive console;
#   - GENHIRE_DISABLE_JOBS is forced on for the duration of that call so the
#     three background daemons (CV-scoring queue, invite cleanup, refund
#     sweeper) start ONLY in the real subprocess — otherwise the watcher's
#     copies would run against the live DB for the dev server's whole
#     lifetime, duplicating every scheduled sweep/cleanup alongside the
#     subprocess's real ones.
_is_disposable_reloader_watcher = (
    __name__ == "__main__" and _dev_reloader and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
)

if _is_disposable_reloader_watcher:
    _prior_jobs_disabled = os.environ.get("GENHIRE_DISABLE_JOBS")
    os.environ["GENHIRE_DISABLE_JOBS"] = "1"
    try:
        with contextlib.redirect_stdout(io.StringIO()), contextlib.redirect_stderr(io.StringIO()):
            import core.bootstrap  # noqa: F401  side effects: UTF-8 stdout, TF/glog silencing
            from core.extensions import socketio
            from core.factory import create_app
            app = create_app()
    finally:
        if _prior_jobs_disabled is None:
            os.environ.pop("GENHIRE_DISABLE_JOBS", None)
        else:
            os.environ["GENHIRE_DISABLE_JOBS"] = _prior_jobs_disabled
else:
    import core.bootstrap  # noqa: F401  side effects: UTF-8 stdout, TF/glog silencing
    from core.extensions import socketio
    from core.factory import create_app
    app = create_app()

if __name__ == "__main__":
    from jobs import runner as jobs_runner
    from core.development_server import DevelopmentRequestHandler

    try:
        # socketio.run enables simple-websocket in the native-thread local server.
        socketio.run(
            app,
            debug=_local_development,
            # The interactive debugger turns WebSocket's normal connection-
            # closing signal into a false HTTP 500 in the local threaded server.
            use_debugger=False,
            request_handler=DevelopmentRequestHandler,
            host="0.0.0.0",
            port=int(os.getenv("PORT", "5000")),
            use_reloader=_dev_reloader,
            # Also allow local IDE/piped invocations without a terminal. Cloud
            # Run uses Gunicorn and never executes this development-server path.
            allow_unsafe_werkzeug=_local_development,
        )
    finally:
        jobs_runner.stop_all()

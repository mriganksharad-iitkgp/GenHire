"""GenHire backend entrypoint.

The composition root lives in core/factory.py (create_app); this module stays
as the stable target for both deployment commands:

    gunicorn ... app:app          (Cloud Run / start_server.sh)
    python app.py                 (local dev server with reloader)
"""

import contextlib
import io
import os

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
    __name__ == "__main__" and os.environ.get("WERKZEUG_RUN_MAIN") != "true"
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

    try:
        # socketio.run instead of app.run to enable the WebSocket eventlet server
        socketio.run(
            app,
            debug=True,
            host="0.0.0.0",
            port=int(os.getenv("PORT", "5000")),
            use_reloader=True,
        )
    finally:
        jobs_runner.stop_all()

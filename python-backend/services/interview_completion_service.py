"""Single-flight, bounded report work; HTTP retries observe the same operation."""
import threading
import time
import datetime
import uuid
from concurrent.futures import ThreadPoolExecutor, TimeoutError
from flask import current_app, jsonify

_pool = ThreadPoolExecutor(max_workers=4, thread_name_prefix="interview-report")
_lock = threading.Lock()
_jobs = {}


def complete_in_background(key, complete, collection=None):
    app = current_app._get_current_object()
    with _lock:
        # Completed responses are persisted by the caller; bounded short cache
        # also lets a retry observe an exception before a fresh recovery attempt.
        for old_key, (future, started) in list(_jobs.items()):
            if future.done() and time.monotonic() - started > 120:
                _jobs.pop(old_key, None)
        entry = _jobs.get(key)
        if entry is None:
            if sum(not future.done() for future, _ in _jobs.values()) >= 4:
                return jsonify({"error": "Reports are busy. Your answers are saved; please retry.",
                                "error_code": "report_busy"}), 503
            def run():
                from services.interview_flow_service import session_lock
                with app.app_context():
                    with session_lock(key[-1]):
                        owner = uuid.uuid4().hex
                        identity = {"session_id": key[-1], "user_id": key[-2]}
                        if collection is not None:
                            now = datetime.datetime.now(datetime.timezone.utc)
                            claimed = collection.update_one(dict(identity, **{"$or": [
                                {"report_lease_until": {"$exists": False}}, {"report_lease_until": {"$lte": now}}]}),
                                {"$set": {"report_lease_owner": owner, "report_lease_until": now + datetime.timedelta(minutes=3)}})
                            if not claimed.matched_count:
                                return jsonify({"status": "finishing", "report_pending": True, "retry_after": 2}), 202
                        try:
                            return complete()
                        finally:
                            if collection is not None:
                                collection.update_one(dict(identity, report_lease_owner=owner),
                                    {"$unset": {"report_lease_owner": "", "report_lease_until": ""}})
            entry = (_pool.submit(run), time.monotonic())
            _jobs[key] = entry
    try:
        result = entry[0].result(timeout=.05)
        if isinstance(result, tuple) and result[1] == 202:
            with _lock:
                _jobs.pop(key, None)
        return result
    except TimeoutError:
        return jsonify({"status": "finishing", "report_pending": True, "retry_after": 2}), 202
    except Exception:
        with _lock:
            _jobs.pop(key, None)
        app.logger.exception("Interview report completion failed")
        return jsonify({"error": "Your answers are saved. Please retry report generation."}), 503

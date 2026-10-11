"""System routes: index, health/readiness check, GridFS file serving.

Moved verbatim from app.py. Uses a factory (matching create_cv_routes) because
the routes need the connected database handle.
"""

import logging
import os
import threading
import time

from bson import ObjectId
from middleware.auth_middleware import token_required
from flask import Blueprint, Response, jsonify

logger = logging.getLogger(__name__)

system_bp = Blueprint("system", __name__)


def create_system_routes(db):
    # Cloud Run's HTTP probe talks directly to the container over HTTP. A 302
    # HTTPS redirect would count as success without checking dependencies.
    try:
        from flask_talisman import Talisman
        probe_options = Talisman()(force_https=False)
    except ImportError:
        probe_options = lambda view: view
    health_lock = threading.Lock()
    health_cache = {"expires": 0, "payload": {"status": "checking"}, "status": 503}
    @system_bp.route("/")
    def index():
        return "Welcome to the Interview System API. Please use the /api endpoints to interact with the system."

    # Readiness check — previously an unconditional 200 regardless of whether
    # anything downstream (Mongo) was actually reachable, which is exactly the
    # case a load balancer/orchestrator needs this endpoint to catch. Pings the
    # database with a short timeout; a slow/unreachable DB now reports 503
    # instead of a false "healthy".
    @system_bp.route("/health", methods=["GET"])
    @probe_options
    def health_check():
        if health_cache["expires"] > time.monotonic():
            return jsonify(health_cache["payload"]), health_cache["status"]
        if not health_lock.acquire(blocking=False):
            return jsonify(health_cache["payload"]), health_cache["status"]
        try:
            if health_cache["expires"] > time.monotonic():
                return jsonify(health_cache["payload"]), health_cache["status"]
            try:
                db.command("ping", maxTimeMS=2000)
                from middleware.rate_limiter import store, shared_store_required
                if shared_store_required() or os.getenv("REDIS_URL"):
                    store._client().ping()
                payload = {"status": "healthy", "database": "connected", "request_protection": "available"}
                status = 200
            except Exception as e:
                logger.warning("Readiness dependency unavailable (%s)", type(e).__name__)
                payload, status = {"status": "unhealthy", "dependencies": "unreachable"}, 503
            health_cache.update(expires=time.monotonic() + 3, payload=payload, status=status)
            return jsonify(payload), status
        finally:
            health_lock.release()


    @system_bp.route("/api/files/<gridfs_id>")
    @token_required
    def serve_gridfs_file(current_user, gridfs_id):
        try:
            import gridfs
            fs = gridfs.GridFS(db)
            file_data = fs.get(ObjectId(gridfs_id))
            metadata = getattr(file_data, "metadata", None) or {}
            if metadata.get("purpose") in ("identity_card", "canonical", "session"):
                return jsonify({"error": "Use the protected identity or interview image endpoint."}), 403
            owner = metadata.get("user_id") or getattr(file_data, "user_id", None)
            legacy_path = "gridfs://" + gridfs_id
            owned_legacy = db["users"].find_one({
                "_id": current_user["_id"],
                "$or": [{"profile_photo": legacy_path}, {"cv_path": legacy_path},
                        {"cv_uploads.file_path": legacy_path}],
            }, {"_id": 1})
            if current_user.get("user_type") != "admin" and str(owner) != str(current_user["_id"]) and not owned_legacy:
                return jsonify({"error": "File not found"}), 404
            return Response(
                file_data.read(),
                mimetype=file_data.content_type,
                headers={"Content-Disposition": f"inline; filename={file_data.filename}"}
            )
        except Exception:
            return jsonify({"error": "File not found"}), 404

    return system_bp

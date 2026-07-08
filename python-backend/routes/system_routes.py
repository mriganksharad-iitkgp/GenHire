"""System routes: index, health/readiness check, GridFS file serving.

Moved verbatim from app.py. Uses a factory (matching create_cv_routes) because
the routes need the connected database handle.
"""

import logging

from bson import ObjectId
from flask import Blueprint, Response, jsonify

logger = logging.getLogger(__name__)

system_bp = Blueprint("system", __name__)


def create_system_routes(db):
    @system_bp.route("/")
    def index():
        return "Welcome to the Interview System API. Please use the /api endpoints to interact with the system."

    # Readiness check — previously an unconditional 200 regardless of whether
    # anything downstream (Mongo) was actually reachable, which is exactly the
    # case a load balancer/orchestrator needs this endpoint to catch. Pings the
    # database with a short timeout; a slow/unreachable DB now reports 503
    # instead of a false "healthy".
    @system_bp.route("/health", methods=["GET"])
    def health_check():
        try:
            db.command("ping", maxTimeMS=2000)
            return jsonify({"status": "healthy", "database": "connected"}), 200
        except Exception as e:
            logger.warning(f"Health check failed: {e}")
            return jsonify({"status": "unhealthy", "database": "unreachable"}), 503

    @system_bp.route("/api/files/<gridfs_id>")
    def serve_gridfs_file(gridfs_id):
        try:
            import gridfs
            fs = gridfs.GridFS(db)
            file_data = fs.get(ObjectId(gridfs_id))
            return Response(
                file_data.read(),
                mimetype=file_data.content_type,
                headers={"Content-Disposition": f"inline; filename={file_data.filename}"}
            )
        except Exception:
            return jsonify({"error": "File not found"}), 404

    return system_bp

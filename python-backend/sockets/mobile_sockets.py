"""Socket.IO handlers for the mobile companion camera flow.

Moved verbatim from app.py. The phone opens a QR link (no JWT), joins the
interview's session room after the session id is validated against the
database, and relays recording status back to the desktop.
"""

from flask_socketio import join_room

from config.database import db_config
from extensions import socketio

collections = db_config.get_collections()
interviews_collection = collections["interviews"]


@socketio.on("join_mobile_session")
def handle_mobile_join(data):
    from core import config as app_config

    if not app_config.mobile_recording_enabled():
        return
    session_id = (data or {}).get("session_id")
    if not session_id:
        return
    # The mobile companion connects without a JWT (QR link), so gate the room
    # join on the session actually existing instead.
    session_exists = interviews_collection.find_one(
        {"session_id": session_id}, {"_id": 1}
    ) or collections["practice_sessions"].find_one({"session_id": session_id}, {"_id": 1})
    if not session_exists:
        return
    join_room(session_id)
    socketio.emit("mobile_connected", {"status": "connected"}, room=session_id)


@socketio.on("control_mobile_recording")
def handle_mobile_control(data):
    session_id = data.get("session_id")
    action = data.get("action")  # 'start' or 'stop'

    # Relay the command to the mobile device in the room
    socketio.emit("mobile_recording_action", {"action": action}, room=session_id)


@socketio.on("mobile_status_update")
def handle_mobile_status(data):
    session_id = data.get("session_id")
    status = data.get("status")  # e.g., 'recording', 'uploading', 'completed'
    # Relay status back to desktop to show user
    socketio.emit("mobile_status_dashboard", {"status": status}, room=session_id)

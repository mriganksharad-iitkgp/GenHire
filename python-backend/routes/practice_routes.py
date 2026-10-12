from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from controllers.practice_controller import PracticeController
from config.database import db_config
from services.interview_flow_service import serialized_session, session_lock

practice_bp = Blueprint('practice', __name__, url_prefix='/api/practice')

# Initialize practice controller
collections = db_config.get_collections()
practice_controller = PracticeController(collections)

@practice_bp.route('/start', methods=['POST', 'OPTIONS'])
@token_required
def start_practice_interview(current_user):
    """
    Start a practice interview session
    
    Form Data:
        role: str - Role type (software-engineer, data-scientist, custom, etc.)
        difficulty: str - Interview difficulty (easy, medium, hard)
        jd: file - Optional JD file for custom practice (PDF or TXT)
        cv_id: str - Optional CV ID to use (if not provided, uses primary CV or manual entry)
    """
    # Only candidates can use practice mode
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can use practice mode.'}), 403

    # Burner (invite-only) accounts are scoped to the interview they were
    # sponsored for — practice mode is a general candidate feature unrelated
    # to any specific recruiter invite, so it stays out of scope for them.
    if current_user.get('is_invite_only'):
        return jsonify({
            'error': 'Practice mode is not available on invite-only accounts. This account is scoped to the interview you were invited to.',
            'error_code': 'invite_only_scope',
        }), 403
    
    # Get files and data from request
    jd_file = request.files.get('jd')  # Optional for custom practice
    role = request.form.get('role')
    difficulty = request.form.get('difficulty', 'medium')
    cv_id = request.form.get('cv_id')  # Optional CV selection (Phase 6)
    proctoring_enabled = str(request.form.get('proctoring_enabled', 'false')).strip().lower() in ['1', 'true', 'yes', 'on']
    
    user_id = str(current_user['_id'])
    
    import datetime
    import uuid
    from routes.interview_routes import _session_payload
    with session_lock(f"practice-start:{user_id}"):
        existing = collections['practice_sessions'].find_one({'user_id': user_id,
            'status': {'$in': ['setup', 'active', 'finishing']}})
        if existing:
            if existing.get('role') != role or existing.get('difficulty') != difficulty:
                return jsonify({'error': 'Finish or close your current practice interview before starting a different one.',
                    'error_code': 'practice_in_progress', 'session_id': existing['session_id']}), 409
            return jsonify(_session_payload(existing, practice_controller.interview_api.session_manager
                if practice_controller.interview_api else None)), 200
        lease_id = uuid.uuid4().hex
        now = datetime.datetime.utcnow()
        claimed = collections['users'].update_one({'_id': current_user['_id'],
            '$or': [{'practice_start_lease': {'$exists': False}}, {'practice_start_lease.expires_at': {'$lt': now}}]},
            {'$set': {'practice_start_lease': {'id': lease_id, 'expires_at': now + datetime.timedelta(minutes=2)}}})
        if not claimed.modified_count:
            return jsonify({'error': 'Your practice interview is already starting. Please retry in a moment.',
                'error_code': 'practice_start_in_progress'}), 409
        try:
            existing = collections['practice_sessions'].find_one({'user_id': user_id,
                'status': {'$in': ['setup', 'active', 'finishing']}})
            if existing:
                return jsonify(_session_payload(existing, practice_controller.interview_api.session_manager
                    if practice_controller.interview_api else None)), 200
            result, status_code = practice_controller.start_practice(
                user_id=user_id, jd_file=jd_file, role=role, difficulty=difficulty,
                cv_id=cv_id, proctoring_enabled=proctoring_enabled)
        finally:
            collections['users'].update_one({'_id': current_user['_id'], 'practice_start_lease.id': lease_id},
                {'$unset': {'practice_start_lease': ''}})
    
    return jsonify(result), status_code

@practice_bp.route('/<session_id>/answer', methods=['POST', 'OPTIONS'])
@token_required
@serialized_session
def submit_practice_answer(current_user, session_id):
    """Submit an answer in a practice interview"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    data = request.get_json() or {}
    question = data.get('question')
    answer = data.get('answer')
    
    if not question or answer is None:
        return jsonify({'error': 'Question and answer are required'}), 400
    
    user_id = str(current_user['_id'])
    
    try:
        result, status_code = practice_controller.submit_answer(
            session_id=session_id,
            user_id=user_id,
            question=question,
            answer=answer
        )
        
        return jsonify(result), status_code
    except Exception as e:
        print(f"Error in submit_practice_answer: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@practice_bp.route('/<session_id>/end', methods=['POST', 'OPTIONS'])
@token_required
def end_practice_interview(current_user, session_id):
    """End a practice interview session"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    user_id = str(current_user['_id'])
    from services.interview_completion_service import complete_in_background
    try:
        def complete():
            result, status_code = practice_controller.end_practice(session_id=session_id, user_id=user_id)
            return jsonify(result), status_code
        doc = practice_controller.collections["practice_sessions"].find_one({"session_id": session_id, "user_id": user_id})
        if not doc:
            return jsonify({"error": "Practice session not found"}), 404
        if doc.get("status") in {"completed", "abandoned", "terminated"}:
            from services.interview_flow_service import result_payload
            return jsonify(result_payload(doc))
        return complete_in_background(("practice", user_id, session_id), complete,
                                      practice_controller.collections["practice_sessions"])
    except Exception as e:
        print(f"Error in end_practice_interview: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@practice_bp.route('/history', methods=['GET', 'OPTIONS'])
@token_required
def get_practice_history(current_user):
    """Get user's practice interview history"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    user_id = str(current_user['_id'])
    
    result, status_code = practice_controller.get_history(user_id)
    
    return jsonify(result), status_code

@practice_bp.route('/<session_id>/report', methods=['GET', 'OPTIONS'])
@token_required
def get_practice_report(current_user, session_id):
    """Get detailed report for a specific practice interview"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    user_id = str(current_user['_id'])
    
    try:
        result, status_code = practice_controller.get_practice_report(session_id, user_id)
        return jsonify(result), status_code
    except Exception as e:
        print(f"Error in get_practice_report: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from middleware.auth_middleware import token_required
from controllers.practice_controller import PracticeController
from config.database import db_config

practice_bp = Blueprint('practice', __name__, url_prefix='/api/practice')

# Initialize practice controller
collections = db_config.get_collections()
practice_controller = PracticeController(collections)

@practice_bp.route('/start', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)
@token_required
def start_practice_interview(current_user):
    """Start a practice interview session"""
    # Only candidates can use practice mode
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can use practice mode.'}), 403
    
    # Get files and data from request (CV not required - use profile CV)
    jd_file = request.files.get('jd')  # Optional for custom practice
    role = request.form.get('role')
    difficulty = request.form.get('difficulty', 'medium')
    
    user_id = str(current_user['_id'])
    
    result, status_code = practice_controller.start_practice(
        user_id=user_id,
        jd_file=jd_file,
        role=role,
        difficulty=difficulty
    )
    
    return jsonify(result), status_code

@practice_bp.route('/<session_id>/answer', methods=['POST', 'OPTIONS'])
@cross_origin(origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)
@token_required
def submit_practice_answer(current_user, session_id):
    """Submit an answer in a practice interview"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    data = request.get_json() or {}
    question = data.get('question')
    answer = data.get('answer')
    
    if not question or not answer:
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
@cross_origin(origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)
@token_required
def end_practice_interview(current_user, session_id):
    """End a practice interview session"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized.'}), 403
    
    user_id = str(current_user['_id'])
    
    try:
        result, status_code = practice_controller.end_practice(
            session_id=session_id,
            user_id=user_id
        )
        
        return jsonify(result), status_code
    except Exception as e:
        print(f"Error in end_practice_interview: {str(e)}")
        import traceback
        print(f"Full traceback: {traceback.format_exc()}")
        return jsonify({'error': 'Internal server error', 'details': str(e)}), 500

@practice_bp.route('/history', methods=['GET', 'OPTIONS'])
@cross_origin(origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)
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
@cross_origin(origins=["http://localhost:3000", "http://127.0.0.1:3000"], supports_credentials=True)
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

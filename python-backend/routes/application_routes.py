from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import os
import datetime
from controllers.application_controller import ApplicationController
from middleware.auth_middleware import token_required
from config.database import db_config
from bson import ObjectId

application_bp = Blueprint('applications', __name__, url_prefix='/api')

# Initialize application controller
collections = db_config.get_collections()
application_controller = ApplicationController(collections)

@application_bp.route('/jobs/<job_id>/apply', methods=['POST'])
@cross_origin()
@token_required
def apply_for_job(current_user, job_id):
    """Apply for a job (candidates only)"""
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can apply for jobs.'}), 403
    
    data = request.get_json() or {}
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.apply_for_job(job_id, user_id, data, current_user)
    return jsonify(result), status_code

@application_bp.route('/jobs/<job_id>/withdraw', methods=['DELETE'])
@cross_origin()
@token_required
def withdraw_application(current_user, job_id):
    """Withdraw application for a job (candidates only)"""
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can withdraw applications.'}), 403
    
    user_id = str(current_user['_id'])
    result, status_code = application_controller.withdraw_application(job_id, user_id)
    return jsonify(result), status_code

@application_bp.route('/applications', methods=['GET'])
@cross_origin()
@token_required
def get_applications(current_user):
    """Get applications - candidates see their own, recruiters see applications for their jobs"""
    # Normalize user_type with default for legacy users
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_applications(user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/status', methods=['PUT'])
@cross_origin()
@token_required
def update_application_status(current_user, application_id):
    """Update application status (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update application status.'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    recruiter_id = str(current_user['_id'])
    
    result, status_code = application_controller.update_application_status(application_id, recruiter_id, new_status)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/cv', methods=['GET'])
@cross_origin()
@token_required
def get_application_cv(current_user, application_id):
    """Stream the candidate's CV PDF for a given application (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can view candidate CVs.'}), 403

    # Find the application
    try:
        app_doc = collections['applications'].find_one({'_id': ObjectId(application_id)})
    except Exception:
        return jsonify({'error': 'Invalid application id'}), 400

    if not app_doc:
        return jsonify({'error': 'Application not found'}), 404

    # Verify recruiter owns the job
    job = collections['jobs'].find_one({'_id': ObjectId(app_doc['job_id'])})
    if not job or job.get('created_by') != str(current_user['_id']):
        return jsonify({'error': 'Unauthorized to view this CV'}), 403

    # Look up candidate user for CV path
    try:
        student_user = collections['users'].find_one({'_id': ObjectId(app_doc['student_id'])})
    except Exception:
        student_user = None

    if not student_user:
        return jsonify({'error': 'Candidate not found'}), 404

    cv_path = student_user.get('cv_path')
    if not cv_path or not os.path.exists(cv_path):
        return jsonify({'error': 'CV not found'}), 404

    # Stream the PDF
    return send_file(cv_path)

@application_bp.route('/applications/<application_id>', methods=['GET'])
@cross_origin()
@token_required
def get_application_by_id(current_user, application_id):
    """Get a single application document by id with job details"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_application_by_id(application_id, user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/interview-report', methods=['GET'])
@cross_origin()
@token_required
def get_interview_report(current_user, application_id):
    """Return the latest interview report for a given application"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_interview_report(application_id, user_id, user_type)
    return jsonify(result), status_code

# Debug endpoints
@application_bp.route('/debug/applications', methods=['GET'])
@cross_origin()
def debug_applications():
    """Debug endpoint to see what applications exist"""
    applications = list(collections['applications'].find({}))
    for app in applications:
        app['_id'] = str(app['_id'])
        if isinstance(app.get('applied_at'), datetime.datetime):
            app['applied_at'] = app['applied_at'].isoformat()
        if isinstance(app.get('updated_at'), datetime.datetime):
            app['updated_at'] = app['updated_at'].isoformat()
    return jsonify({'applications': applications, 'count': len(applications)})

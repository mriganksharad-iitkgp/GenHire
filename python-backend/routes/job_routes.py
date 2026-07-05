from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import datetime
import json
from controllers.job_controller import JobController
from middleware.auth_middleware import token_required, verified_required
from config.database import db_config

job_bp = Blueprint('jobs', __name__, url_prefix='/api')

# Initialize job controller
collections = db_config.get_collections()
job_controller = JobController(collections)

@job_bp.route('/jobs', methods=['GET'])
@cross_origin()
@token_required
def get_jobs(current_user):
    """Get all jobs (for recruiters) or available jobs (for candidates)"""
    # Normalize optional search input even though the current candidate UI
    # filters locally. This keeps older/deployed clients from passing None.
    search_query = str(request.args.get('query') or request.args.get('search') or '').strip()
    user_type = current_user.get('user_type', 'candidate')
    user_id = str(current_user['_id'])
    
    result, status_code = job_controller.get_jobs(user_type, user_id, search_query)
    return jsonify(result), status_code

@job_bp.route('/jobs', methods=['POST'])
@cross_origin()
@token_required
@verified_required
def create_job(current_user):
    """
    Create a new job posting (verified recruiters only)
    
    Accepts either:
    - JSON data (application/json) - traditional job creation
    - Form data (multipart/form-data) - with optional JD PDF file (Phase 4)
    
    Form Data (if using multipart/form-data):
        jd_file: file - Optional JD PDF/TXT file
        ... other job fields as form fields ...
    """
    if current_user.get('user_type') not in ['recruiter', 'admin']:
        return jsonify({'error': 'Unauthorized. Only recruiters can create jobs.'}), 403
    
    recruiter_id = str(current_user['_id'])

    # Check if request has files (multipart/form-data)
    jd_file = request.files.get('jd_file')

    # Get job data from either JSON or form data
    if request.is_json:
        data = request.get_json()
    else:
        # Convert form data to dictionary. Array fields are sent as a JSON
        # array string (e.g. '["React","Node.js"]') so multi-line values
        # (responsibilities/requirements/benefits) survive intact; fall back
        # to comma-splitting for older/plain-string clients.
        data = request.form.to_dict()
        for field in ['skills', 'responsibilities', 'requirements', 'benefits']:
            raw = data.get(field)
            if isinstance(raw, str):
                try:
                    parsed = json.loads(raw)
                    data[field] = parsed if isinstance(parsed, list) else [str(parsed)]
                except (ValueError, TypeError):
                    data[field] = [item.strip() for item in raw.split(',') if item.strip()]

    result, status_code = job_controller.create_job(recruiter_id, data, current_user, jd_file=jd_file)
    return jsonify(result), status_code

@job_bp.route('/jobs/generate-ai', methods=['POST'])
@cross_origin()
@token_required
def generate_jd_with_ai(current_user):
    """Generate a complete job description using AI — from a text prompt, an
    uploaded JD file (parsed and structured), or both. Accepts JSON
    ({"prompt": "..."}) or multipart/form-data (prompt field + jd_file)."""
    if current_user.get('user_type') not in ['recruiter', 'admin']:
        return jsonify({'error': 'Unauthorized. Only recruiters can generate job descriptions.'}), 403

    jd_file = request.files.get('jd_file')
    if request.is_json:
        data = request.get_json() or {}
        prompt_text = str(data.get('prompt') or '').strip()
    else:
        prompt_text = str(request.form.get('prompt') or '').strip()

    if not prompt_text and not jd_file:
        return jsonify({'error': 'Please provide a prompt describing the job role, or upload a JD file'}), 400
    if prompt_text and len(prompt_text) < 3:
        return jsonify({'error': 'Prompt too short. Please describe the role you want to hire for.'}), 400
    if len(prompt_text) > 2000:
        return jsonify({'error': 'Prompt too long. Please keep it under 2000 characters.'}), 400

    result, status_code = job_controller.generate_jd_with_ai(
        prompt_text, str(current_user.get('_id')), jd_file=jd_file
    )
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>/jd-download', methods=['GET'])
@cross_origin()
@token_required
def get_jd_download_url(current_user, job_id):
    """Get a signed download URL for the recruiter-uploaded JD PDF."""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    result, status_code = job_controller.get_jd_download_url(job_id, user_id, user_type)
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>', methods=['GET'])
@cross_origin()
@token_required
def get_job_details(current_user, job_id):
    """Get details for a single job"""
    user_type = current_user.get('user_type', 'candidate')
    user_id = str(current_user['_id'])
    
    result, status_code = job_controller.get_job_details(job_id, user_type, user_id)
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>', methods=['PUT'])
@cross_origin()
@token_required
@verified_required
def update_job(current_user, job_id):
    """Update a job posting (verified recruiters only)"""
    if current_user.get('user_type') not in ['recruiter', 'admin']:
        return jsonify({'error': 'Unauthorized. Only recruiters can update jobs.'}), 403
    
    data = request.get_json()
    recruiter_id = str(current_user['_id'])
    
    result, status_code = job_controller.update_job(job_id, recruiter_id, data)
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>', methods=['DELETE'])
@cross_origin()
@token_required
@verified_required
def delete_job(current_user, job_id):
    """Delete a job posting (verified recruiters only)"""
    if current_user.get('user_type') not in ['recruiter', 'admin']:
        return jsonify({'error': 'Unauthorized. Only recruiters can delete jobs.'}), 403
    
    recruiter_id = str(current_user['_id'])
    result, status_code = job_controller.delete_job(job_id, recruiter_id)
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>/applications', methods=['GET'])
@cross_origin()
@token_required
def get_job_applications(current_user, job_id):
    """Get all applications for a specific job (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can view job applications.'}), 403
    
    recruiter_id = str(current_user['_id'])
    result, status_code = job_controller.get_job_applications(job_id, recruiter_id)
    return jsonify(result), status_code

# Remove hardcoded sample jobs from database
@job_bp.route('/remove-sample-jobs', methods=['DELETE'])
@cross_origin()
def remove_sample_jobs():
    """Remove hardcoded sample jobs created by 'system'"""
    collections = db_config.get_collections()
    jobs_collection = collections['jobs']
    
    # Remove jobs created by 'system'
    result = jobs_collection.delete_many({'created_by': 'system'})
    
    return jsonify({'message': f'Removed {result.deleted_count} sample jobs'}), 200

@job_bp.route('/test-jobs', methods=['GET'])
@cross_origin()
def test_jobs():
    """Test endpoint to check jobs without authentication"""
    collections = db_config.get_collections()
    jobs_collection = collections['jobs']
    
    jobs = list(jobs_collection.find())
    for job in jobs:
        job['_id'] = str(job['_id'])
    return jsonify({'jobs': jobs, 'count': len(jobs)}), 200

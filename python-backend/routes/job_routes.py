from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
import datetime
from controllers.job_controller import JobController
from middleware.auth_middleware import token_required
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
    user_type = current_user.get('user_type', 'candidate')
    user_id = str(current_user['_id'])
    
    result, status_code = job_controller.get_jobs(user_type, user_id)
    return jsonify(result), status_code

@job_bp.route('/jobs', methods=['POST'])
@cross_origin()
@token_required
def create_job(current_user):
    """Create a new job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can create jobs.'}), 403
    
    data = request.get_json()
    recruiter_id = str(current_user['_id'])
    
    result, status_code = job_controller.create_job(recruiter_id, data, current_user)
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
def update_job(current_user, job_id):
    """Update a job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update jobs.'}), 403
    
    data = request.get_json()
    recruiter_id = str(current_user['_id'])
    
    result, status_code = job_controller.update_job(job_id, recruiter_id, data)
    return jsonify(result), status_code

@job_bp.route('/jobs/<job_id>', methods=['DELETE'])
@cross_origin()
@token_required
def delete_job(current_user, job_id):
    """Delete a job posting (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
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

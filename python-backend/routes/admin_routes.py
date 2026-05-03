from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required, admin_required

admin_bp = Blueprint('admin', __name__)

# Controller will be initialized in app.py
admin_controller = None

def init_admin_routes(controller):
    global admin_controller
    admin_controller = controller


@admin_bp.route('/stats', methods=['GET'])
@token_required
@admin_required
def get_dashboard_stats(current_user):
    """Get platform statistics for admin dashboard"""
    result, status = admin_controller.get_dashboard_stats(current_user)
    return jsonify(result), status


@admin_bp.route('/users', methods=['GET'])
@token_required
@admin_required
def get_users(current_user):
    """Get list of users with optional filters"""
    filters = {
        'user_type': request.args.get('user_type'),
        'is_verified': request.args.get('is_verified'),
        'search': request.args.get('search'),
        'page': request.args.get('page', 1),
        'limit': request.args.get('limit', 20)
    }
    
    # Convert is_verified to boolean if provided
    if filters['is_verified'] is not None:
        filters['is_verified'] = filters['is_verified'].lower() == 'true'
    
    result, status = admin_controller.get_users(current_user, filters)
    return jsonify(result), status


@admin_bp.route('/users/<user_id>', methods=['GET'])
@token_required
@admin_required
def get_user_details(current_user, user_id):
    """Get detailed information about a specific user"""
    result, status = admin_controller.get_user_details(current_user, user_id)
    return jsonify(result), status


@admin_bp.route('/candidates/<candidate_id>', methods=['GET'])
@token_required
@admin_required
def get_candidate_details(current_user, candidate_id):
    """Get comprehensive candidate details with applications and history"""
    result, status = admin_controller.get_candidate_details(current_user, candidate_id)
    return jsonify(result), status


@admin_bp.route('/candidates/<candidate_id>', methods=['PUT'])
@token_required
@admin_required
def update_candidate(current_user, candidate_id):
    """Update candidate details"""
    data = request.get_json() or {}
    result, status = admin_controller.update_candidate(current_user, candidate_id, data)
    return jsonify(result), status


@admin_bp.route('/recruiters/<recruiter_id>', methods=['GET'])
@token_required
@admin_required
def get_recruiter_details(current_user, recruiter_id):
    """Get comprehensive recruiter details with jobs and statistics"""
    result, status = admin_controller.get_recruiter_details(current_user, recruiter_id)
    return jsonify(result), status


@admin_bp.route('/recruiters/<recruiter_id>', methods=['PUT'])
@token_required
@admin_required
def update_recruiter(current_user, recruiter_id):
    """Update recruiter details"""
    data = request.get_json() or {}
    result, status = admin_controller.update_recruiter(current_user, recruiter_id, data)
    return jsonify(result), status


@admin_bp.route('/pending-recruiters', methods=['GET'])
@token_required
@admin_required
def get_pending_recruiters(current_user):
    """Get list of recruiters pending verification"""
    result, status = admin_controller.get_pending_recruiters(current_user)
    return jsonify(result), status


@admin_bp.route('/users/<recruiter_id>/verify', methods=['PUT'])
@token_required
@admin_required
def verify_recruiter(current_user, recruiter_id):
    """Verify a recruiter account"""
    result, status = admin_controller.verify_recruiter(current_user, recruiter_id)
    return jsonify(result), status


@admin_bp.route('/users/<recruiter_id>/reject', methods=['PUT'])
@token_required
@admin_required
def reject_recruiter(current_user, recruiter_id):
    """Reject/suspend a recruiter account"""
    data = request.get_json() or {}
    reason = data.get('reason')
    result, status = admin_controller.reject_recruiter(current_user, recruiter_id, reason)
    return jsonify(result), status


@admin_bp.route('/users/<user_id>/permissions', methods=['PUT'])
@token_required
@admin_required
def update_user_permissions(current_user, user_id):
    """Update user permissions"""
    data = request.get_json()
    if not data or 'permissions' not in data:
        return jsonify({'error': 'Permissions array is required'}), 400
    
    permissions = data['permissions']
    if not isinstance(permissions, list):
        return jsonify({'error': 'Permissions must be an array'}), 400
    
    result, status = admin_controller.update_user_permissions(current_user, user_id, permissions)
    return jsonify(result), status


@admin_bp.route('/users/<user_id>/user-type', methods=['PUT'])
@token_required
@admin_required
def update_user_type(current_user, user_id):
    """Update user type (promote/demote users)"""
    data = request.get_json()
    if not data or 'user_type' not in data:
        return jsonify({'error': 'User type is required'}), 400
    
    new_user_type = data['user_type']
    result, status = admin_controller.update_user_type(current_user, user_id, new_user_type)
    return jsonify(result), status


@admin_bp.route('/users/<user_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_user(current_user, user_id):
    """Delete a user account"""
    result, status = admin_controller.delete_user(current_user, user_id)
    return jsonify(result), status


@admin_bp.route('/permissions', methods=['GET'])
@token_required
@admin_required
def get_available_permissions(current_user):
    """Get list of available permissions"""
    result, status = admin_controller.get_available_permissions(current_user)
    return jsonify(result), status


@admin_bp.route('/jobs', methods=['GET'])
@token_required
@admin_required
def get_all_jobs(current_user):
    """Get all jobs with filters"""
    filters = {
        'status': request.args.get('status'),
        'recruiter_id': request.args.get('recruiter_id'),
        'search': request.args.get('search'),
        'page': request.args.get('page', 1),
        'limit': request.args.get('limit', 20)
    }
    result, status = admin_controller.get_all_jobs(current_user, filters)
    return jsonify(result), status


@admin_bp.route('/jobs/<job_id>', methods=['GET'])
@token_required
@admin_required
def get_job_details(current_user, job_id):
    """Get comprehensive job details with applicants"""
    result, status = admin_controller.get_job_details(current_user, job_id)
    return jsonify(result), status


@admin_bp.route('/jobs/<job_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_job(current_user, job_id):
    """Delete a job and its applications"""
    result, status = admin_controller.delete_job(current_user, job_id)
    return jsonify(result), status


@admin_bp.route('/applications/<application_id>/status', methods=['PUT'])
@token_required
@admin_required
def update_application_status(current_user, application_id):
    """Update application status"""
    data = request.get_json()
    if not data or 'status' not in data:
        return jsonify({'error': 'Status is required'}), 400
    
    result, status = admin_controller.update_application_status(current_user, application_id, data['status'])
    return jsonify(result), status


@admin_bp.route('/applications/<application_id>', methods=['GET'])
@token_required
@admin_required
def get_application_details(current_user, application_id):
    """Get comprehensive application details"""
    result, status = admin_controller.get_application_details(current_user, application_id)
    return jsonify(result), status


@admin_bp.route('/applications/<application_id>', methods=['PUT'])
@token_required
@admin_required
def update_application(current_user, application_id):
    """Update application details"""
    data = request.get_json() or {}
    result, status = admin_controller.update_application(current_user, application_id, data)
    return jsonify(result), status


@admin_bp.route('/applications/<application_id>', methods=['DELETE'])
@token_required
@admin_required
def delete_application(current_user, application_id):
    """Delete an application"""
    result, status = admin_controller.delete_application(current_user, application_id)
    return jsonify(result), status


@admin_bp.route('/jobs/<job_id>', methods=['PUT'])
@token_required
@admin_required
def update_job(current_user, job_id):
    """Update job details"""
    data = request.get_json() or {}
    result, status = admin_controller.update_job(current_user, job_id, data)
    return jsonify(result), status


@admin_bp.route('/candidates/<candidate_id>/cv', methods=['GET'])
@token_required
@admin_required
def get_candidate_cv(current_user, candidate_id):
    """Get candidate CV details and file path"""
    result, status = admin_controller.get_candidate_cv(current_user, candidate_id)
    return jsonify(result), status


@admin_bp.route('/candidates/<candidate_id>/cv', methods=['DELETE'])
@token_required
@admin_required
def delete_candidate_cv(current_user, candidate_id):
    """Delete candidate CV"""
    result, status = admin_controller.delete_candidate_cv(current_user, candidate_id)
    return jsonify(result), status


@admin_bp.route('/system/stats', methods=['GET'])
@token_required
@admin_required
def get_system_stats(current_user):
    """Get comprehensive system statistics"""
    result, status = admin_controller.get_system_stats(current_user)
    return jsonify(result), status


@admin_bp.route('/candidates/<candidate_id>/practice-history', methods=['GET'])
@token_required
@admin_required
def get_candidate_practice_history(current_user, candidate_id):
    """Get practice interview history for a candidate"""
    result, status = admin_controller.get_candidate_practice_history(current_user, candidate_id)
    return jsonify(result), status


@admin_bp.route('/applications/<application_id>/report', methods=['GET'])
@token_required
@admin_required
def get_application_report(current_user, application_id):
    """Get interview report for an application"""
    result, status = admin_controller.get_application_report(current_user, application_id)
    return jsonify(result), status


@admin_bp.route('/practice/<session_id>/report', methods=['GET'])
@token_required
@admin_required
def get_practice_report(current_user, session_id):
    """Get practice interview report"""
    result, status = admin_controller.get_practice_report(current_user, session_id)
    return jsonify(result), status


@admin_bp.route('/cost-statistics', methods=['GET'])
@token_required
@admin_required
def get_admin_cost_statistics(current_user):
    """Get cost statistics for all recruiters - Admin only"""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_cost_statistics(current_user, period, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/candidates/usage', methods=['GET'])
@token_required
@admin_required
def get_candidate_usage_summary(current_user):
    """Get timeline-based usage summary for each candidate."""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_candidate_usage_summary(current_user, period, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/candidates/<candidate_id>/usage-lines', methods=['GET'])
@token_required
@admin_required
def get_candidate_usage_lines(current_user, candidate_id):
    """Get timeline-based usage line items for one candidate."""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1)
    limit = request.args.get('limit', 50)
    search = request.args.get('search', '')
    result, status = admin_controller.get_candidate_usage_lines(current_user, candidate_id, period, start_date, end_date, page, limit, search)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/recruiters/usage', methods=['GET'])
@token_required
@admin_required
def get_recruiter_usage_summary(current_user):
    """Get timeline-based usage summary for each recruiter."""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_recruiter_usage_summary(current_user, period, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/recruiters/<recruiter_id>/usage-lines', methods=['GET'])
@token_required
@admin_required
def get_recruiter_usage_lines(current_user, recruiter_id):
    """Get timeline-based usage line items for one recruiter."""
    period = request.args.get('period', 'month')
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    page = request.args.get('page', 1)
    limit = request.args.get('limit', 50)
    search = request.args.get('search', '')
    result, status = admin_controller.get_recruiter_usage_lines(current_user, recruiter_id, period, start_date, end_date, page, limit, search)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/candidates/credit-summary', methods=['GET'])
@token_required
@admin_required
def get_candidate_credit_summary(current_user):
    """Get timeline-based credit summary for each candidate."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_candidate_credit_summary(current_user, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/candidates/<candidate_id>/credit-lines', methods=['GET'])
@token_required
@admin_required
def get_candidate_credit_lines(current_user, candidate_id):
    """Get timeline-based credit line items for one candidate."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_candidate_credit_lines(current_user, candidate_id, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/recruiters/credit-summary', methods=['GET'])
@token_required
@admin_required
def get_recruiter_credit_summary(current_user):
    """Get timeline-based credit summary for each recruiter."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_recruiter_credit_summary(current_user, start_date, end_date)
    return jsonify(result), status


@admin_bp.route('/cost-statistics/recruiters/<recruiter_id>/credit-lines', methods=['GET'])
@token_required
@admin_required
def get_recruiter_credit_lines(current_user, recruiter_id):
    """Get timeline-based credit line items for one recruiter."""
    start_date = request.args.get('start_date')
    end_date = request.args.get('end_date')
    result, status = admin_controller.get_recruiter_credit_lines(current_user, recruiter_id, start_date, end_date)
    return jsonify(result), status

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

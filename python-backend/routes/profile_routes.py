from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.profile_controller import ProfileController
from middleware.auth_middleware import token_required
from config.database import db_config

profile_bp = Blueprint('profile', __name__, url_prefix='/api')

# Initialize profile controller
collections = db_config.get_collections()
profile_controller = ProfileController(collections)

@profile_bp.route('/profile', methods=['GET'])
@cross_origin()
@token_required
def get_profile(current_user):
    """Get user profile data"""
    result, status_code = profile_controller.get_profile(str(current_user['_id']))
    return jsonify(result), status_code

@profile_bp.route('/profile', methods=['PUT'])
@cross_origin()
@token_required
def update_profile(current_user):
    """Update user profile data"""
    data = request.get_json()
    result, status_code = profile_controller.update_profile(str(current_user['_id']), data)
    return jsonify(result), status_code

@profile_bp.route('/company-profile', methods=['PUT'])
@cross_origin()
@token_required
def update_company_profile(current_user):
    """Update company profile data for recruiters"""
    data = request.get_json()
    result, status_code = profile_controller.update_company_profile(str(current_user['_id']), data)
    return jsonify(result), status_code

@profile_bp.route('/cv-details', methods=['GET'])
@cross_origin()
@token_required
def get_cv_details(current_user):
    """Get CV details for the current user"""
    result, status_code = profile_controller.get_cv_details(str(current_user['_id']))
    return jsonify(result), status_code

@profile_bp.route('/cv-details', methods=['PUT'])
@cross_origin()
@token_required
def update_cv_details(current_user):
    """Update CV details for the current user"""
    data = request.get_json()
    result, status_code = profile_controller.update_cv_details(str(current_user['_id']), data)
    return jsonify(result), status_code

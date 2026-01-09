from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.auth_controller import AuthController
from middleware.auth_middleware import token_required
from config.database import db_config

auth_bp = Blueprint('auth', __name__, url_prefix='/api')

# Initialize auth controller
collections = db_config.get_collections()
auth_controller = AuthController(collections)

@auth_bp.route('/register', methods=['POST'])
@cross_origin()
def register():
    """User registration endpoint"""
    data = request.get_json()
    result, status_code = auth_controller.register_user(data)
    return jsonify(result), status_code

@auth_bp.route('/login', methods=['POST'])
@cross_origin()
def login():
    """User login endpoint"""
    data = request.get_json()
    email = data.get('email')
    password = data.get('password')
    user_type = data.get('userType', 'candidate')
    
    result, status_code = auth_controller.login_user(email, password, user_type)
    return jsonify(result), status_code

@auth_bp.route('/me', methods=['GET'])
@cross_origin()
@token_required
def get_current_user(current_user):
    """Get current user information"""
    user_info = auth_controller.get_current_user_info(current_user)
    return jsonify(user_info)

@auth_bp.route('/verify-email', methods=['POST'])
@cross_origin()
def verify_email():
    """Verify user's email address"""
    data = request.get_json()
    token = data.get('token')
    
    if not token:
        return jsonify({'error': 'Verification token is required'}), 400
    
    result, status_code = auth_controller.verify_email(token)
    return jsonify(result), status_code

@auth_bp.route('/resend-verification', methods=['POST'])
@cross_origin()
def resend_verification():
    """Resend verification email"""
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    result, status_code = auth_controller.resend_verification_email(email)
    return jsonify(result), status_code

@auth_bp.route('/forgot-password', methods=['POST'])
@cross_origin()
def forgot_password():
    """Request password reset email"""
    data = request.get_json()
    email = data.get('email')
    
    if not email:
        return jsonify({'error': 'Email is required'}), 400
    
    result, status_code = auth_controller.request_password_reset(email)
    return jsonify(result), status_code

@auth_bp.route('/reset-password', methods=['POST'])
@cross_origin()
def reset_password():
    """Reset password using reset token"""
    data = request.get_json()
    token = data.get('token')
    new_password = data.get('password')
    confirm_password = data.get('confirmPassword')
    
    if not token:
        return jsonify({'error': 'Reset token is required'}), 400
    
    result, status_code = auth_controller.reset_password(token, new_password, confirm_password)
    return jsonify(result), status_code

@auth_bp.route('/google-oauth', methods=['POST'])
@cross_origin()
def google_oauth():
    """Authenticate or create user with Google OAuth"""
    data = request.get_json()
    token = data.get('token')
    user_type = data.get('userType', 'candidate')

    if not token:
        return jsonify({'error': 'Google token is required'}), 400

    # Pass additional user data for recruiter onboarding
    result, status_code = auth_controller.google_oauth_login(token, user_type, data)
    return jsonify(result), status_code
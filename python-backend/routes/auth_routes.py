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

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.file_controller import FileController
from middleware.auth_middleware import token_required, admin_required
from config.database import db_config
from bson import ObjectId

file_bp = Blueprint('files', __name__, url_prefix='/api')

# Initialize file controller
collections = db_config.get_collections()
file_controller = FileController(collections)

@file_bp.route('/upload', methods=['POST'])
@cross_origin()
def upload_files():
    """Handle JD and CV file uploads"""
    if "jd" not in request.files or "cv" not in request.files:
        return jsonify({"error": "Both JD and CV files are required"}), 400

    jd_file = request.files["jd"]
    cv_file = request.files["cv"]
    
    result, status_code = file_controller.upload_files(jd_file, cv_file)
    return jsonify(result), status_code

@file_bp.route('/upload-cv', methods=['POST'])
@cross_origin()
@token_required
def upload_cv(current_user):
    """Upload CV for a specific user"""
    if 'cv' not in request.files:
        return jsonify({'error': 'No CV file provided'}), 400
    
    cv_file = request.files['cv']
    user_id = current_user['_id']
    
    result, status_code = file_controller.upload_cv(user_id, cv_file)
    return jsonify(result), status_code

@file_bp.route('/upload-photo', methods=['POST'])
@cross_origin()
@token_required
def upload_photo(current_user):
    """Upload profile photo for a user"""
    if 'photo' not in request.files:
        return jsonify({'error': 'No photo file provided'}), 400
    
    photo_file = request.files['photo']
    user_id = current_user['_id']
    
    result, status_code = file_controller.upload_photo(user_id, photo_file)
    return jsonify(result), status_code

@file_bp.route('/view-file', methods=['GET'])
@cross_origin()
def view_file():
    """View a file from the server by given file path"""
    file_path = request.args.get("path")
    if not file_path:
        return jsonify({"error": "Missing 'path' query parameter"}), 400

    return file_controller.serve_file(file_path)

@file_bp.route('/download-cv', methods=['GET'])
@cross_origin()
@token_required
def download_cv(current_user):
    """Download user's CV"""
    user_id = current_user['_id']
    return file_controller.download_cv(user_id)

@file_bp.route('/view-cv', methods=['GET'])
@cross_origin()
@token_required
def view_cv(current_user):
    """View user's CV in browser"""
    user_id = current_user['_id']
    return file_controller.view_cv(user_id)

@file_bp.route('/view-photo', methods=['GET'])
@cross_origin()
@token_required
def view_photo(current_user):
    """View user's profile photo"""
    user_id = current_user['_id']
    return file_controller.view_photo(user_id)


# Admin routes for viewing files by user ID
@file_bp.route('/admin/cv/<user_id>', methods=['GET'])
@cross_origin()
@token_required
@admin_required
def admin_view_cv(current_user, user_id):
    """Admin: View any user's CV by user ID"""
    return file_controller.view_cv_by_id(user_id)


@file_bp.route('/admin/photo/<user_id>', methods=['GET'])
@cross_origin()
@token_required
@admin_required
def admin_view_photo(current_user, user_id):
    """Admin: View any user's profile photo by user ID"""
    return file_controller.view_photo_by_id(user_id)

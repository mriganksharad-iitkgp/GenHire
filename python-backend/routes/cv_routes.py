"""
CV Routes - API endpoints for managing multiple CV uploads
"""

from flask import Blueprint, request, jsonify
from middleware.auth_middleware import token_required
from controllers.cv_controller import CVController

def create_cv_routes(db_collections):
    """Create CV management routes"""
    cv_bp = Blueprint('cv', __name__)
    cv_controller = CVController(db_collections)
    
    @cv_bp.route('/upload', methods=['POST'])
    @token_required
    def upload_cv(current_user):
        """Upload a new CV PDF"""
        try:
            # Only candidates can upload CVs
            if current_user.get('user_type') != 'candidate':
                return jsonify({'error': 'Only candidates can upload CVs'}), 403
            
            # Check if file is in request
            if 'cv_file' not in request.files:
                return jsonify({'error': 'No file provided'}), 400
            
            cv_file = request.files['cv_file']
            is_primary = request.form.get('is_primary', 'false').lower() == 'true'
            
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.upload_cv(user_id, cv_file, is_primary)
            
            return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Upload failed: {str(e)}'}), 500
    
    @cv_bp.route('/list', methods=['GET'])
    @token_required
    def list_cvs(current_user):
        """Get list of all CVs for current user"""
        try:
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.list_cvs(user_id)
            
            return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Failed to list CVs: {str(e)}'}), 500
    
    @cv_bp.route('/<cv_id>', methods=['GET'])
    @token_required
    def get_cv(current_user, cv_id):
        """Get specific CV details"""
        try:
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.get_cv(user_id, cv_id)
            
            return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Failed to get CV: {str(e)}'}), 500
    
    @cv_bp.route('/<cv_id>', methods=['DELETE'])
    @token_required
    def delete_cv(current_user, cv_id):
        """Delete a CV"""
        try:
            # Only candidates can delete their CVs
            if current_user.get('user_type') != 'candidate':
                return jsonify({'error': 'Only candidates can delete CVs'}), 403
            
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.delete_cv(user_id, cv_id)
            
            return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Failed to delete CV: {str(e)}'}), 500
    
    @cv_bp.route('/<cv_id>/set-primary', methods=['PUT'])
    @token_required
    def set_primary_cv(current_user, cv_id):
        """Set a CV as primary (default for applications)"""
        try:
            # Only candidates can set primary CV
            if current_user.get('user_type') != 'candidate':
                return jsonify({'error': 'Only candidates can set primary CV'}), 403
            
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.set_primary_cv(user_id, cv_id)
            
            return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Failed to set primary CV: {str(e)}'}), 500
    
    @cv_bp.route('/<cv_id>/preview', methods=['GET'])
    @token_required
    def preview_cv(current_user, cv_id):
        """Preview/Download CV PDF file"""
        try:
            from flask import send_file
            import os
            
            user_id = str(current_user['_id'])
            
            # Get CV details
            cv = cv_controller.get_cv_by_id(user_id, cv_id)
            if not cv:
                return jsonify({'error': 'CV not found'}), 404
            
            file_path = cv.get('file_path')
            if not file_path or not os.path.exists(file_path):
                return jsonify({'error': 'CV file not found'}), 404
            
            # Send PDF file
            return send_file(
                file_path,
                mimetype='application/pdf',
                as_attachment=False,  # Open in browser, not download
                download_name=cv.get('filename', 'cv.pdf')
            )
            
        except Exception as e:
            return jsonify({'error': f'Failed to preview CV: {str(e)}'}), 500
    
    @cv_bp.route('/<cv_id>/text', methods=['GET'])
    @token_required
    def get_cv_text(current_user, cv_id):
        """Get extracted text from CV"""
        try:
            user_id = str(current_user['_id'])
            response, status_code = cv_controller.get_cv(user_id, cv_id)
            
            if status_code == 200:
                # Return only extracted text
                cv_data = response.get('cv', {})
                return jsonify({
                    'filename': cv_data.get('filename'),
                    'extracted_text': cv_data.get('extracted_text', ''),
                    'character_count': len(cv_data.get('extracted_text', ''))
                }), 200
            else:
                return jsonify(response), status_code
            
        except Exception as e:
            return jsonify({'error': f'Failed to get CV text: {str(e)}'}), 500
    
    return cv_bp

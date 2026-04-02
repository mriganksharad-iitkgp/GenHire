"""
CV Controller - Manage multiple CV uploads for candidates
Handles CV PDF upload, storage (GCS or local), extraction, and management
"""

import os
import uuid
import logging
from datetime import datetime
from werkzeug.utils import secure_filename
from bson import ObjectId
from services.pdf_parser_service import get_pdf_parser
from services import gcs_service

logger = logging.getLogger(__name__)

class CVController:
    """Controller for handling multiple CV uploads and management"""
    
    ALLOWED_EXTENSIONS = {'pdf'}
    MAX_FILE_SIZE_MB = 10
    MAX_CVS_PER_USER = 5
    
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.upload_folder = 'uploads/cvs'
        
        # Ensure upload directory exists
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # Initialize PDF parser
        try:
            self.pdf_parser = get_pdf_parser()
        except Exception as e:
            logger.warning(f"PDF parser initialization failed: {e}")
            self.pdf_parser = None
    
    def _allowed_file(self, filename):
        """Check if file has allowed extension"""
        return '.' in filename and filename.rsplit('.', 1)[1].lower() in self.ALLOWED_EXTENSIONS
    
    def _get_user_cv_folder(self, user_id):
        """Get folder path for user's CVs"""
        user_folder = os.path.join(self.upload_folder, str(user_id))
        os.makedirs(user_folder, exist_ok=True)
        return user_folder
    
    def upload_cv(self, user_id, cv_file, is_primary=False):
        """
        Upload a new CV PDF for user
        
        Args:
            user_id: User ID
            cv_file: File object from request
            is_primary: Set as primary CV
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            # Get user
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            # Validate file
            if not cv_file or cv_file.filename == '':
                return {'error': 'No file selected'}, 400
            
            if not self._allowed_file(cv_file.filename):
                return {'error': 'Only PDF files are allowed'}, 400
            
            # Check CV count limit
            cv_uploads = user.get('cv_uploads', [])
            if len(cv_uploads) >= self.MAX_CVS_PER_USER:
                return {'error': f'Maximum {self.MAX_CVS_PER_USER} CVs allowed per user'}, 400
            
            # Generate unique filename
            cv_id = str(uuid.uuid4())
            original_filename = secure_filename(cv_file.filename)
            file_extension = original_filename.rsplit('.', 1)[1].lower()
            filename = f"{cv_id}.{file_extension}"
            
            # Save file locally first (needed for PDF text extraction)
            user_folder = self._get_user_cv_folder(user_id)
            local_file_path = os.path.join(user_folder, filename)
            cv_file.save(local_file_path)
            
            # Extract text using PDF parser
            extracted_text = ""
            metadata = {}
            
            try:
                if self.pdf_parser:
                    result = self.pdf_parser.parse_cv_pdf(local_file_path)
                    extracted_text = result.get('text', '')
                    metadata = result.get('metadata', {})
                    logger.info(f"Extracted {len(extracted_text)} characters from CV: {original_filename}")
                else:
                    logger.warning("PDF parser not available, CV text not extracted")
            except Exception as e:
                logger.error(f"Failed to extract text from CV: {e}")
                # Continue with upload but without extracted text
            
            # Upload to GCS if configured, otherwise keep local
            file_path = local_file_path
            gcs_path = None
            if gcs_service.is_gcs_configured():
                try:
                    gcs_path = f"cvs/{user_id}/{filename}"
                    gcs_service.upload_from_path(local_file_path, gcs_path)
                    file_path = f"gs://{os.getenv('GCS_BUCKET_NAME')}/{gcs_path}"
                    # Remove local file after successful GCS upload
                    try:
                        os.remove(local_file_path)
                    except OSError:
                        pass
                    logger.info(f"CV uploaded to GCS: {gcs_path}")
                except Exception as e:
                    logger.warning(f"GCS upload failed, keeping local: {e}")
                    gcs_path = None
            
            # Create CV upload record
            cv_upload = {
                'cv_id': cv_id,
                'filename': original_filename,
                'file_path': file_path,
                'gcs_path': gcs_path,
                'extracted_text': extracted_text,
                'upload_date': datetime.utcnow(),
                'is_primary': is_primary or len(cv_uploads) == 0,  # First CV is always primary
                'metadata': {
                    'file_size': metadata.get('file_size', 0),
                    'pages': metadata.get('pages', 0),
                    'character_count': len(extracted_text),
                    'word_count': metadata.get('word_count', 0)
                }
            }
            
            # If setting as primary, unset other primary flags
            if cv_upload['is_primary']:
                for cv in cv_uploads:
                    cv['is_primary'] = False
            
            # Add to user's CV uploads
            cv_uploads.append(cv_upload)
            
            # Update user document
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'cv_uploads': cv_uploads,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return {
                'message': 'CV uploaded successfully',
                'cv': {
                    'cv_id': cv_id,
                    'filename': original_filename,
                    'is_primary': cv_upload['is_primary'],
                    'upload_date': cv_upload['upload_date'].isoformat(),
                    'metadata': cv_upload['metadata']
                }
            }, 201
            
        except Exception as e:
            logger.error(f"Error uploading CV: {e}")
            import traceback
            traceback.print_exc()
            return {'error': f'Failed to upload CV: {str(e)}'}, 500
    
    def list_cvs(self, user_id):
        """
        Get list of all CVs for user
        
        Args:
            user_id: User ID
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            cv_uploads = user.get('cv_uploads', [])
            
            # Format response (exclude extracted_text and file_path for list view)
            cvs = []
            for cv in cv_uploads:
                # Get filename - handle both new and legacy formats
                filename = cv.get('filename')
                if not filename:
                    # Fallback: try to extract from file_path
                    file_path = cv.get('file_path', '')
                    if file_path:
                        filename = os.path.basename(file_path)
                    else:
                        filename = f"CV_{cv.get('cv_id', 'unknown')[:8]}.pdf"
                
                cvs.append({
                    'cv_id': cv.get('cv_id'),
                    'filename': filename,
                    'is_primary': cv.get('is_primary', False),
                    'upload_date': cv.get('upload_date').isoformat() if cv.get('upload_date') else None,
                    'metadata': cv.get('metadata', {})
                })
            
            return {
                'cvs': cvs,
                'count': len(cvs),
                'max_allowed': self.MAX_CVS_PER_USER
            }, 200
            
        except Exception as e:
            logger.error(f"Error listing CVs: {e}")
            return {'error': f'Failed to list CVs: {str(e)}'}, 500
    
    def get_cv(self, user_id, cv_id):
        """
        Get specific CV details including extracted text
        
        Args:
            user_id: User ID
            cv_id: CV ID
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            cv_uploads = user.get('cv_uploads', [])
            cv = next((c for c in cv_uploads if c.get('cv_id') == cv_id), None)
            
            if not cv:
                return {'error': 'CV not found'}, 404
            
            return {
                'cv': {
                    'cv_id': cv.get('cv_id'),
                    'filename': cv.get('filename'),
                    'is_primary': cv.get('is_primary', False),
                    'upload_date': cv.get('upload_date').isoformat() if cv.get('upload_date') else None,
                    'extracted_text': cv.get('extracted_text', ''),
                    'metadata': cv.get('metadata', {})
                }
            }, 200
            
        except Exception as e:
            logger.error(f"Error getting CV: {e}")
            return {'error': f'Failed to get CV: {str(e)}'}, 500
    
    def delete_cv(self, user_id, cv_id):
        """
        Delete a CV
        
        Args:
            user_id: User ID
            cv_id: CV ID
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            cv_uploads = user.get('cv_uploads', [])
            cv = next((c for c in cv_uploads if c.get('cv_id') == cv_id), None)
            
            if not cv:
                return {'error': 'CV not found'}, 404
            
            # Don't allow deleting if it's the only CV
            if len(cv_uploads) == 1:
                return {'error': 'Cannot delete the only CV. Upload a new one first.'}, 400
            
            was_primary = cv.get('is_primary', False)
            
            # Delete file from GCS and/or local
            try:
                gcs_path = cv.get('gcs_path')
                if gcs_path and gcs_service.is_gcs_configured():
                    gcs_service.delete_file(gcs_path)
                local_path = cv.get('file_path', '')
                if local_path and not local_path.startswith('gs://') and os.path.exists(local_path):
                    os.remove(local_path)
            except Exception as e:
                logger.warning(f"Failed to delete CV file: {e}")
            
            # Remove from list
            cv_uploads = [c for c in cv_uploads if c.get('cv_id') != cv_id]
            
            # If deleted CV was primary, set first CV as primary
            if was_primary and cv_uploads:
                cv_uploads[0]['is_primary'] = True
            
            # Update user document
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'cv_uploads': cv_uploads,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return {'message': 'CV deleted successfully'}, 200
            
        except Exception as e:
            logger.error(f"Error deleting CV: {e}")
            return {'error': f'Failed to delete CV: {str(e)}'}, 500
    
    def set_primary_cv(self, user_id, cv_id):
        """
        Set a CV as primary (default for applications)
        
        Args:
            user_id: User ID
            cv_id: CV ID to set as primary
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            cv_uploads = user.get('cv_uploads', [])
            cv = next((c for c in cv_uploads if c.get('cv_id') == cv_id), None)
            
            if not cv:
                return {'error': 'CV not found'}, 404
            
            # Unset all primary flags
            for c in cv_uploads:
                c['is_primary'] = False
            
            # Set selected CV as primary
            cv['is_primary'] = True
            
            # Update user document
            self.users_collection.update_one(
                {'_id': ObjectId(user_id)},
                {
                    '$set': {
                        'cv_uploads': cv_uploads,
                        'updated_at': datetime.utcnow()
                    }
                }
            )
            
            return {'message': 'Primary CV updated successfully'}, 200
            
        except Exception as e:
            logger.error(f"Error setting primary CV: {e}")
            return {'error': f'Failed to set primary CV: {str(e)}'}, 500
    
    def get_primary_cv(self, user_id):
        """
        Get user's primary CV
        
        Args:
            user_id: User ID
            
        Returns:
            CV dict or None
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return None
            
            cv_uploads = user.get('cv_uploads', [])
            primary_cv = next((c for c in cv_uploads if c.get('is_primary', False)), None)
            
            # If no primary, return first CV
            if not primary_cv and cv_uploads:
                primary_cv = cv_uploads[0]
            
            return primary_cv
            
        except Exception as e:
            logger.error(f"Error getting primary CV: {e}")
            return None
    
    def get_cv_by_id(self, user_id, cv_id):
        """
        Get specific CV by ID
        
        Args:
            user_id: User ID
            cv_id: CV ID
            
        Returns:
            CV dict or None
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return None
            
            cv_uploads = user.get('cv_uploads', [])
            cv = next((c for c in cv_uploads if c.get('cv_id') == cv_id), None)
            
            return cv
            
        except Exception as e:
            logger.error(f"Error getting CV by ID: {e}")
            return None
    
    def get_cv_download_url(self, user_id, cv_id):
        """
        Get a download URL for a CV. Returns a signed GCS URL or local file path.
        
        Args:
            user_id: User ID
            cv_id: CV ID
            
        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return {'error': 'User not found'}, 404
            
            cv_uploads = user.get('cv_uploads', [])
            cv = next((c for c in cv_uploads if c.get('cv_id') == cv_id), None)
            
            if not cv:
                return {'error': 'CV not found'}, 404
            
            gcs_path = cv.get('gcs_path')
            if gcs_path and gcs_service.is_gcs_configured():
                try:
                    signed_url = gcs_service.generate_signed_url(gcs_path, expiration_minutes=60)
                    return {
                        'download_url': signed_url,
                        'filename': cv.get('filename', f'{cv_id}.pdf'),
                        'source': 'gcs'
                    }, 200
                except Exception as e:
                    logger.error(f"Failed to generate signed URL: {e}")
                    return {'error': 'Failed to generate download link'}, 500
            
            # Fallback to local file path
            local_path = cv.get('file_path', '')
            if local_path and not local_path.startswith('gs://') and os.path.exists(local_path):
                return {
                    'download_url': None,
                    'local_path': local_path,
                    'filename': cv.get('filename', f'{cv_id}.pdf'),
                    'source': 'local'
                }, 200
            
            return {'error': 'CV file not available'}, 404
            
        except Exception as e:
            logger.error(f"Error getting CV download URL: {e}")
            return {'error': f'Failed to get download URL: {str(e)}'}, 500

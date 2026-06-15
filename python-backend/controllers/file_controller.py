import os
import tempfile
from werkzeug.utils import secure_filename
import uuid
from flask import send_file, jsonify, redirect
from bson import ObjectId
import gridfs
from services import gcs_service

class FileController:
    def __init__(self, db_collections):
        self.users_collection = db_collections['users']
        self.db = self.users_collection.database
        self.fs = gridfs.GridFS(self.db)
        
        self.upload_folder = os.path.join(tempfile.gettempdir(), 'hrtech_uploads')
        self.allowed_extensions = {'pdf', 'jpg', 'jpeg', 'png', 'gif'}
        
        # Ensure folders exist
        self.jd_folder = os.path.join(self.upload_folder, "jd")
        self.cv_folder = os.path.join(self.upload_folder, "cv")
        self.photos_folder = os.path.join(self.upload_folder, "photos")
        self.proctoring_folder = os.path.join(self.upload_folder, "proctoring")
        
        for folder in [self.jd_folder, self.cv_folder, self.photos_folder, self.proctoring_folder]:
            os.makedirs(folder, exist_ok=True)
        
    def allowed_file(self, filename):
        """Check if file extension is allowed"""
        return "." in filename and filename.rsplit(".", 1)[1].lower() in self.allowed_extensions
        
    def upload_files(self, jd_file, cv_file):
        """Upload JD and CV files"""
        if not jd_file or not self.allowed_file(jd_file.filename):
            return {'error': 'Invalid JD file format'}, 400
        if not cv_file or not self.allowed_file(cv_file.filename):
            return {'error': 'Invalid CV file format'}, 400

        # Generate random filenames while preserving original file extensions
        jd_ext = os.path.splitext(jd_file.filename)[1]
        jd_filename = secure_filename(str(uuid.uuid4()) + jd_ext)
        cv_ext = os.path.splitext(cv_file.filename)[1]
        cv_filename = secure_filename(str(uuid.uuid4()) + cv_ext)
        
        jd_path = os.path.join(self.jd_folder, jd_filename)
        cv_path = os.path.join(self.cv_folder, cv_filename)

        # Save both files now that they have passed validation
        jd_file.save(jd_path)
        cv_file.save(cv_path)
        
        return {
            "message": "Files uploaded successfully!",
            "jd_file_path": jd_path,
            "cv_file_path": cv_path,
            "similarity": 85.5,  # Mock similarity
            "interview_questions": ["Sample question 1", "Sample question 2", "Sample question 3"]
        }, 200
        
    def upload_cv(self, user_id, cv_file):
        """Upload CV for a specific user"""
        if not cv_file or not self.allowed_file(cv_file.filename):
            return {'error': 'Invalid CV file format. Only PDF files are allowed.'}, 400
        
        # Generate unique filename
        cv_ext = os.path.splitext(cv_file.filename)[1]
        cv_filename = secure_filename(str(uuid.uuid4()) + cv_ext)
        cv_path = os.path.join(self.cv_folder, cv_filename)
        
        # Save file
        cv_file.save(cv_path)
        
        # Update user record with CV path
        self.users_collection.update_one(
            {'_id': user_id},
            {'$set': {'cv_path': cv_path, 'cv_filename': cv_filename}}
        )
        
        return {
            'message': 'CV uploaded successfully',
            'cv_path': cv_path,
            'filename': cv_filename
        }, 200
        
    def upload_photo(self, user_id, photo_file):
        """Upload profile photo for a user"""
        if not photo_file:
            return {'error': 'No photo file selected'}, 400
        
        # Check file extension
        allowed_photo_extensions = {'png', 'jpg', 'jpeg', 'gif'}
        if not ('.' in photo_file.filename and 
                photo_file.filename.rsplit('.', 1)[1].lower() in allowed_photo_extensions):
            return {'error': 'Invalid photo format. Only PNG, JPG, JPEG, GIF allowed.'}, 400
        
        # Generate unique filename
        photo_ext = os.path.splitext(photo_file.filename)[1]
        photo_filename = secure_filename(str(uuid.uuid4()) + photo_ext)
        local_photo_path = os.path.join(self.photos_folder, photo_filename)
        
        # Save file locally
        photo_file.save(local_photo_path)
        
        # Upload to GridFS
        content_type = f"image/{photo_ext.replace('.', '')}"
        with open(local_photo_path, 'rb') as f:
            gridfs_id = self.fs.put(f, filename=photo_filename, content_type=content_type)
        
        photo_path = f"gridfs://{gridfs_id}"
        
        # Upload to GCS if configured
        gcs_path = None
        if gcs_service.is_gcs_configured():
            try:
                gcs_path = f"photos/{user_id}/{photo_filename}"
                gcs_service.upload_from_path(local_photo_path, gcs_path, content_type=content_type)
                photo_path = f"gs://{os.getenv('GCS_BUCKET_NAME')}/{gcs_path}"
            except Exception as e:
                gcs_path = None
                
        # Remove local file
        try:
            os.remove(local_photo_path)
        except OSError:
            pass
        
        # Update user record with photo path
        self.users_collection.update_one(
            {'_id': ObjectId(user_id)},
            {'$set': {
                'profile_photo': photo_path, 
                'photo_filename': photo_filename,
                'photo_gcs_path': gcs_path
            }}
        )
        
        return {
            'message': 'Photo uploaded successfully',
            'photo_path': photo_path,
            'filename': photo_filename
        }, 200
        
    def get_cv_path(self, user_id):
        """Retrieve CV file path for user"""
        user = self.users_collection.find_one({'_id': user_id})
        if not user:
            return None
        return user.get('cv_path')
        
    def get_photo_path(self, user_id):
        """Retrieve photo file path for user"""
        user = self.users_collection.find_one({'_id': user_id})
        if not user:
            return None
        return user.get('profile_photo')
        
    def serve_file(self, file_path):
        """Serve file with security checks"""
        base_dir = os.path.abspath(os.path.join(os.getcwd(), "uploads"))
        abs_file_path = os.path.abspath(file_path)
        
        if not abs_file_path.startswith(base_dir):
            return {'error': 'Unauthorized file path'}, 403

        if not os.path.isfile(abs_file_path):
            return {'error': 'File not found'}, 404

        return send_file(abs_file_path)
        
    def download_cv(self, user_id):
        """Download user's CV"""
        cv_path = self.get_cv_path(user_id)
        if not cv_path or not os.path.exists(cv_path):
            return {'error': 'CV not found'}, 404
        
        return send_file(cv_path, as_attachment=True)
        
    def view_cv(self, user_id):
        """View user's CV in browser"""
        cv_path = self.get_cv_path(user_id)
        if not cv_path or not os.path.exists(cv_path):
            return {'error': 'CV not found'}, 404
        
        return send_file(cv_path)
        
    def view_photo(self, user_id):
        """View user's profile photo"""
        user = self.users_collection.find_one({'_id': ObjectId(user_id)})
        if not user:
            return {'error': 'User not found'}, 404
            
        photo_path = user.get('profile_photo')
        photo_gcs_path = user.get('photo_gcs_path')
        
        if photo_gcs_path and gcs_service.is_gcs_configured():
            try:
                from flask import redirect
                signed_url = gcs_service.generate_signed_url(photo_gcs_path, expiration_minutes=60)
                return redirect(signed_url)
            except Exception:
                pass
                
        if photo_path and photo_path.startswith('gridfs://'):
            from flask import redirect
            gridfs_id = photo_path.split('gridfs://')[1]
            return redirect(f"/api/files/{gridfs_id}")
                
        if not photo_path or not os.path.exists(photo_path):
            return {'error': 'Photo not found'}, 404
        
        return send_file(photo_path)

    def view_cv_by_id(self, user_id):
        """View CV for a specific user by ID (admin use)"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            cv_path = user.get('cv_path')
            if not cv_path or not os.path.exists(cv_path):
                return jsonify({'error': 'CV not found'}), 404
            
            return send_file(cv_path)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

    def view_photo_by_id(self, user_id):
        """View profile photo for a specific user by ID (admin use)"""
        try:
            user = self.users_collection.find_one({'_id': ObjectId(user_id)})
            if not user:
                return jsonify({'error': 'User not found'}), 404
            
            photo_path = user.get('profile_photo')
            photo_gcs_path = user.get('photo_gcs_path')
            
            if photo_gcs_path and gcs_service.is_gcs_configured():
                try:
                    from flask import redirect
                    signed_url = gcs_service.generate_signed_url(photo_gcs_path, expiration_minutes=60)
                    return redirect(signed_url)
                except Exception:
                    pass
            
            if photo_path and photo_path.startswith('gridfs://'):
                from flask import redirect
                gridfs_id = photo_path.split('gridfs://')[1]
                return redirect(f"/api/files/{gridfs_id}")
            
            if not photo_path or not os.path.exists(photo_path):
                return jsonify({'error': 'Photo not found'}), 404
            
            return send_file(photo_path)
        except Exception as e:
            return jsonify({'error': str(e)}), 500

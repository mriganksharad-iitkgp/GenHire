import datetime
import os
import uuid
import logging
from bson import ObjectId
from werkzeug.utils import secure_filename
from services.pdf_parser_service import get_pdf_parser

logger = logging.getLogger(__name__)

class JobController:
    def __init__(self, db_collections):
        self.jobs_collection = db_collections['jobs']
        self.applications_collection = db_collections['applications']
        self.upload_folder = 'uploads/jds'
        
        # Ensure upload directory exists
        os.makedirs(self.upload_folder, exist_ok=True)
        
        # Initialize PDF parser
        try:
            self.pdf_parser = get_pdf_parser()
        except Exception as e:
            logger.warning(f"PDF parser initialization failed: {e}")
            self.pdf_parser = None
        
    def get_jobs(self, user_type, user_id):
        """Retrieve jobs based on user type and permissions"""
        if user_type == 'recruiter':
            # Return all jobs for recruiters
            jobs = list(self.jobs_collection.find({'created_by': user_id}))
            for job in jobs:
                job['_id'] = str(job['_id'])
            return jobs, 200
        else:
            # For candidates: Show active jobs + jobs they have applied to
            # Get job IDs that the user has applied to
            user_applications = list(self.applications_collection.find({'student_id': user_id}))
            applied_job_ids = [app['job_id'] for app in user_applications]
            
            # Build query: active jobs (not created by system) OR jobs user has applied to
            query = {
                '$or': [
                    {'status': 'active', 'created_by': {'$ne': 'system'}},  # Show active jobs not created by system
                    {'_id': {'$in': [ObjectId(job_id) for job_id in applied_job_ids]}}  # Show jobs user applied to
                ]
            }
            
            jobs = list(self.jobs_collection.find(query))
            for job in jobs:
                job['_id'] = str(job['_id'])
                # Remove sensitive recruiter info
                job.pop('created_by', None)
            return jobs, 200
        
    def create_job(self, recruiter_id, job_data, recruiter_profile, jd_file=None):
        """
        Create new job posting
        
        Args:
            recruiter_id: ID of recruiter creating the job
            job_data: Job data dictionary
            recruiter_profile: Recruiter's profile data
            jd_file: Optional JD PDF file (Phase 4)
            
        Returns:
            tuple: (response_dict, status_code)
        """
        required_fields = ['title', 'department', 'location', 'type', 'experience', 'salary', 'description']
        
        for field in required_fields:
            if field not in job_data or not job_data[field]:
                return {'error': f'{field} is required'}, 400
        
        # Validate minimum CV score if provided
        minimum_cv_score = job_data.get('minimum_cv_score')
        if minimum_cv_score is not None:
            try:
                minimum_cv_score = float(minimum_cv_score)
                if minimum_cv_score < 0 or minimum_cv_score > 100:
                    return {'error': 'Minimum CV score must be between 0 and 100'}, 400
            except (ValueError, TypeError):
                return {'error': 'Minimum CV score must be a valid number'}, 400
        else:
            minimum_cv_score = 50.0  # Default minimum CV score
        
        # Check for unique job title
        job_title = job_data['title'].strip()
        existing_job = self.jobs_collection.find_one({'title': job_title, 'created_by': recruiter_id})
        if existing_job:
            return {'error': f'A job with the title "{job_title}" already exists. Please use a unique job title.'}, 400
        
        # Normalize/validate status with enhanced workflow - default to draft
        raw_status = (job_data.get('status') or 'draft').strip().lower()
        allowed_statuses = {'draft', 'active', 'paused', 'closed'}
        status = raw_status if raw_status in allowed_statuses else 'draft'

        # Helpers to normalize list-like fields possibly sent as strings
        def normalize_list_field(val, separator=','):
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                # Try both newline and comma separated values
                text = val.replace('\r', '').strip()
                parts = []
                for chunk in text.split('\n'):
                    parts.extend([p.strip() for p in chunk.split(separator)])
                return [p for p in parts if p]
            return []

        # Get company information from recruiter's profile
        company_name = recruiter_profile.get('company_name') or job_data.get('company') or 'TechCorp Solutions'
        company_logo = recruiter_profile.get('company_logo') or job_data.get('logo') or None
        
        # Handle JD PDF upload (Phase 4)
        jd_pdf_path = None
        jd_extracted_text = None
        jd_upload_date = None
        
        if jd_file and jd_file.filename:
            try:
                # Generate unique filename
                job_id = str(uuid.uuid4())
                file_extension = secure_filename(jd_file.filename).rsplit('.', 1)[-1].lower()
                
                # Validate file type
                if file_extension not in ['pdf', 'txt']:
                    logger.warning(f"Invalid JD file type: {file_extension}")
                else:
                    jd_filename = f"jd_{job_id}.{file_extension}"
                    jd_pdf_path = os.path.join(self.upload_folder, jd_filename)
                    
                    # Save file
                    jd_file.save(jd_pdf_path)
                    jd_upload_date = datetime.datetime.utcnow()
                    
                    # Extract text from JD PDF/TXT
                    if self.pdf_parser:
                        try:
                            jd_extracted_text = self.pdf_parser.extract_text(jd_pdf_path)
                            logger.info(f"Extracted {len(jd_extracted_text)} characters from JD: {jd_filename}")
                        except Exception as e:
                            logger.error(f"Failed to extract text from JD: {e}")
                            # Continue with job creation without extracted text
                    else:
                        logger.warning("PDF parser not available, JD text not extracted")
            except Exception as e:
                logger.error(f"Error processing JD file: {e}")
                # Continue with job creation without JD file

        job_document = {
            'title': job_data['title'],
            'department': job_data['department'],
            'location': job_data['location'],
            'type': job_data['type'],
            'experience': job_data['experience'],
            'salary': job_data['salary'],
            'description': job_data['description'],
            'company': company_name,
            'logo': company_logo,
            'skills': normalize_list_field(job_data.get('skills', [])),
            'responsibilities': normalize_list_field(job_data.get('responsibilities', []), separator='\n'),
            'requirements': normalize_list_field(job_data.get('requirements', []), separator='\n'),
            'benefits': normalize_list_field(job_data.get('benefits', []), separator='\n'),
            'status': status,
            'minimum_cv_score': minimum_cv_score,
            'created_by': recruiter_id,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow(),
            'deadline': job_data.get('deadline'),
            'applicants': 0,
            'interviewed': 0,
            'selected': 0,
            'rejected': 0,
            'pending': 0,
            # JD PDF fields (Phase 4)
            'jd_pdf_path': jd_pdf_path,
            'jd_extracted_text': jd_extracted_text,
            'jd_upload_date': jd_upload_date
        }
        
        result = self.jobs_collection.insert_one(job_document)
        job_document['_id'] = str(result.inserted_id)
        
        return {'message': 'Job created successfully', 'job': job_document}, 201
        
    def update_job(self, job_id, recruiter_id, job_data):
        """Update existing job posting"""
        # Validate job_id format
        if not job_id or job_id == 'undefined' or job_id == 'null':
            return {'error': 'Invalid job ID provided'}, 400
        
        try:
            job_object_id = ObjectId(job_id)
        except Exception as e:
            return {'error': f'Invalid job ID format: {job_id}'}, 400
        
        # Verify job belongs to current recruiter
        job = self.jobs_collection.find_one({'_id': job_object_id, 'created_by': recruiter_id})
        if not job:
            return {'error': 'Job not found or unauthorized'}, 404
        
        update_fields = {}
        
        # Status progression validation
        def validate_status_progression(current_status, new_status):
            status_hierarchy = {'draft': 0, 'active': 1, 'paused': 2, 'closed': 3}
            current_level = status_hierarchy.get(current_status, 0)
            new_level = status_hierarchy.get(new_status, 0)
            return new_level >= current_level
        
        def normalize_list_field(val, separator=','):
            if isinstance(val, list):
                return [str(x).strip() for x in val if str(x).strip()]
            if isinstance(val, str):
                # Try both newline and comma separated values
                text = val.replace('\r', '').strip()
                parts = []
                for chunk in text.split('\n'):
                    parts.extend([p.strip() for p in chunk.split(separator)])
                return [p for p in parts if p]
            return []
        
        allowed_fields = ['title', 'department', 'location', 'type', 'experience', 'salary', 'description', 'skills', 'responsibilities', 'requirements', 'benefits', 'status', 'deadline', 'minimum_cv_score']
        for field in allowed_fields:
            if field in job_data:
                if field == 'status':
                    raw = str(job_data[field]).strip().lower()
                    allowed_statuses = {'draft', 'active', 'paused', 'closed'}
                    if raw in allowed_statuses:
                        current_status = job.get('status', 'draft')
                        if validate_status_progression(current_status, raw):
                            update_fields[field] = raw
                        else:
                            return {'error': f'Cannot change status from {current_status} to {raw}. Status can only progress forward.'}, 400
                    else:
                        return {'error': f'Invalid status: {raw}. Allowed values: {list(allowed_statuses)}'}, 400
                elif field == 'minimum_cv_score':
                    # Validate minimum CV score
                    try:
                        cv_score = float(job_data[field])
                        if cv_score < 0 or cv_score > 100:
                            return {'error': 'Minimum CV score must be between 0 and 100'}, 400
                        update_fields[field] = cv_score
                    except (ValueError, TypeError):
                        return {'error': 'Minimum CV score must be a valid number'}, 400
                elif field in {'skills'}:
                    update_fields[field] = normalize_list_field(job_data.get(field, []))
                elif field in {'responsibilities', 'requirements', 'benefits'}:
                    update_fields[field] = normalize_list_field(job_data.get(field, []), separator='\n')
                else:
                    update_fields[field] = job_data[field]
        
        if update_fields:
            update_fields['updated_at'] = datetime.datetime.utcnow()
            self.jobs_collection.update_one({'_id': job_object_id}, {'$set': update_fields})
        
        return {'message': 'Job updated successfully'}, 200
        
    def delete_job(self, job_id, recruiter_id):
        """Delete job posting"""
        # Verify job belongs to current recruiter
        result = self.jobs_collection.delete_one({'_id': ObjectId(job_id), 'created_by': recruiter_id})
        if result.deleted_count == 0:
            return {'error': 'Job not found'}, 404
        
        return {'message': 'Job deleted successfully'}, 200
        
    def get_job_details(self, job_id, user_type, user_id=None):
        """Get single job details with permission checks"""
        try:
            job = self.jobs_collection.find_one({'_id': ObjectId(job_id)})
        except Exception:
            return {'error': 'Invalid job id'}, 400

        if not job:
            return {'error': 'Job not found'}, 404

        if user_type != 'recruiter':
            # For candidates, restrict to active jobs only
            status = (job.get('status') or '').strip().lower()
            if status not in ['active', ''] and job.get('status') is not None:
                return {'error': 'Job not available'}, 403
            # Hide recruiter-only fields
            job.pop('created_by', None)

        job['_id'] = str(job['_id'])
        return job, 200
    
    def get_job_applications(self, job_id, recruiter_id):
        """Get all applications for a specific job (recruiters only)"""
        # Verify job belongs to current recruiter
        job = self.jobs_collection.find_one({'_id': ObjectId(job_id), 'created_by': recruiter_id})
        if not job:
            return {'error': 'Job not found or unauthorized'}, 404
        
        # Get all applications for this job
        applications = list(self.applications_collection.find({'job_id': job_id}))
        
        # Convert ObjectId to string
        for app in applications:
            app['_id'] = str(app['_id'])
        
        return {
            'job': {
                'id': str(job['_id']),
                'title': job.get('title'),
                'department': job.get('department'),
                'location': job.get('location')
            },
            'applications': applications
        }, 200

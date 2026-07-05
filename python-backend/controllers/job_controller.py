import datetime
import os
import uuid
import json
import re
import logging
from bson import ObjectId
from werkzeug.utils import secure_filename
from services.pdf_parser_service import get_pdf_parser
from services import gcs_service
from dotenv import load_dotenv
from utils.job_standards import canonicalize_job_role
from services.usage_telemetry_service import record_usage_event
from payment_module.config.settings import PaymentConfig
from payment_module.services.wallet_service import WalletService

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
        self.wallet_service = WalletService(self.jobs_collection.database)

    @staticmethod
    def _normalize_text_key(value):
        return re.sub(r"\s+", " ", str(value or "")).strip().lower()

    def _find_recruiter_duplicate_job(self, recruiter_id, title, location, exclude_job_id=None):
        """Check duplicate by normalized title+location within a single recruiter's jobs."""
        title_key = self._normalize_text_key(title)
        location_key = self._normalize_text_key(location)
        if not title_key or not location_key:
            return None

        recruiter_jobs = self.jobs_collection.find(
            {'created_by': recruiter_id},
            {'title': 1, 'location': 1}
        )

        for job in recruiter_jobs:
            if exclude_job_id and str(job.get('_id')) == str(exclude_job_id):
                continue

            existing_title_key = self._normalize_text_key(job.get('title', ''))
            existing_location_key = self._normalize_text_key(job.get('location', ''))
            if existing_title_key == title_key and existing_location_key == location_key:
                return job

        return None
        
    def _job_search_filter(self, search_query):
        normalized = self._normalize_text_key(search_query)
        if not normalized:
            return None
        pattern = re.escape(normalized)
        return {
            '$or': [
                {'title': {'$regex': pattern, '$options': 'i'}},
                {'description': {'$regex': pattern, '$options': 'i'}},
                {'department': {'$regex': pattern, '$options': 'i'}},
                {'location': {'$regex': pattern, '$options': 'i'}},
                {'skills': {'$regex': pattern, '$options': 'i'}},
            ]
        }

    def get_jobs(self, user_type, user_id, search_query=''):
        """Retrieve jobs based on user type and permissions"""
        search_filter = self._job_search_filter(search_query)
        if user_type == 'recruiter':
            # Return all jobs for recruiters
            query = {'created_by': user_id}
            if search_filter:
                query = {'$and': [query, search_filter]}
            jobs = list(self.jobs_collection.find(query))
            for job in jobs:
                job['_id'] = str(job['_id'])

            job_ids_str = [job['_id'] for job in jobs]

            # BULK FETCH APPLICATIONS
            all_apps = list(self.applications_collection.find(
                {'job_id': {'$in': job_ids_str}, 'is_visible': True},
                {'job_id': 1, 'status': 1}
            ))
            
            # Group applications by job_id
            apps_by_job = {job_id: [] for job_id in job_ids_str}
            for app in all_apps:
                apps_by_job[app.get('job_id')].append(app)

            for job in jobs:
                job_id_str = job['_id']
                job_applications = apps_by_job.get(job_id_str, [])

                interviewed_count = 0
                screening_cleared_count = 0
                rejected_count = 0
                pending_count = 0

                for app in job_applications:
                    status = str(app.get('status', 'pending')).lower()
                    if status == 'interviewed':
                        interviewed_count += 1
                    elif status in ('screening_cleared', 'selected'):  # 'selected' = legacy value
                        screening_cleared_count += 1
                    elif status == 'rejected':
                        rejected_count += 1
                    elif status in ['pending', 'reviewed', 'shortlisted']:
                        pending_count += 1

                job['applicants'] = len(job_applications)
                job['interviewed'] = interviewed_count
                job['screening_cleared'] = screening_cleared_count
                # Deprecated alias kept one release for older clients/kiosk builds.
                job['selected'] = screening_cleared_count
                job['rejected'] = rejected_count
                job['pending'] = pending_count

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
            if search_filter:
                query = {'$and': [query, search_filter]}
            
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

        # Proctoring configuration — defaults all enabled
        default_proctoring = {
            'voice_detection': True,
            'object_detection': True,
            'eyeball_tracking': True,
            'gaze_heatmap': True,
        }
        raw_proctoring = job_data.get('proctoring_config')
        if isinstance(raw_proctoring, dict):
            proctoring_config = {
                k: bool(raw_proctoring.get(k, True)) for k in default_proctoring
            }
        else:
            proctoring_config = default_proctoring
        
        # Preserve recruiter-entered title; derive canonical role separately for candidate filters
        job_title = re.sub(r"\s+", " ", str(job_data.get('title', ''))).strip()
        if not job_title:
            return {'error': 'Job title is required'}, 400

        location = str(job_data.get('location', '')).strip()
        if not location:
            return {'error': 'location is required'}, 400

        canonical_role = canonicalize_job_role(job_title)
        if not canonical_role:
            return {'error': 'Job title is required'}, 400

        # Enforce uniqueness only within this recruiter's jobs and only for exact title+location pair
        existing_job = self._find_recruiter_duplicate_job(recruiter_id, job_title, location)
        if existing_job:
            return {
                'error': (
                    f'A job with the title "{job_title}" at location "{location}" already exists '
                    'for your account. Please change either title or location.'
                )
            }, 400
        
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
        
        # Handle JD PDF upload — stored in Google Cloud Storage so candidates
        # can download the exact document the recruiter uploaded. The file is
        # optional and non-fatal: if GCS isn't configured or the upload fails,
        # the job is still created (just without a downloadable JD PDF).
        jd_pdf_path = None
        jd_gcs_path = None
        jd_original_filename = None
        jd_extracted_text = None
        jd_upload_date = None

        if jd_file and jd_file.filename:
            file_extension = secure_filename(jd_file.filename).rsplit('.', 1)[-1].lower()
            if file_extension not in ['pdf', 'txt']:
                logger.warning(f"Invalid JD file type: {file_extension}")
            else:
                job_uid = str(uuid.uuid4())
                jd_filename = f"jd_{job_uid}.{file_extension}"
                local_path = os.path.join(self.upload_folder, jd_filename)
                try:
                    jd_file.save(local_path)

                    # Extract text before upload (pdf_parser needs a local path).
                    if self.pdf_parser:
                        try:
                            jd_extracted_text = self.pdf_parser.extract_text(local_path)
                            logger.info(f"Extracted {len(jd_extracted_text)} characters from JD: {jd_filename}")
                        except Exception as e:
                            logger.error(f"Failed to extract text from JD: {e}")
                    else:
                        logger.warning("PDF parser not available, JD text not extracted")

                    if gcs_service.is_gcs_configured():
                        try:
                            jd_gcs_path = f"jds/{recruiter_id}/{jd_filename}"
                            gcs_service.upload_from_path(local_path, jd_gcs_path)
                            jd_pdf_path = f"gs://{os.getenv('GCS_BUCKET_NAME')}/{jd_gcs_path}"
                            jd_original_filename = secure_filename(jd_file.filename)
                            jd_upload_date = datetime.datetime.utcnow()
                            logger.info(f"JD uploaded to GCS: {jd_gcs_path}")
                        except Exception as e:
                            logger.error(f"GCS upload failed for JD, continuing without it: {e}")
                            jd_gcs_path = None
                            jd_pdf_path = None
                    else:
                        logger.warning("GCS not configured — JD PDF will not be available for candidate download")
                except Exception as e:
                    logger.error(f"Error processing JD file: {e}")
                finally:
                    try:
                        os.remove(local_path)
                    except OSError:
                        pass

        job_document = {
            'title': job_title,
            'canonical_role': canonical_role,
            'department': job_data['department'],
            'location': location,
            'title_key': self._normalize_text_key(job_title),
            'location_key': self._normalize_text_key(location),
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
            'proctoring_config': proctoring_config,
            'created_by': recruiter_id,
            'created_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow(),
            'deadline': job_data.get('deadline'),
            'applicants': 0,
            'interviewed': 0,
            'screening_cleared': 0,
            'rejected': 0,
            'pending': 0,
            # JD PDF fields (stored in GCS)
            'jd_pdf_path': jd_pdf_path,
            'jd_gcs_path': jd_gcs_path,
            'jd_original_filename': jd_original_filename,
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
        
        allowed_fields = ['title', 'department', 'location', 'type', 'experience', 'salary', 'description', 'skills', 'responsibilities', 'requirements', 'benefits', 'status', 'deadline', 'minimum_cv_score', 'proctoring_config']
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
                elif field == 'proctoring_config':
                    raw_pc = job_data.get(field, {})
                    if isinstance(raw_pc, dict):
                        valid_keys = {'voice_detection', 'object_detection', 'eyeball_tracking', 'gaze_heatmap'}
                        update_fields[field] = {k: bool(raw_pc.get(k, True)) for k in valid_keys}
                elif field in {'skills'}:
                    update_fields[field] = normalize_list_field(job_data.get(field, []))
                elif field in {'responsibilities', 'requirements', 'benefits'}:
                    update_fields[field] = normalize_list_field(job_data.get(field, []), separator='\n')
                elif field == 'title':
                    title_value = re.sub(r"\s+", " ", str(job_data[field] or '')).strip()
                    canonical_title = canonicalize_job_role(title_value)
                    if not canonical_title:
                        return {'error': 'Job title is required'}, 400
                    update_fields[field] = title_value
                    update_fields['canonical_role'] = canonical_title
                elif field == 'location':
                    location = str(job_data[field]).strip()
                    if not location:
                        return {'error': 'location is required'}, 400
                    update_fields[field] = location
                else:
                    update_fields[field] = job_data[field]

        # Duplicate validation for updates: same recruiter cannot have same normalized title+location pair
        candidate_title = update_fields.get('title', job.get('title', ''))
        candidate_location = update_fields.get('location', job.get('location', ''))
        duplicate_job = self._find_recruiter_duplicate_job(
            recruiter_id,
            candidate_title,
            candidate_location,
            exclude_job_id=job_object_id
        )
        if duplicate_job:
            return {
                'error': (
                    f'A job with the title "{candidate_title}" at location "{candidate_location}" already exists '
                    'for your account. Please change either title or location.'
                )
            }, 400

        if 'title' in update_fields:
            update_fields['title_key'] = self._normalize_text_key(update_fields['title'])
        if 'location' in update_fields:
            update_fields['location_key'] = self._normalize_text_key(update_fields['location'])
        
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

    def get_jd_download_url(self, job_id, user_id, user_type):
        """Get a signed download URL for the recruiter-uploaded JD PDF.

        Available to the job's own recruiter and to any candidate (job
        listings are already visible platform-wide to candidates; this just
        lets them download the original document instead of only reading the
        parsed fields)."""
        try:
            job = self.jobs_collection.find_one({'_id': ObjectId(job_id)})
        except Exception:
            return {'error': 'Invalid job id'}, 400
        if not job:
            return {'error': 'Job not found'}, 404

        if user_type == 'recruiter' and job.get('created_by') != user_id:
            return {'error': 'Unauthorized'}, 403

        jd_gcs_path = job.get('jd_gcs_path')
        if not jd_gcs_path:
            return {'error': 'No JD file has been uploaded for this job'}, 404

        if not gcs_service.is_gcs_configured():
            return {'error': 'Cloud storage is not configured'}, 500

        try:
            signed_url = gcs_service.generate_signed_url(jd_gcs_path, expiration_minutes=60)
        except Exception as e:
            logger.error(f"Failed to generate JD signed URL: {e}")
            return {'error': 'Failed to generate download link'}, 500

        return {
            'download_url': signed_url,
            'filename': job.get('jd_original_filename') or f"{job.get('title', 'job-description')}.pdf",
        }, 200
        
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

    def _extract_jd_file_text(self, jd_file):
        """Extract text from an uploaded JD file for AI parsing. Uses a
        throwaway temp path — the file itself is not persisted here; it gets
        re-uploaded (and stored in GCS) when the recruiter actually submits
        the job via create_job()."""
        if not jd_file or not jd_file.filename:
            return None
        file_extension = secure_filename(jd_file.filename).rsplit('.', 1)[-1].lower()
        if file_extension not in ['pdf', 'txt']:
            return None
        temp_name = f"jd_parse_{uuid.uuid4()}.{file_extension}"
        temp_path = os.path.join(self.upload_folder, temp_name)
        try:
            jd_file.save(temp_path)
            if self.pdf_parser:
                return self.pdf_parser.extract_text(temp_path)
            return None
        except Exception as e:
            logger.error(f"Failed to extract text from uploaded JD for AI parsing: {e}")
            return None
        finally:
            try:
                os.remove(temp_path)
            except OSError:
                pass

    def generate_jd_with_ai(self, prompt_text, recruiter_id=None, jd_file=None):
        """Generate a complete job description using Groq AI, from a text
        prompt, an uploaded JD file (parsed and structured), or both."""
        generation_id = str(uuid.uuid4())
        deduction = None

        jd_file_text = self._extract_jd_file_text(jd_file) if jd_file else None
        if jd_file and jd_file.filename and jd_file_text is None:
            return {
                'error': 'Could not read the uploaded JD file. Please upload a PDF or TXT file, or describe the role in the prompt instead.',
            }, 400
        if not (prompt_text or "").strip() and not jd_file_text:
            return {
                'error': 'Please provide a prompt describing the job role, or upload a JD file to parse.',
            }, 400

        def refund_ai_jd(reason):
            if not recruiter_id or not deduction or not deduction.get("success"):
                return None
            return self.wallet_service.credit_wallet(
                owner_id=str(recruiter_id),
                audience="recruiter",
                credits=int(PaymentConfig.RECRUITER_AI_JD_CREDITS),
                transaction_type="ai_jd_generation_refund",
                reference_type="ai_jd_prompt",
                reference_id=generation_id,
                metadata={
                    "reason": reason,
                    "original_transaction_id": (
                        (deduction.get("transaction") or {}).get("id")
                    ),
                },
                idempotency_key=f"ai-jd-generation-refund:{generation_id}",
            )

        try:
            if recruiter_id:
                deduction = self.wallet_service.debit_wallet(
                    owner_id=str(recruiter_id),
                    audience="recruiter",
                    credits=int(PaymentConfig.RECRUITER_AI_JD_CREDITS),
                    transaction_type="ai_jd_generation",
                    reference_type="ai_jd_prompt",
                    reference_id=generation_id,
                    metadata={
                        "prompt_preview": (prompt_text or "")[:160],
                    },
                    idempotency_key=f"ai-jd-generation:{generation_id}",
                )
                if not deduction.get("success"):
                    return {
                        "error": "Insufficient credits for AI JD generation",
                        "error_code": deduction.get("error_code", "insufficient_credits"),
                        "credits_required": int(PaymentConfig.RECRUITER_AI_JD_CREDITS),
                        "credits_remaining": int(deduction.get("credits_remaining", 0) or 0),
                    }, 402

            from services.llm_fallback_service import LLMFallbackService
            
            fallback_service = LLMFallbackService()

            system_prompt = """You are an expert HR recruiter and job description writer. Based on the user's input, generate a complete, professional job posting.

Return ONLY a valid JSON object (no markdown, no code fences, no explanation) with exactly these fields:

{
  "title": "Exact job title",
  "department": "One of: Engineering, Product, Design, Data & Analytics, Marketing, Sales, Customer Success, Operations, Finance, Human Resources, Legal, Security, DevOps, Quality Assurance, Research & Development",
  "location": "One of: Remote, Bangalore, Karnataka, Mumbai, Maharashtra, Delhi, NCR, Hyderabad, Telangana, Chennai, Tamil Nadu, Pune, Maharashtra, Kolkata, West Bengal, Remote (India), Remote (Global), or any other relevant location",
  "type": "One of: Full-time, Part-time, Contract, Internship, Freelance, Remote",
  "experience": "One of: Entry Level (0-1 years), 1-2 years, 2-4 years, 3-5 years, 4-6 years, 5-7 years, 6-8 years, 7+ years, 10+ years",
  "salary": "Indian salary range format like ₹12,00,000 - ₹18,00,000. Pick from: ₹3,00,000 - ₹5,00,000, ₹5,00,000 - ₹8,00,000, ₹8,00,000 - ₹12,00,000, ₹12,00,000 - ₹18,00,000, ₹18,00,000 - ₹25,00,000, ₹25,00,000 - ₹35,00,000, ₹35,00,000 - ₹50,00,000, ₹50,00,000 - ₹75,00,000, ₹75,00,000 - ₹1,00,00,000, ₹1,00,00,000 - ₹1,50,00,000",
  "skills": ["skill1", "skill2", "skill3", "skill4", "skill5"],
  "description": "A compelling 2-3 sentence job description paragraph",
  "responsibilities": ["responsibility1", "responsibility2", "responsibility3", "responsibility4", "responsibility5"],
  "requirements": ["requirement1", "requirement2", "requirement3", "requirement4", "requirement5"],
  "benefits": ["benefit1", "benefit2", "benefit3", "benefit4", "benefit5"],
  "minimum_cv_score": 50
}

Rules:
- skills should have 4-8 relevant technical/soft skills
- responsibilities, requirements, benefits should each have 4-6 items
- description should be professional, engaging, and 2-3 sentences
- All values must match the predefined options exactly where specified
- If the user mentions specific details (salary, location, etc.), use those
- Return ONLY the JSON object, nothing else"""

            if jd_file_text:
                user_request = (
                    "Extract and structure the following job description document into the "
                    "required JSON fields. Fill in any details it doesn't explicitly state with "
                    f"sensible, professional defaults.\n\n--- JD DOCUMENT ---\n{jd_file_text[:12000]}"
                )
                if (prompt_text or "").strip():
                    user_request += f"\n\n--- ADDITIONAL INSTRUCTIONS FROM RECRUITER ---\n{prompt_text.strip()}"
            else:
                user_request = f"Generate a complete job posting for: {prompt_text}"

            full_prompt = f"{system_prompt}\n\nUser request: {user_request}"

            try:
                result = fallback_service.invoke(full_prompt, json_mode=True)
                response_text = result["content"]
                usage = result.get("usage", {})
            except Exception as e:
                refund = refund_ai_jd(f"llm_fallback_exhausted: {str(e)}")
                return {
                    'error': 'AI JD generation failed due to service limits. All providers exhausted.',
                    'details': str(e),
                    'credit_refund': refund,
                }, 503

            prompt_tokens = usage.get('prompt_tokens') if isinstance(usage, dict) else None
            completion_tokens = usage.get('completion_tokens') if isinstance(usage, dict) else None
            usage_source = 'actual' if (prompt_tokens is not None or completion_tokens is not None) else 'assumed'
            
            # Clean markdown code fences if present
            if response_text.startswith('```'):
                response_text = re.sub(r'^```(?:json)?\s*', '', response_text)
                response_text = re.sub(r'\s*```$', '', response_text)

            job_data = json.loads(response_text)

            # Validate required fields exist
            required_fields = ['title', 'department', 'location', 'type', 'experience', 
                             'salary', 'skills', 'description', 'responsibilities', 
                             'requirements', 'benefits']
            for field in required_fields:
                if field not in job_data:
                    refund = refund_ai_jd(f"missing_field:{field}")
                    return {
                        'error': f'AI response missing field: {field}',
                        'credit_refund': refund,
                    }, 500

            # Ensure array fields are lists
            for field in ['skills', 'responsibilities', 'requirements', 'benefits']:
                if not isinstance(job_data[field], list):
                    job_data[field] = [job_data[field]]

            # Set defaults
            job_data.setdefault('minimum_cv_score', 50)

            if recruiter_id:
                record_usage_event(
                    {
                        'users': self.jobs_collection.database.get_collection('users')
                    },
                    action_type='ai_jd_generation',
                    actor_type='recruiter',
                    actor_id=str(recruiter_id),
                    model='llama-3.3-70b-versatile',
                    prompt_tokens=prompt_tokens,
                    completion_tokens=completion_tokens,
                    usage_source=usage_source,
                    source={
                        'type': 'jd_prompt',
                        'id': '',
                        'label': (prompt_text or '')[:120] or '[JD file upload]',
                    },
                    occurred_at=datetime.datetime.utcnow(),
                    metadata={
                        'prompt_text_length': len(prompt_text or ''),
                        'prompt_text': (prompt_text or '')[:12000],
                        'jd_file_uploaded': bool(jd_file_text),
                        'generated_jd_text': (response_text or '')[:20000],
                    }
                )

            wallet_summary = None
            if recruiter_id:
                wallet_summary = self.wallet_service.get_wallet_summary(
                    owner_id=str(recruiter_id),
                    audience="recruiter",
                )

            return {
                'job_data': job_data,
                'credits_deducted': int(PaymentConfig.RECRUITER_AI_JD_CREDITS),
                'usage_deduction': deduction,
                'wallet': wallet_summary,
            }, 200

        except json.JSONDecodeError as e:
            logger.error(f"AI response JSON parse error: {e}")
            refund = refund_ai_jd("json_parse_failed")
            return {
                'error': 'Failed to parse AI response. Please try again.',
                'credit_refund': refund,
            }, 500
        except Exception as e:
            logger.error(f"AI JD generation error: {e}")
            refund = refund_ai_jd("ai_generation_failed")
            return {
                'error': f'AI generation failed: {str(e)}',
                'credit_refund': refund,
            }, 500

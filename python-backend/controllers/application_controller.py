import datetime
from bson import ObjectId
import sys
import os
sys.path.append(os.path.join(os.path.dirname(__file__), '..'))
from services.cv_scoring_service import CVScoringService

class ApplicationController:
    def __init__(self, db_collections):
        self.applications_collection = db_collections['applications']
        self.jobs_collection = db_collections['jobs']
        self.users_collection = db_collections['users']
        self.interviews_collection = db_collections['interviews']
        
        # Initialize CV scoring service
        try:
            self.cv_scoring_service = CVScoringService()
        except Exception as e:
            print(f"Warning: CV scoring service initialization failed: {e}")
            self.cv_scoring_service = None
        
    def apply_for_job(self, job_id, user_id, application_data, user_profile):
        """Submit job application"""
        # Check if job exists
        job = self.jobs_collection.find_one({'_id': ObjectId(job_id)})
        if not job:
            return {'error': 'Job not found'}, 404
        
        # Check if CV details are completed (mandatory requirement)
        cv_details = user_profile.get('cv_details')
        if not cv_details:
            return {
                'error': 'CV details are required before applying for jobs. Please complete your CV details first.',
                'redirect': '/profile/cv-details'
            }, 400
        
        # Validate required CV sections
        validation_errors = self._validate_cv_completion(cv_details)
        if validation_errors:
            return {
                'error': 'Please complete the following required CV sections before applying:\n' + '\n'.join(validation_errors),
                'redirect': '/profile/cv-details'
            }, 400
        
        # Check if already applied
        existing_application = self.applications_collection.find_one({
            'job_id': job_id,
            'student_id': user_id
        })
        if existing_application:
            return {'error': 'You have already applied for this job'}, 400
        
        # Calculate actual CV score using AI
        cv_score = 75.0  # fallback score
        cv_score_breakdown = None
        
        if self.cv_scoring_service and cv_details:
            try:
                print("Calculating CV-JD matching score...")
                scoring_result = self.cv_scoring_service.calculate_cv_score(cv_details, job)
                cv_score = scoring_result.get('total_score', 75.0)
                cv_score_breakdown = scoring_result.get('score_breakdown')
                print(f"CV score calculated: {cv_score}")
            except Exception as e:
                print(f"Error calculating CV score: {e}")
                cv_score = 75.0
        
        application_doc = {
            'job_id': job_id,
            'student_id': user_id,
            'student_name': user_profile.get('name', ''),
            'student_email': user_profile.get('email', ''),
            'cover_letter': application_data.get('cover_letter', ''),
            'status': 'pending',
            'applied_at': datetime.datetime.utcnow(),
            'updated_at': datetime.datetime.utcnow(),
            'job_title': job.get('title', ''),
            'recruiter_id': job.get('created_by', ''),
            # AI-calculated CV score
            'cv_score': cv_score,
            'cv_score_breakdown': cv_score_breakdown,
            'interview_score': None,
            'student_profile': {
                'bio': user_profile.get('bio', ''),
                'skills': user_profile.get('skills', []),
                'experience': user_profile.get('experience', ''),
                'education': user_profile.get('education', ''),
                'phone': user_profile.get('phone', ''),
                'location': user_profile.get('location', '')
            }
        }
        
        # Insert application
        result = self.applications_collection.insert_one(application_doc)
        
        # Update job applicant count
        self.jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$inc': {'applicants': 1, 'pending': 1}}
        )
        
        application_doc['_id'] = str(result.inserted_id)
        
        return {
            'message': 'Application submitted successfully',
            'application': application_doc
        }, 201
        
    def withdraw_application(self, job_id, user_id):
        """Withdraw job application"""
        # Check if application exists
        application = self.applications_collection.find_one({
            'job_id': job_id,
            'student_id': user_id
        })
        if not application:
            return {'error': 'No application found for this job'}, 404
        
        # Check if application can be withdrawn (only pending or applied status)
        status = application.get('status', '').lower()
        if status not in ['pending', 'applied']:
            return {'error': 'Cannot withdraw application. Application is already being processed.'}, 400
        
        # Delete the application
        self.applications_collection.delete_one({
            'job_id': job_id,
            'student_id': user_id
        })
        
        # Update job applicant count
        self.jobs_collection.update_one(
            {'_id': ObjectId(job_id)},
            {'$inc': {'applicants': -1, 'pending': -1}}
        )
        
        return {'message': 'Application withdrawn successfully'}, 200
        
    def get_applications(self, user_id, user_type):
        """Retrieve applications based on user type"""
        if user_type in ['candidate', 'student']:
            # Students see their own applications
            applications = list(self.applications_collection.find({'student_id': user_id}))
            
            # Convert ObjectId to string and fetch job details
            for app in applications:
                app['_id'] = str(app['_id'])
                # Normalize datetime serialization for frontend
                if isinstance(app.get('applied_at'), datetime.datetime):
                    app['applied_at'] = app['applied_at'].isoformat()
                if isinstance(app.get('updated_at'), datetime.datetime):
                    app['updated_at'] = app['updated_at'].isoformat()
                # Ensure scores exist for UI
                if app.get('cv_score') is None:
                    app['cv_score'] = 85.0  # fallback placeholder for legacy data
                # expose interview_score if present (legacy docs may miss it)
                if 'interview_score' not in app:
                    app['interview_score'] = None
                    
                job = self.jobs_collection.find_one({'_id': ObjectId(app['job_id'])})
                if job:
                    app['job_details'] = {
                        'title': job.get('title'),
                        'company': job.get('company', 'TechCorp Solutions'),
                        'location': job.get('location'),
                        'type': job.get('type'),
                        'department': job.get('department'),
                        'logo': job.get('logo')
                    }
                    
                # Get proctoring score from most recent completed interview
                completed_interview = self.interviews_collection.find_one(
                    {'application_id': app['_id'], 'status': 'completed'},
                    sort=[('updated_at', -1)]
                )
                if completed_interview and completed_interview.get('proctoring_score'):
                    proctoring_score = completed_interview.get('proctoring_score')
                    # Handle both numeric and string values, exclude 'N/A'
                    if isinstance(proctoring_score, (int, float)):
                        app['proctoring_score'] = proctoring_score
                    elif isinstance(proctoring_score, str) and proctoring_score.replace('.', '', 1).isdigit():
                        app['proctoring_score'] = float(proctoring_score)
                    else:
                        app['proctoring_score'] = None
                else:
                    app['proctoring_score'] = None
                    
                # Whether an interview report is available
                app['report_available'] = completed_interview is not None
            
            return applications, 200
            
        elif user_type == 'recruiter':
            # Recruiters see applications for their jobs
            recruiter_jobs = list(self.jobs_collection.find({'created_by': user_id}, {'_id': 1}))
            job_ids = [str(job['_id']) for job in recruiter_jobs]
            
            applications = list(self.applications_collection.find({'job_id': {'$in': job_ids}}))
            
            # Convert ObjectId to string and add job details
            for app in applications:
                app['_id'] = str(app['_id'])
                # Normalize datetime serialization for frontend
                if isinstance(app.get('applied_at'), datetime.datetime):
                    app['applied_at'] = app['applied_at'].isoformat()
                if isinstance(app.get('updated_at'), datetime.datetime):
                    app['updated_at'] = app['updated_at'].isoformat()
                if app.get('cv_score') is None:
                    app['cv_score'] = 85.0
                if 'interview_score' not in app:
                    app['interview_score'] = None
                    
                job = self.jobs_collection.find_one({'_id': ObjectId(app['job_id'])})
                if job:
                    app['job_details'] = {
                        'title': job.get('title'),
                        'department': job.get('department'),
                        'location': job.get('location'),
                        'logo': job.get('logo'),
                        'company': job.get('company', 'TechCorp Solutions')
                    }
                    
                # Provide base URL for CV retrieval; the frontend can append '?token=...'
                app['cv_url'] = f"/api/applications/{app['_id']}/cv"
                
                # Get proctoring score from most recent completed interview
                completed_interview = self.interviews_collection.find_one(
                    {'application_id': app['_id'], 'status': 'completed'},
                    sort=[('updated_at', -1)]
                )
                if completed_interview and completed_interview.get('proctoring_score'):
                    proctoring_score = completed_interview.get('proctoring_score')
                    # Handle both numeric and string values, exclude 'N/A'
                    if isinstance(proctoring_score, (int, float)):
                        app['proctoring_score'] = proctoring_score
                    elif isinstance(proctoring_score, str) and proctoring_score.replace('.', '', 1).isdigit():
                        app['proctoring_score'] = float(proctoring_score)
                    else:
                        app['proctoring_score'] = None
                else:
                    app['proctoring_score'] = None
                    
                # Whether a report is available
                app['report_available'] = completed_interview is not None
            
            return applications, 200
        
        else:
            return {'error': 'Unauthorized'}, 403
            
    def update_application_status(self, application_id, recruiter_id, new_status):
        """Update application status (recruiters only)"""
        if new_status not in ['pending', 'reviewed', 'shortlisted', 'interviewed', 'selected', 'rejected']:
            return {'error': 'Invalid status'}, 400
        
        # Find application
        application = self.applications_collection.find_one({'_id': ObjectId(application_id)})
        if not application:
            return {'error': 'Application not found'}, 404
        
        # Verify the job belongs to current recruiter
        job = self.jobs_collection.find_one({'_id': ObjectId(application['job_id']), 'created_by': recruiter_id})
        if not job:
            return {'error': 'Unauthorized to update this application'}, 403
        
        old_status = application.get('status', 'pending')
        
        # Update application status
        self.applications_collection.update_one(
            {'_id': ObjectId(application_id)},
            {
                '$set': {
                    'status': new_status,
                    'updated_at': datetime.datetime.utcnow(),
                    'updated_by': recruiter_id
                }
            }
        )
        
        # Update job statistics
        # Build proper increments for known job counters
        job_update = {}
        status_counters = ['pending', 'interviewed', 'selected', 'rejected']  # keep only fields that exist on jobs

        if old_status in status_counters:
            job_update[old_status] = -1
        if new_status in status_counters:
            job_update[new_status] = job_update.get(new_status, 0) + 1

        if job_update:
            self.jobs_collection.update_one({'_id': ObjectId(application['job_id'])}, {'$inc': job_update})
        
        return {'message': 'Application status updated successfully'}, 200
        
    def get_application_by_id(self, application_id, user_id, user_type):
        """Get a single application document by id with job details"""
        try:
            app_doc = self.applications_collection.find_one({'_id': ObjectId(application_id)})
        except Exception:
            return {'error': 'Invalid application id'}, 400

        if not app_doc:
            return {'error': 'Application not found'}, 404

        if user_type in ['candidate', 'student']:
            if app_doc.get('student_id') != user_id:
                return {'error': 'Unauthorized'}, 403
        elif user_type == 'recruiter':
            job = self.jobs_collection.find_one({'_id': ObjectId(app_doc['job_id'])})
            if not job or job.get('created_by') != user_id:
                return {'error': 'Unauthorized'}, 403
        else:
            return {'error': 'Unauthorized'}, 403

        # shape response
        app_doc['_id'] = str(app_doc['_id'])
        if isinstance(app_doc.get('applied_at'), datetime.datetime):
            app_doc['applied_at'] = app_doc['applied_at'].isoformat()
        if isinstance(app_doc.get('updated_at'), datetime.datetime):
            app_doc['updated_at'] = app_doc['updated_at'].isoformat()
        if app_doc.get('cv_score') is None:
            app_doc['cv_score'] = 85.0
        if 'interview_score' not in app_doc:
            app_doc['interview_score'] = None

        job = self.jobs_collection.find_one({'_id': ObjectId(app_doc['job_id'])})
        if job:
            app_doc['job_details'] = {
                'title': job.get('title'),
                'company': job.get('company', 'TechCorp Solutions'),
                'location': job.get('location'),
                'type': job.get('type'),
                'department': job.get('department'),
                'logo': job.get('logo')
            }

        # whether report exists
        app_doc['report_available'] = self.interviews_collection.find_one({'application_id': app_doc['_id'], 'status': 'completed'}) is not None

        return app_doc, 200
        
    def get_interview_report(self, application_id, user_id, user_type):
        """Return the latest interview report for a given application"""
        try:
            app_doc = self.applications_collection.find_one({'_id': ObjectId(application_id)})
        except Exception:
            return {'error': 'Invalid application id'}, 400

        if not app_doc:
            return {'error': 'Application not found'}, 404

        if user_type in ['candidate', 'student']:
            if app_doc.get('student_id') != user_id:
                return {'error': 'Unauthorized'}, 403
        elif user_type == 'recruiter':
            job = self.jobs_collection.find_one({'_id': ObjectId(app_doc['job_id'])})
            if not job or job.get('created_by') != user_id:
                return {'error': 'Unauthorized'}, 403
        else:
            return {'error': 'Unauthorized'}, 403

        report = self.interviews_collection.find_one(
            {'application_id': application_id, 'status': 'completed'},
            sort=[('updated_at', -1)]
        )
        if not report:
            return {'error': 'Report not found'}, 404

        # Return lightweight report summary
        payload = {
            'session_id': report.get('session_id'),
            'final_score': report.get('final_score'),
            'proctoring_score': report.get('proctoring_score'),
            'evaluation': report.get('evaluation')
        }
        return payload, 200
    
    def _validate_cv_completion(self, cv_details):
        """Validate that required CV sections are completed"""
        errors = []
        
        # Education validation
        education = cv_details.get('education', [])
        has_valid_education = any(
            edu.get('degree', '').strip() and 
            edu.get('institution', '').strip() and 
            edu.get('year', '').strip()
            for edu in education
        )
        if not has_valid_education:
            errors.append('- At least one complete education entry is required')
        
        # Skills validation
        skills = cv_details.get('skills', {})
        technical_skills = skills.get('technical', [])
        if not technical_skills or len(technical_skills) == 0:
            errors.append('- Technical Skills are required')
        
        # Projects validation
        projects = cv_details.get('projects', [])
        has_valid_project = any(
            project.get('title', '').strip() and 
            project.get('description', '').strip()
            for project in projects
        )
        if not has_valid_project:
            errors.append('- At least one complete project entry is required')
        
        # Salary Expectations validation
        salary_expectations = cv_details.get('salaryExpectations', {})
        if not salary_expectations.get('expectedSalary'):
            errors.append('- Expected Salary is required')
        
        return errors
    
    def recalculate_cv_score(self, application_id, user_id, user_type):
        """Recalculate CV score for an existing application"""
        try:
            # Find application
            application = self.applications_collection.find_one({'_id': ObjectId(application_id)})
            if not application:
                return {'error': 'Application not found'}, 404
            
            # Authorization check
            if user_type == 'recruiter':
                job = self.jobs_collection.find_one({'_id': ObjectId(application['job_id'])})
                if not job or job.get('created_by') != user_id:
                    return {'error': 'Unauthorized'}, 403
            elif user_type in ['candidate', 'student']:
                if application.get('student_id') != user_id:
                    return {'error': 'Unauthorized'}, 403
            else:
                return {'error': 'Unauthorized'}, 403
            
            # Get student profile and CV details
            student = self.users_collection.find_one({'_id': ObjectId(application['student_id'])})
            if not student:
                return {'error': 'Student profile not found'}, 404
            
            cv_details = student.get('cv_details')
            if not cv_details:
                return {'error': 'CV details not found for this student'}, 400
            
            # Get job details
            job = self.jobs_collection.find_one({'_id': ObjectId(application['job_id'])})
            if not job:
                return {'error': 'Job not found'}, 404
            
            # Calculate new CV score
            if not self.cv_scoring_service:
                return {'error': 'CV scoring service not available'}, 503
            
            try:
                print(f"Recalculating CV score for application {application_id}...")
                scoring_result = self.cv_scoring_service.calculate_cv_score(cv_details, job)
                new_cv_score = scoring_result.get('total_score', 75.0)
                new_cv_score_breakdown = scoring_result.get('score_breakdown')
                
                # Update application with new score
                self.applications_collection.update_one(
                    {'_id': ObjectId(application_id)},
                    {
                        '$set': {
                            'cv_score': new_cv_score,
                            'cv_score_breakdown': new_cv_score_breakdown,
                            'updated_at': datetime.datetime.utcnow()
                        }
                    }
                )
                
                print(f"CV score updated: {new_cv_score}")
                
                return {
                    'message': 'CV score recalculated successfully',
                    'cv_score': new_cv_score,
                    'cv_score_breakdown': new_cv_score_breakdown
                }, 200
                
            except Exception as e:
                print(f"Error recalculating CV score: {e}")
                return {'error': f'Failed to recalculate CV score: {str(e)}'}, 500
                
        except Exception as e:
            return {'error': f'Internal error: {str(e)}'}, 500

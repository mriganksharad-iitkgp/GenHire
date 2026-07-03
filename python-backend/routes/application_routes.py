from flask import Blueprint, request, jsonify, send_file
from flask_cors import cross_origin
import os
import datetime
import uuid
from controllers.application_controller import ApplicationController
from middleware.auth_middleware import token_required
from middleware.rate_limiter import rate_limit
from config.database import db_config
from bson import ObjectId

application_bp = Blueprint('applications', __name__, url_prefix='/api')

# Initialize application controller
collections = db_config.get_collections()
application_controller = ApplicationController(collections)


def _format_cv_from_details(cv_details):
    if not isinstance(cv_details, dict):
        return ""

    parts = []
    personal = cv_details.get('personalInfo', {})
    name = personal.get('fullName')
    if name:
        parts.append(f"Name: {name}")
    if personal.get('email'):
        parts.append(f"Email: {personal.get('email')}")
    if personal.get('phone'):
        parts.append(f"Phone: {personal.get('phone')}")

    summary = cv_details.get('professionalSummary')
    if summary:
        parts.append("\nProfessional Summary")
        parts.append(str(summary))

    education = cv_details.get('education', []) or []
    if education:
        parts.append("\nEducation")
        for edu in education:
            parts.append(f"- {edu.get('degree', '')} at {edu.get('institution', '')}")

    experience = cv_details.get('workExperience', []) or []
    if experience:
        parts.append("\nWork Experience")
        for exp in experience:
            parts.append(f"- {exp.get('position', '')} at {exp.get('company', '')}")

    skills = cv_details.get('skills', {})
    technical_skills = skills.get('technical', []) if isinstance(skills, dict) else []
    if technical_skills:
        parts.append("\nSkills")
        parts.append(", ".join(str(skill) for skill in technical_skills if skill))

    projects = cv_details.get('projects', []) or []
    if projects:
        parts.append("\nProjects")
        for project in projects:
            parts.append(f"- {project.get('name', '')}: {project.get('description', '')}")

    return "\n".join(part for part in parts if part)


def _generate_profile_cv_pdf(cv_text, application_id):
    output_dir = os.path.join('uploads', 'generated_profile_cvs')
    os.makedirs(output_dir, exist_ok=True)
    output_path = os.path.join(output_dir, f"application_{application_id}_{uuid.uuid4().hex[:8]}.pdf")

    from matplotlib import pyplot as plt
    from matplotlib.backends.backend_pdf import PdfPages

    lines = [line for line in str(cv_text or '').splitlines()]
    if not lines:
        lines = ["Profile CV details are available but currently empty."]

    lines_per_page = 44
    with PdfPages(output_path) as pdf:
        for idx in range(0, len(lines), lines_per_page):
            chunk = lines[idx:idx + lines_per_page]
            fig = plt.figure(figsize=(8.27, 11.69))
            fig.text(0.06, 0.96, "\n".join(chunk), va='top', ha='left', family='monospace', fontsize=10)
            plt.axis('off')
            pdf.savefig(fig)
            plt.close(fig)

    return output_path

@application_bp.route('/jobs/<job_id>/apply', methods=['POST'])
@cross_origin()
@token_required
@rate_limit(max_calls=10, window_seconds=3600)
def apply_for_job(current_user, job_id):
    """
    Apply for a job (candidates only)
    
    Request Body:
        cover_letter: str - Optional cover letter
        cv_id: str - Optional CV ID to use for application (if not provided, uses primary CV or manual entry)
    """
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can apply for jobs.'}), 403
    
    data = request.get_json() or {}
    user_id = str(current_user['_id'])
    
    # Extract optional cv_id from request data
    cv_id = data.get('cv_id')  # None if not provided
    
    result, status_code = application_controller.apply_for_job(
        job_id, 
        user_id, 
        data, 
        current_user,
        cv_id=cv_id  # Pass cv_id to controller
    )
    return jsonify(result), status_code

@application_bp.route('/jobs/<job_id>/withdraw', methods=['DELETE'])
@cross_origin()
@token_required
def withdraw_application(current_user, job_id):
    """Withdraw application for a job (candidates only)"""
    # Normalize user_type with backward compatibility (missing -> candidate)
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['candidate', 'student']:
        return jsonify({'error': 'Unauthorized. Only candidates can withdraw applications.'}), 403
    
    user_id = str(current_user['_id'])
    result, status_code = application_controller.withdraw_application(job_id, user_id)
    return jsonify(result), status_code

@application_bp.route('/applications', methods=['GET'])
@cross_origin()
@token_required
def get_applications(current_user):
    """Get applications - candidates see their own, recruiters see applications for their jobs"""
    # Normalize user_type with default for legacy users
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_applications(user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/status', methods=['PUT'])
@cross_origin()
@token_required
def update_application_status(current_user, application_id):
    """Update application status (recruiters only)"""
    if current_user.get('user_type') != 'recruiter':
        return jsonify({'error': 'Unauthorized. Only recruiters can update application status.'}), 403
    
    data = request.get_json()
    new_status = data.get('status')
    recruiter_id = str(current_user['_id'])
    
    result, status_code = application_controller.update_application_status(application_id, recruiter_id, new_status)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/cv', methods=['GET'])
@cross_origin()
@token_required
def get_application_cv(current_user, application_id):
    """Stream the exact CV used for a given application (candidate owner or recruiter owner)."""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    if user_type not in ['recruiter', 'candidate', 'student']:
        return jsonify({'error': 'Unauthorized'}), 403

    # Find the application
    try:
        app_doc = collections['applications'].find_one({'_id': ObjectId(application_id)})
    except Exception:
        return jsonify({'error': 'Invalid application id'}), 400

    if not app_doc:
        return jsonify({'error': 'Application not found'}), 404

    current_user_id = str(current_user['_id'])

    if user_type == 'recruiter':
        # Verify recruiter owns the job
        job = collections['jobs'].find_one({'_id': ObjectId(app_doc['job_id'])})
        if not job or job.get('created_by') != current_user_id:
            return jsonify({'error': 'Unauthorized to view this CV'}), 403
    else:
        # Candidate can only view their own application CV
        if str(app_doc.get('student_id')) != current_user_id:
            return jsonify({'error': 'Unauthorized to view this CV'}), 403

    # Look up candidate user for CV path
    try:
        student_user = collections['users'].find_one({'_id': ObjectId(app_doc['student_id'])})
    except Exception:
        student_user = None

    if not student_user:
        return jsonify({'error': 'Candidate not found'}), 404

    cv_path = None
    cv_id = app_doc.get('cv_id')
    cv_snapshot = app_doc.get('cv_snapshot') or {}

    # Priority 1: Exact CV selected during application
    if cv_id:
        for cv in (student_user.get('cv_uploads') or []):
            if cv.get('cv_id') == cv_id:
                # Check GCS first (deployed version)
                gcs_path = cv.get('gcs_path')
                if gcs_path:
                    try:
                        from services import gcs_service
                        if gcs_service.is_gcs_configured():
                            from flask import redirect
                            signed_url = gcs_service.generate_signed_url(gcs_path, expiration_minutes=60)
                            return redirect(signed_url)
                    except Exception as e:
                        import logging
                        logging.getLogger(__name__).warning(f"GCS signed URL failed for application CV: {e}")
                # Check local file
                if cv.get('file_path') and not cv['file_path'].startswith('gs://') and os.path.exists(cv.get('file_path')):
                    cv_path = cv.get('file_path')
                    break

    # Priority 2: Snapshot path captured at application time
    if not cv_path:
        snapshot_file_path = cv_snapshot.get('file_path')
        if snapshot_file_path and not snapshot_file_path.startswith('gs://') and os.path.exists(snapshot_file_path):
            cv_path = snapshot_file_path

    # Priority 3: Try GCS for primary CV (deployed version fallback)
    if not cv_path:
        for cv in (student_user.get('cv_uploads') or []):
            gcs_path = cv.get('gcs_path')
            if gcs_path:
                try:
                    from services import gcs_service
                    if gcs_service.is_gcs_configured():
                        from flask import redirect
                        signed_url = gcs_service.generate_signed_url(gcs_path, expiration_minutes=60)
                        return redirect(signed_url)
                except Exception:
                    pass

    # Priority 4: Legacy fallback for older application records
    if not cv_path and student_user.get('cv_path') and os.path.exists(student_user.get('cv_path')):
        cv_path = student_user.get('cv_path')

    if cv_path:
        return send_file(cv_path)

    # Manual/profile CV: generate PDF from stored snapshot/details
    if app_doc.get('cv_source') == 'cv_manual_entry':
        cv_text = cv_snapshot.get('text') or _format_cv_from_details(student_user.get('cv_details'))
        if cv_text:
            generated_pdf = _generate_profile_cv_pdf(cv_text, application_id)
            return send_file(generated_pdf, mimetype='application/pdf')

    return jsonify({'error': 'CV not found for this application'}), 404

@application_bp.route('/applications/<application_id>', methods=['GET'])
@cross_origin()
@token_required
def get_application_by_id(current_user, application_id):
    """Get a single application document by id with job details"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_application_by_id(application_id, user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/interview-report', methods=['GET'])
@cross_origin()
@token_required
def get_interview_report(current_user, application_id):
    """Return the latest interview report for a given application"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.get_interview_report(application_id, user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/recalculate-score', methods=['POST'])
@cross_origin()
@token_required
def recalculate_cv_score(current_user, application_id):
    """Recalculate CV score for an existing application"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    result, status_code = application_controller.recalculate_cv_score(application_id, user_id, user_type)
    return jsonify(result), status_code

@application_bp.route('/applications/<application_id>/update-score', methods=['PUT'])
@cross_origin()
@token_required
def update_interview_score(current_user, application_id):
    """Update interview score for an application"""
    user_type = str((current_user.get('user_type') or 'candidate')).strip().lower()
    user_id = str(current_user['_id'])
    
    try:
        data = request.get_json()
        interview_score = data.get('interview_score')
        
        if interview_score is None:
            return jsonify({'error': 'interview_score is required'}), 400
            
        if not isinstance(interview_score, (int, float)) or interview_score < 0 or interview_score > 100:
            return jsonify({'error': 'interview_score must be a number between 0 and 100'}), 400
        
        result, status_code = application_controller.update_interview_score(application_id, user_id, user_type, interview_score)
        return jsonify(result), status_code
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Debug endpoints
@application_bp.route('/debug/applications', methods=['GET'])
@cross_origin()
def debug_applications():
    """Debug endpoint to see what applications exist"""
    applications = list(collections['applications'].find({}))
    for app in applications:
        app['_id'] = str(app['_id'])
        if isinstance(app.get('applied_at'), datetime.datetime):
            app['applied_at'] = app['applied_at'].isoformat()
        if isinstance(app.get('updated_at'), datetime.datetime):
            app['updated_at'] = app['updated_at'].isoformat()
    return jsonify({'applications': applications, 'count': len(applications)})

from flask import Blueprint, request, jsonify
from flask_cors import cross_origin
from controllers.profile_controller import ProfileController
from middleware.auth_middleware import token_required, recruiter_required
from config.database import db_config
from bson import ObjectId
import random
from datetime import datetime, timedelta

profile_bp = Blueprint('profile', __name__, url_prefix='/api')

# Initialize profile controller
collections = db_config.get_collections()
profile_controller = ProfileController(collections)

@profile_bp.route('/profile', methods=['GET'])
@cross_origin()
@token_required
def get_profile(current_user):
    """Get user profile data"""
    result, status_code = profile_controller.get_profile(str(current_user['_id']))
    return jsonify(result), status_code

@profile_bp.route('/profile', methods=['PUT'])
@cross_origin()
@token_required
def update_profile(current_user):
    """Update user profile data"""
    data = request.get_json()
    result, status_code = profile_controller.update_profile(str(current_user['_id']), data)
    return jsonify(result), status_code

@profile_bp.route('/company-profile', methods=['PUT'])
@cross_origin()
@token_required
def update_company_profile(current_user):
    """Update company profile data for recruiters"""
    data = request.get_json()
    result, status_code = profile_controller.update_company_profile(str(current_user['_id']), data)
    return jsonify(result), status_code

@profile_bp.route('/cv-details', methods=['GET'])
@cross_origin()
@token_required
def get_cv_details(current_user):
    """Get CV details for the current user"""
    result, status_code = profile_controller.get_cv_details(str(current_user['_id']))
    return jsonify(result), status_code

@profile_bp.route('/cv-details', methods=['PUT'])
@cross_origin()
@token_required
def update_cv_details(current_user):
    """Update CV details for the current user"""
    data = request.get_json()
    result, status_code = profile_controller.update_cv_details(str(current_user['_id']), data)
    return jsonify(result), status_code


@profile_bp.route('/recruiter/cost-statistics', methods=['GET'])
@cross_origin()
@token_required
def get_recruiter_cost_statistics(current_user):
    """Get cost statistics for the logged in recruiter based on their actual data"""
    try:
        from services.credit_service import (
            calculate_recruiter_credits,
            generate_usage_history,
            generate_job_breakdown
        )
        
        # Verify user is a recruiter
        if current_user.get('user_type') != 'recruiter':
            return jsonify({'success': False, 'message': 'Only recruiters can access cost statistics'}), 403
        
        recruiter_id = str(current_user['_id'])
        db = db_config.get_db()
        
        # Get recruiter's jobs - query with string ID (consistent with admin portal)
        jobs = list(db.jobs.find({'created_by': recruiter_id}))
        
        # Debug log
        print(f"[Cost Stats] Recruiter {recruiter_id} has {len(jobs)} jobs")
        
        # Get applications for recruiter's jobs (only visible ones - CV scoring complete)
        job_ids = [str(job['_id']) for job in jobs]
        all_applications = list(db.applications.find({
            'job_id': {'$in': job_ids},
            'is_visible': True
        })) if job_ids else []
        applications_count = len(all_applications)
        
        # Count ALL interviews (for summary/overview stats)
        all_interviews_count = len([app for app in all_applications if str(app.get('status', '')).lower() in ['interviewed', 'selected', 'rejected']])
        
        # Count interviews in the LAST 30 DAYS only (for credit/quota calculation)
        # Use updated_at (when status was changed to interviewed), not applied_at (when candidate applied)
        thirty_days_ago = datetime.utcnow() - timedelta(days=30)
        interviews_count_last_30_days = len([
            app for app in all_applications
            if str(app.get('status', '')).lower() in ['interviewed', 'selected', 'rejected']
            and app.get('updated_at', datetime.min) >= thirty_days_ago
        ])
        
        # Debug log
        print(f"[Cost Stats] Applications: {applications_count}, All Interviews: {all_interviews_count}, Last 30 days: {interviews_count_last_30_days}")
        
        # Get recruiter's subscription
        subscription = db.subscriptions.find_one({
            'employer_id': ObjectId(recruiter_id),
            'status': 'active'
        })
        
        # Get plan details if subscription exists
        plan = None
        if subscription and subscription.get('plan_id'):
            plan = db.plans.find_one({'_id': subscription['plan_id']})
        
        # Calculate credits using shared service (uses last-30-days interviews for quota)
        credits_data = calculate_recruiter_credits(
            recruiter=current_user,
            jobs=jobs,
            applications_count=applications_count,
            interviews_count=interviews_count_last_30_days,
            plan=plan,
            add_variation=True
        )
        
        # Generate usage history from real interview data
        usage_history = generate_usage_history(
            credits_data['breakdown']['cloudflare'],
            credits_data['breakdown']['nlp'],
            credits_data['breakdown']['llm'],
            weeks=6,
            db=db,
            job_ids=job_ids
        )
        
        # Use last-30-days interview count for credit quota
        interviews_used_for_quota = interviews_count_last_30_days
        
        # Generate job breakdown
        job_breakdown = generate_job_breakdown(jobs, max_jobs=10)
        
        # Generate recent activity based on applications
        recent_activity = []
        # Fixed credit costs per activity type (deterministic)
        activity_types = [
            ('CV Analysis', 'nlp', 27),
            ('Video Interview', 'cloudflare', 80),
            ('Interview Evaluation', 'llm', 42),
            ('Job Description Matching', 'nlp', 15),
        ]
        
        sorted_applications = sorted(all_applications, key=lambda x: x.get('applied_at', datetime.min), reverse=True)[:10]
        for i, app in enumerate(sorted_applications):
            activity_type = activity_types[i % len(activity_types)]
            job = next((j for j in jobs if str(j['_id']) == app.get('job_id')), None)
            
            recent_activity.append({
                'id': i + 1,
                'action': activity_type[0],
                'job': job.get('title', 'Unknown Job') if job else 'Unknown Job',
                'credits': activity_type[2],
                'service': activity_type[1],
                'timestamp': app.get('applied_at', datetime.utcnow()).strftime('%Y-%m-%d %H:%M')
            })
        
        # If no applications, show placeholder activity based on jobs
        today = datetime.utcnow()
        if not recent_activity:
            for i in range(min(6, max(1, len(jobs)))):
                activity_type = activity_types[i % len(activity_types)]
                # Deterministic timestamp offset based on index
                timestamp = today - timedelta(hours=(i + 1) * 12)
                recent_activity.append({
                    'id': i + 1,
                    'action': activity_type[0],
                    'job': jobs[i % len(jobs)].get('title', 'Sample Job') if jobs else 'No Jobs Yet',
                    'credits': activity_type[2],
                    'service': activity_type[1],
                    'timestamp': timestamp.strftime('%Y-%m-%d %H:%M')
                })
        
        cost_data = {
            'recruiter': {
                'name': current_user.get('name', 'Recruiter'),
                'email': current_user.get('email', ''),
                'company': current_user.get('company_name', 'Company'),
                'joinedDate': current_user.get('created_at', datetime.utcnow()).strftime('%Y-%m-%d') if isinstance(current_user.get('created_at'), datetime) else str(current_user.get('created_at', ''))[:10]
            },
            'plan': {
                'name': credits_data['plan']['name'],
                'interviews_allowed': (subscription.get('interviews_allowed') or 2) if subscription else 2,
                'interviews_remaining': max(0, ((subscription.get('interviews_allowed') or 2) - interviews_used_for_quota) if subscription else (2 - interviews_used_for_quota)),
                'interviews_used': min(interviews_used_for_quota, (subscription.get('interviews_allowed') or 2) if subscription else 2),
                'expires_at': subscription.get('expires_at').strftime('%Y-%m-%d') if subscription and subscription.get('expires_at') else None
            },
            'credits': {
                'allocated': credits_data['allocated'],
                'used': credits_data['used'],
                'available': credits_data['available'],
                'usage_percentage': credits_data['usage_percentage'],
                'cloudflare': {
                    'allocated': credits_data['allocation']['cloudflare'],
                    'used': credits_data['breakdown']['cloudflare']
                },
                'nlp': {
                    'allocated': credits_data['allocation']['nlp'],
                    'used': credits_data['breakdown']['nlp']
                },
                'llm': {
                    'allocated': credits_data['allocation']['llm'],
                    'used': credits_data['breakdown']['llm']
                }
            },
            'usageHistory': usage_history,
            'recentActivity': recent_activity,
            'jobBreakdown': job_breakdown,
            'summary': {
                'totalJobs': credits_data['activity']['total_jobs'],
                'totalApplicants': credits_data['activity']['total_applicants'],
                'totalInterviews': interviews_count_last_30_days,
                'activeJobs': credits_data['activity']['active_jobs']
            }
        }
        
        return jsonify({'success': True, 'data': cost_data}), 200
        
    except Exception as e:
        import traceback
        traceback.print_exc()
        return jsonify({'success': False, 'message': str(e)}), 500
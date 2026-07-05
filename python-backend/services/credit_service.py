"""
Credit Service - Standardized credit calculation for cost statistics.
Used by both admin panel and recruiter portal for consistency.
"""
from datetime import datetime, timedelta
import random


# Credit allocation by plan tier
PLAN_CREDITS = {
    'free': 500,
    'starter': 2000,
    'growth': 5000,
    'professional': 5000,
    'recruiter-max': 10000,
    'max': 10000,
    'default': 2000
}

# Service distribution percentages
SERVICE_DISTRIBUTION = {
    'cloudflare': 0.35,  # Video processing & face verification
    'nlp': 0.40,         # CV analysis & job matching (Gemini)
    'llm': 0.25          # Interview questions & evaluation (ChatGPT)
}

# Cost per activity type (in credits)
ACTIVITY_COSTS = {
    'interview': 150,      # Per interview conducted
    'cv_analysis': 25,     # Per CV analyzed
    'job_posting': 50,     # Per job posted
    'video_processing': 75 # Per video processed
}


def get_plan_credits(subscription_plan=None, plan_name=None):
    """
    Get base credits allocation based on subscription plan.
    Handles both subscription object and plan name string.
    """
    if plan_name:
        plan_lower = plan_name.lower() if plan_name else ''
    elif subscription_plan:
        plan_lower = subscription_plan.lower() if isinstance(subscription_plan, str) else ''
    else:
        return PLAN_CREDITS['default']
    
    for tier, credits in PLAN_CREDITS.items():
        if tier in plan_lower:
            return credits
    
    return PLAN_CREDITS['default']


def calculate_service_allocation(base_credits):
    """
    Calculate credit allocation per service.
    Returns dict with allocated credits for each service.
    """
    return {
        'cloudflare': int(base_credits * SERVICE_DISTRIBUTION['cloudflare']),
        'nlp': int(base_credits * SERVICE_DISTRIBUTION['nlp']),
        'llm': int(base_credits * SERVICE_DISTRIBUTION['llm'])
    }


def calculate_usage_factor(total_interviews, total_applicants, base_credits):
    """
    Calculate usage factor based on actual activity.
    Returns a float between 0.05 and 0.95.
    """
    if base_credits <= 0:
        return 0.05
    
    # Calculate based on activity
    activity_credits = (
        total_interviews * ACTIVITY_COSTS['interview'] +
        total_applicants * ACTIVITY_COSTS['cv_analysis']
    )
    
    raw_factor = activity_credits / base_credits
    
    # Clamp between 0.05 (new users show some usage) and 0.95
    return min(0.95, max(0.05, raw_factor))


def calculate_recruiter_credits(recruiter, jobs, applications_count, interviews_count=None, plan=None, add_variation=False):
    """
    Calculate comprehensive credit statistics for a recruiter based on REAL activity data.
    
    Args:
        recruiter: Recruiter user document
        jobs: List of job documents created by this recruiter
        applications_count: Total number of applications for recruiter's jobs (from actual DB query)
        interviews_count: Total number of completed interviews (applications with interviewed/selected/rejected status)
        plan: Optional plan document from subscriptions
        add_variation: Deprecated - kept for backward compatibility but ignored
    
    Returns:
        dict with full credit statistics based on actual usage
    """
    # Determine base credits from plan
    if plan:
        plan_name = plan.get('name', '')
    else:
        plan_name = recruiter.get('subscription_plan', '')
    
    base_credits = get_plan_credits(plan_name=plan_name)
    
    # Calculate service allocations
    allocation = calculate_service_allocation(base_credits)
    
    # Calculate REAL activity metrics from actual data
    # Use passed-in counts when available (from actual DB queries), fall back to job fields
    total_applicants = applications_count if applications_count is not None else sum(job.get('applicants', 0) for job in jobs)
    total_interviews = interviews_count if interviews_count is not None else sum(job.get('interviewed', 0) for job in jobs)
    total_jobs = len(jobs)
    active_jobs = len([j for j in jobs if str(j.get('status', '')).lower() == 'active'])
    
    # Calculate REAL usage based on actual activity (deterministic)
    # Each activity has a fixed credit cost
    interview_credits = total_interviews * ACTIVITY_COSTS['interview']  # 150 per interview
    cv_credits = total_applicants * ACTIVITY_COSTS['cv_analysis']       # 25 per CV
    job_posting_credits = total_jobs * ACTIVITY_COSTS['job_posting']    # 50 per job
    
    total_activity_credits = interview_credits + cv_credits + job_posting_credits
    
    # Distribute across services based on activity type
    # Cloudflare: Video interviews (35% of interview credits)
    # NLP: CV analysis (all CV credits + 40% of job posting)
    # LLM: Interview evaluation (65% of interview credits + 60% of job posting)
    
    cloudflare_used = min(allocation['cloudflare'], int(interview_credits * 0.35) + int(total_jobs * 15))
    nlp_used = min(allocation['nlp'], cv_credits + int(job_posting_credits * 0.40))
    llm_used = min(allocation['llm'], int(interview_credits * 0.65) + int(job_posting_credits * 0.60))
    
    # Ensure minimum baseline for new recruiters (5% of allocation)
    if total_activity_credits == 0:
        cloudflare_used = int(allocation['cloudflare'] * 0.05)
        nlp_used = int(allocation['nlp'] * 0.05)
        llm_used = int(allocation['llm'] * 0.05)
    
    total_used = cloudflare_used + nlp_used + llm_used
    
    # Determine department
    department = recruiter.get('department') or recruiter.get('company_name') or 'General'
    if not department or department == 'General':
        company = recruiter.get('company_name', '').lower()
        if any(term in company for term in ['tech', 'software', 'it', 'digital']):
            department = recruiter.get('company_name', 'TechCorp Solutions')
        elif any(term in company for term in ['hr', 'human', 'talent']):
            department = recruiter.get('company_name', 'HR Solutions')
        elif any(term in company for term in ['sale', 'business', 'revenue']):
            department = recruiter.get('company_name', 'Sales Dept')
        else:
            department = recruiter.get('company_name') or 'General'
    
    return {
        'id': str(recruiter['_id']),
        'name': recruiter.get('name', 'Unknown Recruiter'),
        'email': recruiter.get('email', ''),
        'department': department,
        'company': recruiter.get('company_name', ''),
        'allocated': base_credits,
        'used': total_used,
        'available': base_credits - total_used,
        'usage_percentage': round((total_used / base_credits * 100) if base_credits > 0 else 0, 1),
        'breakdown': {
            'cloudflare': cloudflare_used,
            'nlp': nlp_used,
            'llm': llm_used
        },
        'allocation': {
            'cloudflare': allocation['cloudflare'],
            'nlp': allocation['nlp'],
            'llm': allocation['llm']
        },
        'activity': {
            'total_jobs': total_jobs,
            'total_applicants': total_applicants,
            'total_interviews': total_interviews,
            'active_jobs': active_jobs,
            'credits_from_interviews': interview_credits,
            'credits_from_cv_analysis': cv_credits,
            'credits_from_job_posting': job_posting_credits
        },
        'plan': {
            'name': plan.get('name', 'Free Tier') if plan else (plan_name or 'Free Tier'),
            'tier': plan_name.lower() if plan_name else 'free'
        }
    }


def aggregate_recruiter_statistics(recruiters_data):
    """
    Aggregate statistics from multiple recruiters for admin overview.
    
    Args:
        recruiters_data: List of recruiter credit stats from calculate_recruiter_credits
    
    Returns:
        dict with aggregated overview statistics
    """
    if not recruiters_data:
        return {
            'totalBudget': 0,
            'totalUsed': 0,
            'totalAvailable': 0,
            'cloudflare': {'allocated': 0, 'used': 0},
            'nlp': {'allocated': 0, 'used': 0},
            'llm': {'allocated': 0, 'used': 0},
            'totalRecruiters': 0,
            'activeRecruiters': 0
        }
    
    total_budget = sum(r['allocated'] for r in recruiters_data)
    total_used = sum(r['used'] for r in recruiters_data)
    total_cloudflare_allocated = sum(r['allocation']['cloudflare'] for r in recruiters_data)
    total_cloudflare_used = sum(r['breakdown']['cloudflare'] for r in recruiters_data)
    total_nlp_allocated = sum(r['allocation']['nlp'] for r in recruiters_data)
    total_nlp_used = sum(r['breakdown']['nlp'] for r in recruiters_data)
    total_llm_allocated = sum(r['allocation']['llm'] for r in recruiters_data)
    total_llm_used = sum(r['breakdown']['llm'] for r in recruiters_data)
    
    active_recruiters = len([r for r in recruiters_data if r['activity']['total_jobs'] > 0])
    
    return {
        'totalBudget': total_budget,
        'totalUsed': total_used,
        'totalAvailable': total_budget - total_used,
        'cloudflare': {'allocated': total_cloudflare_allocated, 'used': total_cloudflare_used},
        'nlp': {'allocated': total_nlp_allocated, 'used': total_nlp_used},
        'llm': {'allocated': total_llm_allocated, 'used': total_llm_used},
        'totalRecruiters': len(recruiters_data),
        'activeRecruiters': active_recruiters
    }


def generate_usage_history(cloudflare_used, nlp_used, llm_used, weeks=6, db=None, job_ids=None):
    """
    Generate usage history for visualization charts.
    If db and job_ids are provided, uses real per-week interview data from MongoDB.
    Otherwise falls back to a deterministic estimate.
    """
    today = datetime.utcnow()
    history = []

    # Try to get real weekly data from the database
    real_weekly = None
    if db is not None and job_ids:
        try:
            start_date = today - timedelta(weeks=weeks)
            # Query applications that represent interviews (status = interviewed/selected/rejected)
            pipeline = [
                {
                    '$match': {
                        'job_id': {'$in': job_ids},
                        'is_visible': True,
                        'status': {'$in': ['interviewed', 'selected', 'screening_cleared', 'rejected']},
                        'updated_at': {'$gte': start_date}
                    }
                },
                {
                    '$group': {
                        '_id': {
                            '$subtract': [
                                {'$week': '$updated_at'},
                                {'$week': start_date}
                            ]
                        },
                        'count': {'$sum': 1},
                        'min_date': {'$min': '$updated_at'}
                    }
                }
            ]
            results = list(db.applications.aggregate(pipeline))

            # Build a week-number to count map
            # We'll bucket by actual calendar weeks instead
            week_counts = [0] * weeks
            for app in db.applications.find({
                'job_id': {'$in': job_ids},
                'is_visible': True,
                'status': {'$in': ['interviewed', 'selected', 'screening_cleared', 'rejected']},
                'updated_at': {'$gte': start_date}
            }, {'updated_at': 1}):
                app_date = app.get('updated_at')
                if app_date:
                    delta_days = (today - app_date).days
                    week_index = weeks - 1 - (delta_days // 7)
                    if 0 <= week_index < weeks:
                        week_counts[week_index] += 1

            real_weekly = week_counts
        except Exception as e:
            print(f"[Weekly Trend] Error querying real data: {e}")
            real_weekly = None

    for i in range(weeks):
        week_date = today - timedelta(weeks=(weeks - 1 - i))

        if real_weekly is not None:
            interviews = real_weekly[i]
            history.append({
                'date': week_date.strftime('%Y-%m-%d'),
                'week': f'Week {i + 1}',
                'interviews': interviews,
                'cloudflare': int(interviews * ACTIVITY_COSTS.get('interview', 150) * 0.35),
                'nlp': int(interviews * ACTIVITY_COSTS.get('cv_analysis', 25)),
                'llm': int(interviews * ACTIVITY_COSTS.get('interview', 150) * 0.65)
            })
        else:
            # Fallback: deterministic estimate
            factor = (i + 1) / weeks
            variation = 1.0 + (0.1 * ((i % 3) - 1))
            history.append({
                'date': week_date.strftime('%Y-%m-%d'),
                'week': f'Week {i + 1}',
                'interviews': 0,
                'cloudflare': int(cloudflare_used * factor / weeks * variation),
                'nlp': int(nlp_used * factor / weeks * variation),
                'llm': int(llm_used * factor / weeks * variation)
            })

    return history


def generate_job_breakdown(jobs, max_jobs=10):
    """
    Generate per-job cost breakdown based on REAL job data.
    Uses fixed rates for deterministic calculations.
    """
    breakdown = []
    
    for job in jobs[:max_jobs]:
        candidates = job.get('applicants', 0)
        interviewed = job.get('interviewed', 0)
        
        # Fixed rates for deterministic calculation
        job_cloudflare = interviewed * 32  # Fixed rate: 32 credits per interview for video
        job_nlp = candidates * 27          # Fixed rate: 27 credits per CV analysis
        job_llm = interviewed * 40         # Fixed rate: 40 credits per interview evaluation
        
        breakdown.append({
            'id': str(job['_id']),
            'title': job.get('title', 'Untitled Job'),
            'candidates': candidates,
            'interviewed': interviewed,
            'cloudflare': job_cloudflare,
            'nlp': job_nlp,
            'llm': job_llm,
            'total': job_cloudflare + job_nlp + job_llm
        })
    
    return breakdown

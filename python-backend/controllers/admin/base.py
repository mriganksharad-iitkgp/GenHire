"""Shared state and platform-overview stats for the admin controller mixins."""

import datetime
from repositories import (
    ApplicationRepository,
    InterviewRepository,
    JobRepository,
    RecruiterRepository,
    UserRepository,
)
from services.email_service import EmailService


class AdminBase:
    def __init__(self, db_collections):
        self.users_collection = db_collections["users"]
        self.jobs_collection = db_collections["jobs"]
        self.applications_collection = db_collections["applications"]
        self.interviews_collection = db_collections.get("interviews")  # May not exist
        self.practice_sessions_collection = db_collections.get(
            "practice_sessions"
        )  # For practice history
        # Store reference to db for accessing other collections like subscriptions
        self.db_collections = db_collections
        self.email_service = EmailService()

        # Repositories — preferred access path for new/simple queries; the
        # remaining raw collection calls (aggregations, counts) migrate
        # opportunistically as their methods get touched.
        self.user_repo = UserRepository(self.users_collection)
        self.recruiter_repo = RecruiterRepository(self.users_collection)
        self.job_repo = JobRepository(self.jobs_collection)
        self.application_repo = ApplicationRepository(self.applications_collection)
        self.interview_repo = (
            InterviewRepository(self.interviews_collection)
            if self.interviews_collection is not None
            else None
        )

    def get_dashboard_stats(self, current_user):
        """Get platform statistics for admin dashboard"""
        try:
            # Count users by type
            total_candidates = self.users_collection.count_documents(
                {"user_type": "candidate"}
            )
            total_recruiters = self.users_collection.count_documents(
                {"user_type": "recruiter"}
            )
            total_admins = self.users_collection.count_documents({"user_type": "admin"})

            # Pending recruiter verifications
            pending_verifications = self.users_collection.count_documents(
                {"user_type": "recruiter", "is_verified": False}
            )

            # Verified recruiters
            verified_recruiters = self.users_collection.count_documents(
                {"user_type": "recruiter", "is_verified": True}
            )

            # Job statistics
            total_jobs = self.jobs_collection.count_documents({})
            active_jobs = self.jobs_collection.count_documents(
                {"status": {"$in": ["active", "open", None]}}
            )

            # Application statistics
            total_applications = self.applications_collection.count_documents({})

            # Recent activity - users registered in last 7 days
            seven_days_ago = datetime.datetime.utcnow() - datetime.timedelta(days=7)
            new_users_week = self.users_collection.count_documents(
                {"created_at": {"$gte": seven_days_ago}}
            )

            return {
                "users": {
                    "total": total_candidates + total_recruiters + total_admins,
                    "candidates": total_candidates,
                    "recruiters": total_recruiters,
                    "admins": total_admins,
                    "new_this_week": new_users_week,
                },
                "recruiters": {
                    "total": total_recruiters,
                    "verified": verified_recruiters,
                    "pending_verification": pending_verifications,
                },
                "jobs": {"total": total_jobs, "active": active_jobs},
                "applications": {"total": total_applications},
            }, 200
        except Exception as e:
            print(f"Error getting dashboard stats: {str(e)}")
            return {"error": "Failed to get dashboard statistics"}, 500

    def get_system_stats(self, current_user):
        """Get comprehensive system statistics"""
        try:
            # Time periods
            now = datetime.datetime.utcnow()
            today = now.replace(hour=0, minute=0, second=0, microsecond=0)
            week_ago = now - datetime.timedelta(days=7)
            month_ago = now - datetime.timedelta(days=30)

            # User stats
            total_users = self.users_collection.count_documents({})
            total_candidates = self.users_collection.count_documents(
                {"user_type": "candidate"}
            )
            total_recruiters = self.users_collection.count_documents(
                {"user_type": "recruiter"}
            )
            total_admins = self.users_collection.count_documents({"user_type": "admin"})
            verified_recruiters = self.users_collection.count_documents(
                {"user_type": "recruiter", "is_verified": True}
            )
            pending_recruiters = self.users_collection.count_documents(
                {"user_type": "recruiter", "is_verified": False}
            )

            # New registrations
            new_users_today = self.users_collection.count_documents(
                {"created_at": {"$gte": today}}
            )
            new_users_week = self.users_collection.count_documents(
                {"created_at": {"$gte": week_ago}}
            )
            new_users_month = self.users_collection.count_documents(
                {"created_at": {"$gte": month_ago}}
            )

            # Job stats
            total_jobs = self.jobs_collection.count_documents({})
            active_jobs = self.jobs_collection.count_documents(
                {"status": {"$in": ["active", "open"]}}
            )
            closed_jobs = self.jobs_collection.count_documents({"status": "closed"})
            new_jobs_week = self.jobs_collection.count_documents(
                {"created_at": {"$gte": week_ago}}
            )

            # Application stats
            total_applications = self.applications_collection.count_documents({})
            pending_applications = self.applications_collection.count_documents(
                {"status": "pending"}
            )
            shortlisted_applications = self.applications_collection.count_documents(
                {"status": "shortlisted"}
            )
            interviewed_applications = self.applications_collection.count_documents(
                {"status": "interviewed"}
            )
            selected_applications = self.applications_collection.count_documents(
                {"status": {"$in": ["screening_cleared", "selected"]}}
            )
            rejected_applications = self.applications_collection.count_documents(
                {"status": "rejected"}
            )
            new_applications_week = self.applications_collection.count_documents(
                {"applied_at": {"$gte": week_ago}}
            )

            # Interview stats (if collection exists)
            interview_stats = {}
            if self.interviews_collection:
                total_interviews = self.interviews_collection.count_documents({})
                completed_interviews = self.interviews_collection.count_documents(
                    {"status": "completed"}
                )
                interview_stats = {
                    "total": total_interviews,
                    "completed": completed_interviews,
                }

            return {
                "users": {
                    "total": total_users,
                    "candidates": total_candidates,
                    "recruiters": total_recruiters,
                    "admins": total_admins,
                    "verified_recruiters": verified_recruiters,
                    "pending_recruiters": pending_recruiters,
                    "new_today": new_users_today,
                    "new_this_week": new_users_week,
                    "new_this_month": new_users_month,
                },
                "jobs": {
                    "total": total_jobs,
                    "active": active_jobs,
                    "closed": closed_jobs,
                    "new_this_week": new_jobs_week,
                },
                "applications": {
                    "total": total_applications,
                    "pending": pending_applications,
                    "shortlisted": shortlisted_applications,
                    "interviewed": interviewed_applications,
                    "screening_cleared": selected_applications,
                    "rejected": rejected_applications,
                    "new_this_week": new_applications_week,
                    "success_rate": (
                        round((selected_applications / total_applications * 100), 2)
                        if total_applications > 0
                        else 0
                    ),
                },
                "interviews": interview_stats,
                "generated_at": now.isoformat(),
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting system stats: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get system statistics"}, 500

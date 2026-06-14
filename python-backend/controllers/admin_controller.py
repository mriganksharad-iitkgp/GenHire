import datetime
import json
import math
import re
from bson import ObjectId
from collections import defaultdict
from models.user import AVAILABLE_PERMISSIONS
from payment_module.services.wallet_service import WalletService


class AdminController:
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

    def get_users(self, current_user, filters=None):
        """Get list of users with optional filters and pagination"""
        try:
            filters = filters or {}

            # Build query
            query = {}

            # Filter by user type
            if filters.get("user_type"):
                query["user_type"] = filters["user_type"]

            # Filter by verification status
            if filters.get("is_verified") is not None:
                query["is_verified"] = filters["is_verified"]

            # Search by name or email
            if filters.get("search"):
                search_term = filters["search"]
                query["$or"] = [
                    {"name": {"$regex": search_term, "$options": "i"}},
                    {"email": {"$regex": search_term, "$options": "i"}},
                    {"company_name": {"$regex": search_term, "$options": "i"}},
                ]

            # Pagination
            page = int(filters.get("page", 1))
            limit = int(filters.get("limit", 20))
            skip = (page - 1) * limit

            # Get total count for pagination
            total_count = self.users_collection.count_documents(query)

            # Get users with sorting (newest first)
            users_cursor = (
                self.users_collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )
            users_docs = list(users_cursor)

            active_plan_by_user_id = {}
            subscriptions_collection = self.users_collection.database.get_collection(
                "subscriptions"
            )

            def _load_active_plan_name(user_docs, audience):
                if not user_docs:
                    return

                user_object_ids = [doc["_id"] for doc in user_docs]
                user_string_ids = [str(doc["_id"]) for doc in user_docs]

                audience_filter = (
                    {
                        "$or": [
                            {"plan_snapshot.audience": "recruiter"},
                            {"plan_snapshot.audience": {"$exists": False}},
                        ]
                    }
                    if audience == "recruiter"
                    else {"plan_snapshot.audience": "candidate"}
                )

                sub_query = {
                    "status": "active",
                    "$and": [
                        audience_filter,
                        {
                            "$or": [
                                {"employer_id": {"$in": user_object_ids}},
                                {"employer_id": {"$in": user_string_ids}},
                            ]
                        },
                    ],
                }

                active_subscriptions = list(
                    subscriptions_collection.find(sub_query).sort("created_at", -1)
                )

                for subscription in active_subscriptions:
                    owner_id = str(subscription.get("employer_id"))
                    if owner_id in active_plan_by_user_id:
                        continue

                    plan_snapshot = subscription.get("plan_snapshot") or {}
                    plan_name = (
                        plan_snapshot.get("name") or plan_snapshot.get("slug") or "Free"
                    )
                    active_plan_by_user_id[owner_id] = plan_name

            candidate_docs = [
                doc for doc in users_docs if doc.get("user_type") == "candidate"
            ]
            recruiter_docs = [
                doc for doc in users_docs if doc.get("user_type") == "recruiter"
            ]

            _load_active_plan_name(candidate_docs, "candidate")
            _load_active_plan_name(recruiter_docs, "recruiter")

            users = []
            for user in users_docs:
                user_id = str(user["_id"])
                users.append(
                    {
                        "id": user_id,
                        "name": user.get("name", ""),
                        "email": user.get("email", ""),
                        "user_type": user.get("user_type", "candidate"),
                        "is_verified": user.get("is_verified", True),
                        "email_verified": user.get("email_verified", False),
                        "permissions": user.get("permissions", []),
                        "company_name": user.get("company_name"),
                        "company_industry": user.get("company_industry"),
                        "created_at": (
                            user.get("created_at").isoformat()
                            if user.get("created_at")
                            else None
                        ),
                        "verified_at": (
                            user.get("verified_at").isoformat()
                            if user.get("verified_at")
                            else None
                        ),
                        "auth_provider": user.get("auth_provider", "local"),
                        "enrolled_plan": active_plan_by_user_id.get(user_id, "Free"),
                    }
                )

            return {
                "users": users,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "total_pages": (total_count + limit - 1) // limit,
                },
            }, 200
        except Exception as e:
            print(f"Error getting users: {str(e)}")
            return {"error": "Failed to get users"}, 500

    def get_pending_recruiters(self, current_user):
        """Get list of recruiters pending verification"""
        try:
            query = {
                "user_type": "recruiter", 
                "is_verified": False,
                "$or": [
                    {"rejection_reason": None},
                    {"rejection_reason": {"$exists": False}}
                ]
            }

            recruiters_cursor = self.users_collection.find(query).sort("created_at", -1)

            recruiters = []
            for recruiter in recruiters_cursor:
                recruiters.append(
                    {
                        "id": str(recruiter["_id"]),
                        "name": recruiter.get("name", ""),
                        "email": recruiter.get("email", ""),
                        "phone": recruiter.get("phone"),
                        "company_name": recruiter.get("company_name", ""),
                        "company_description": recruiter.get("company_description", ""),
                        "company_website": recruiter.get("company_website"),
                        "company_industry": recruiter.get("company_industry", ""),
                        "company_size": recruiter.get("company_size"),
                        "company_location": recruiter.get("location")
                        or recruiter.get("company_location", ""),
                        "reason_for_joining": recruiter.get("reason_for_joining", ""),
                        "linkedin_profile": recruiter.get("linkedin_profile", ""),
                        "email_verified": recruiter.get("email_verified", False),
                        "created_at": (
                            recruiter.get("created_at").isoformat()
                            if recruiter.get("created_at")
                            else None
                        ),
                        "auth_provider": recruiter.get("auth_provider", "local"),
                    }
                )

            return {"pending_recruiters": recruiters, "count": len(recruiters)}, 200
        except Exception as e:
            print(f"Error getting pending recruiters: {str(e)}")
            return {"error": "Failed to get pending recruiters"}, 500

    def get_user_details(self, current_user, user_id):
        """Get detailed information about a specific user"""
        try:
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return {"error": "User not found"}, 404

            # Get additional stats for the user
            user_stats = {}

            if user.get("user_type") == "candidate":
                # Count applications
                user_stats["applications_count"] = (
                    self.applications_collection.count_documents(
                        {"candidate_id": str(user["_id"])}
                    )
                )
            elif user.get("user_type") == "recruiter":
                # Count jobs posted
                user_stats["jobs_posted"] = self.jobs_collection.count_documents(
                    {"recruiter_id": str(user["_id"])}
                )
                user_stats["total_applications"] = (
                    self.applications_collection.count_documents(
                        {
                            "job_id": {
                                "$in": [
                                    str(job["_id"])
                                    for job in self.jobs_collection.find(
                                        {"recruiter_id": str(user["_id"])}, {"_id": 1}
                                    )
                                ]
                            }
                        }
                    )
                )

            return {
                "user": {
                    "id": str(user["_id"]),
                    "name": user.get("name", ""),
                    "email": user.get("email", ""),
                    "user_type": user.get("user_type", "candidate"),
                    "phone": user.get("phone"),
                    "location": user.get("location"),
                    "title": user.get("title"),
                    "about": user.get("about"),
                    "is_verified": user.get("is_verified", True),
                    "email_verified": user.get("email_verified", False),
                    "permissions": user.get("permissions", []),
                    "company_name": user.get("company_name"),
                    "company_description": user.get("company_description"),
                    "company_website": user.get("company_website"),
                    "company_industry": user.get("company_industry"),
                    "company_size": user.get("company_size"),
                    "created_at": (
                        user.get("created_at").isoformat()
                        if user.get("created_at")
                        else None
                    ),
                    "updated_at": (
                        user.get("updated_at").isoformat()
                        if user.get("updated_at")
                        else None
                    ),
                    "verified_at": (
                        user.get("verified_at").isoformat()
                        if user.get("verified_at")
                        else None
                    ),
                    "verified_by": user.get("verified_by"),
                    "auth_provider": user.get("auth_provider", "local"),
                },
                "stats": user_stats,
            }, 200
        except Exception as e:
            print(f"Error getting user details: {str(e)}")
            return {"error": "Failed to get user details"}, 500

    def verify_recruiter(self, current_user, recruiter_id):
        """Verify a recruiter account"""
        try:
            recruiter = self.users_collection.find_one({"_id": ObjectId(recruiter_id)})

            if not recruiter:
                return {"error": "Recruiter not found"}, 404

            if recruiter.get("user_type") != "recruiter":
                return {"error": "User is not a recruiter"}, 400

            if recruiter.get("is_verified", False):
                return {"error": "Recruiter is already verified"}, 400

            # Update verification status
            self.users_collection.update_one(
                {"_id": ObjectId(recruiter_id)},
                {
                    "$set": {
                        "is_verified": True,
                        "verified_by": str(current_user["_id"]),
                        "verified_at": datetime.datetime.utcnow(),
                        "updated_at": datetime.datetime.utcnow(),
                        "rejection_reason": None,  # Clear any previous rejection reason
                    }
                },
            )

            return {
                "message": f'Recruiter {recruiter.get("name")} has been verified successfully',
                "recruiter_id": recruiter_id,
            }, 200
        except Exception as e:
            print(f"Error verifying recruiter: {str(e)}")
            return {"error": "Failed to verify recruiter"}, 500

    def reject_recruiter(self, current_user, recruiter_id, reason=None):
        """Reject/suspend a recruiter account"""
        try:
            recruiter = self.users_collection.find_one({"_id": ObjectId(recruiter_id)})

            if not recruiter:
                return {"error": "Recruiter not found"}, 404

            if recruiter.get("user_type") != "recruiter":
                return {"error": "User is not a recruiter"}, 400

            # Update to unverified status with rejection reason
            self.users_collection.update_one(
                {"_id": ObjectId(recruiter_id)},
                {
                    "$set": {
                        "is_verified": False,
                        "rejection_reason": reason
                        or "Account verification rejected by admin",
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )

            return {
                "message": f'Recruiter {recruiter.get("name")} has been rejected',
                "recruiter_id": recruiter_id,
            }, 200
        except Exception as e:
            print(f"Error rejecting recruiter: {str(e)}")
            return {"error": "Failed to reject recruiter"}, 500

    def update_user_permissions(self, current_user, user_id, permissions):
        """Update user permissions (and promote to admin if granting admin-level permissions)"""
        try:
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return {"error": "User not found"}, 404

            # Validate permissions
            invalid_permissions = [
                p for p in permissions if p not in AVAILABLE_PERMISSIONS
            ]
            if invalid_permissions:
                return {
                    "error": f'Invalid permissions: {", ".join(invalid_permissions)}',
                    "available_permissions": AVAILABLE_PERMISSIONS,
                }, 400

            # Check if granting admin-level permissions (*, or any permission)
            has_admin_permissions = len(permissions) > 0
            is_super_admin = "*" in permissions

            # Only allow granting admin permissions to candidates, not recruiters
            if has_admin_permissions and user.get("user_type") == "recruiter":
                return {
                    "error": "Cannot grant admin permissions to recruiter accounts. Only candidates can be promoted to admin.",
                    "user_type": user.get("user_type"),
                }, 400

            # Build update data
            update_data = {
                "permissions": permissions,
                "updated_at": datetime.datetime.utcnow(),
            }

            # If granting any permissions, promote user to admin
            if has_admin_permissions and user.get("user_type") == "candidate":
                update_data["user_type"] = "admin"
                update_data["is_verified"] = True
                new_role = "admin"
            elif not has_admin_permissions and user.get("user_type") == "admin":
                # If removing all permissions from admin, demote back to candidate
                update_data["user_type"] = "candidate"
                new_role = "candidate"
            else:
                new_role = user.get("user_type")

            # Update user
            self.users_collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": update_data}
            )

            return {
                "message": f'Permissions updated for {user.get("name")}',
                "user_id": user_id,
                "permissions": permissions,
                "user_type": new_role,
                "promoted": new_role != user.get("user_type"),
            }, 200
        except Exception as e:
            print(f"Error updating permissions: {str(e)}")
            return {"error": "Failed to update permissions"}, 500

    def update_user_type(self, current_user, user_id, new_user_type):
        """Update user type (promote/demote users)"""
        try:
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return {"error": "User not found"}, 404

            # Validate user type
            if new_user_type not in ["candidate", "recruiter", "admin"]:
                return {"error": "Invalid user type"}, 400

            # Prevent demoting self
            if (
                str(user["_id"]) == str(current_user["_id"])
                and new_user_type != "admin"
            ):
                return {"error": "Cannot demote yourself"}, 400

            # Prevent promoting recruiters to admin - only candidates can become admins
            if new_user_type == "admin" and user.get("user_type") == "recruiter":
                return {
                    "error": "Recruiters cannot be promoted to admin. Only candidates can become admins.",
                    "current_type": user.get("user_type"),
                }, 400

            update_data = {
                "user_type": new_user_type,
                "updated_at": datetime.datetime.utcnow(),
            }

            # Auto-verify if promoting to admin
            if new_user_type == "admin":
                update_data["is_verified"] = True
                update_data["permissions"] = ["*"]  # Give all permissions to new admin

            # If demoting admin to candidate, clear permissions
            if new_user_type == "candidate" and user.get("user_type") == "admin":
                update_data["permissions"] = []

            self.users_collection.update_one(
                {"_id": ObjectId(user_id)}, {"$set": update_data}
            )

            return {
                "message": f'User {user.get("name")} is now a {new_user_type}',
                "user_id": user_id,
                "new_user_type": new_user_type,
            }, 200
        except Exception as e:
            print(f"Error updating user type: {str(e)}")
            return {"error": "Failed to update user type"}, 500

    def get_available_permissions(self, current_user):
        """Get list of available permissions"""
        return {"permissions": AVAILABLE_PERMISSIONS}, 200

    def delete_user(self, current_user, user_id):
        """Delete a user account (soft delete or hard delete)"""
        try:
            user = self.users_collection.find_one({"_id": ObjectId(user_id)})

            if not user:
                return {"error": "User not found"}, 404

            # Prevent deleting self
            if str(user["_id"]) == str(current_user["_id"]):
                return {"error": "Cannot delete your own account"}, 400

            # Prevent deleting other admins (only super admin with '*' permission can)
            if user.get("user_type") == "admin":
                if "*" not in current_user.get("permissions", []):
                    return {
                        "error": "Only super admins can delete other admin accounts"
                    }, 403

            # Hard delete the user
            self.users_collection.delete_one({"_id": ObjectId(user_id)})

            # Also delete related data based on user type
            if user.get("user_type") == "candidate":
                # Delete candidate's applications
                self.applications_collection.delete_many(
                    {"student_id": str(user["_id"])}
                )
            elif user.get("user_type") == "recruiter":
                # Delete recruiter's jobs and their applications
                recruiter_jobs = list(
                    self.jobs_collection.find(
                        {"created_by": str(user["_id"])}, {"_id": 1}
                    )
                )
                job_ids = [str(job["_id"]) for job in recruiter_jobs]
                if job_ids:
                    self.applications_collection.delete_many(
                        {"job_id": {"$in": job_ids}}
                    )
                self.jobs_collection.delete_many({"created_by": str(user["_id"])})

            return {
                "message": f'User {user.get("name")} has been deleted',
                "user_id": user_id,
            }, 200
        except Exception as e:
            print(f"Error deleting user: {str(e)}")
            return {"error": "Failed to delete user"}, 500

    def get_candidate_details(self, current_user, candidate_id):
        """Get comprehensive details about a candidate including applications and interview history"""
        try:
            candidate = self.users_collection.find_one({"_id": ObjectId(candidate_id)})

            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            # Helper to safely format datetime
            def safe_isoformat(dt):
                if dt is None:
                    return None
                if isinstance(dt, datetime.datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt  # Already a string
                return str(dt)

            # Get all applications by this candidate
            applications_cursor = self.applications_collection.find(
                {"student_id": str(candidate["_id"])}
            ).sort("applied_at", -1)

            applications = []
            for app in applications_cursor:
                # Get job details for each application
                job = None
                recruiter = None
                try:
                    if app.get("job_id"):
                        job = self.jobs_collection.find_one(
                            {"_id": ObjectId(app["job_id"])}
                        )
                    if app.get("recruiter_id"):
                        recruiter = self.users_collection.find_one(
                            {"_id": ObjectId(app["recruiter_id"])}
                        )
                except:
                    pass

                applications.append(
                    {
                        "id": str(app["_id"]),
                        "job_id": app.get("job_id"),
                        "job_title": app.get("job_title")
                        or (job.get("title") if job else "Unknown"),
                        "company": (
                            job.get("company")
                            if job
                            else (
                                recruiter.get("company_name")
                                if recruiter
                                else "Unknown"
                            )
                        ),
                        "status": app.get("status", "pending"),
                        "cv_score": app.get("cv_score"),
                        "interview_score": app.get("interview_score"),
                        "proctoring_score": app.get("proctoring_score"),
                        "applied_at": safe_isoformat(app.get("applied_at")),
                        "cover_letter": app.get("cover_letter"),
                        "cv_score_breakdown": app.get("cv_score_breakdown"),
                        "processing_status": app.get("processing_status"),
                    }
                )

            # Get statistics
            stats = {
                "total_applications": len(applications),
                "pending": sum(1 for app in applications if app["status"] == "pending"),
                "shortlisted": sum(
                    1 for app in applications if app["status"] == "shortlisted"
                ),
                "interviewed": sum(
                    1 for app in applications if app["status"] == "interviewed"
                ),
                "selected": sum(
                    1 for app in applications if app["status"] == "selected"
                ),
                "rejected": sum(
                    1 for app in applications if app["status"] == "rejected"
                ),
                "avg_cv_score": (
                    round(
                        sum(app["cv_score"] or 0 for app in applications)
                        / len(applications),
                        2,
                    )
                    if applications
                    else 0
                ),
                "avg_interview_score": round(
                    sum(
                        app["interview_score"] or 0
                        for app in applications
                        if app["interview_score"]
                    )
                    / max(sum(1 for app in applications if app["interview_score"]), 1),
                    2,
                ),
            }

            return {
                "candidate": {
                    "id": str(candidate["_id"]),
                    "name": candidate.get("name", ""),
                    "email": candidate.get("email", ""),
                    "phone": candidate.get("phone"),
                    "location": candidate.get("location"),
                    "title": candidate.get("title"),
                    "about": candidate.get("about"),
                    "skills": candidate.get("skills", []),
                    "cv_path": candidate.get("cv_path"),
                    "cv_details": candidate.get("cv_details"),
                    "cv_uploads": candidate.get("cv_uploads", []),
                    "profile_photo": candidate.get("profile_photo"),
                    "linkedin": candidate.get("linkedin"),
                    "github": candidate.get("github"),
                    "portfolio": candidate.get("portfolio"),
                    "experience": candidate.get("experience"),
                    "education": candidate.get("education"),
                    "resume_summary": candidate.get("resume_summary"),
                    "certifications": candidate.get("certifications"),
                    "languages": candidate.get("languages"),
                    "availability": candidate.get("availability"),
                    "created_at": safe_isoformat(candidate.get("created_at")),
                    "updated_at": safe_isoformat(candidate.get("updated_at")),
                    "email_verified": candidate.get("email_verified", False),
                    "auth_provider": candidate.get("auth_provider", "local"),
                },
                "applications": applications,
                "stats": stats,
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting candidate details for ID {candidate_id}: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get candidate details"}, 500

    def get_recruiter_details(self, current_user, recruiter_id):
        """Get comprehensive details about a recruiter including jobs and statistics"""
        try:
            recruiter = self.users_collection.find_one({"_id": ObjectId(recruiter_id)})

            if not recruiter:
                return {"error": "Recruiter not found"}, 404

            if recruiter.get("user_type") != "recruiter":
                return {"error": "User is not a recruiter"}, 400

            # Helper to safely format datetime
            def safe_isoformat(dt):
                if dt is None:
                    return None
                if isinstance(dt, datetime.datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt  # Already a string
                return str(dt)

            # Get all jobs posted by this recruiter
            jobs_cursor = self.jobs_collection.find(
                {"created_by": str(recruiter["_id"])}
            ).sort("created_at", -1)

            jobs = []
            total_applications = 0
            total_selected = 0
            total_rejected = 0

            for job in jobs_cursor:
                # Get application stats for each job
                job_applications = list(
                    self.applications_collection.find({"job_id": str(job["_id"])})
                )

                app_count = len(job_applications)
                total_applications += app_count

                selected_count = sum(
                    1 for app in job_applications if app.get("status") == "selected"
                )
                rejected_count = sum(
                    1 for app in job_applications if app.get("status") == "rejected"
                )
                interviewed_count = sum(
                    1 for app in job_applications if app.get("status") == "interviewed"
                )

                total_selected += selected_count
                total_rejected += rejected_count

                jobs.append(
                    {
                        "id": str(job["_id"]),
                        "title": job.get("title"),
                        "department": job.get("department"),
                        "location": job.get("location"),
                        "type": job.get("type"),
                        "status": job.get("status", "active"),
                        "created_at": safe_isoformat(job.get("created_at")),
                        "deadline": safe_isoformat(job.get("deadline")),
                        "applicants": app_count,
                        "interviewed": interviewed_count,
                        "selected": selected_count,
                        "rejected": rejected_count,
                        "salary": job.get("salary"),
                        "experience": job.get("experience"),
                    }
                )

            # Get statistics
            stats = {
                "total_jobs": len(jobs),
                "active_jobs": sum(
                    1 for job in jobs if job["status"] in ["active", "open"]
                ),
                "total_applications": total_applications,
                "total_selected": total_selected,
                "total_rejected": total_rejected,
                "conversion_rate": (
                    round((total_selected / total_applications * 100), 2)
                    if total_applications > 0
                    else 0
                ),
            }

            return {
                "recruiter": {
                    "id": str(recruiter["_id"]),
                    "name": recruiter.get("name", ""),
                    "email": recruiter.get("email", ""),
                    "phone": recruiter.get("phone"),
                    "location": recruiter.get("location"),
                    "company_name": recruiter.get("company_name"),
                    "company_logo": recruiter.get("company_logo"),
                    "company_description": recruiter.get("company_description"),
                    "company_website": recruiter.get("company_website"),
                    "company_size": recruiter.get("company_size"),
                    "company_industry": recruiter.get("company_industry"),
                    "is_verified": recruiter.get("is_verified", False),
                    "verified_at": safe_isoformat(recruiter.get("verified_at")),
                    "verified_by": recruiter.get("verified_by"),
                    "created_at": safe_isoformat(recruiter.get("created_at")),
                    "updated_at": safe_isoformat(recruiter.get("updated_at")),
                    "linkedin_profile": recruiter.get("linkedin_profile"),
                    "reason_for_joining": recruiter.get("reason_for_joining"),
                    "auth_provider": recruiter.get("auth_provider", "local"),
                },
                "jobs": jobs,
                "stats": stats,
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting recruiter details for ID {recruiter_id}: {str(e)}")
            print(traceback.format_exc())
            return {"error": f"Failed to get recruiter details: {str(e)}"}, 500

    def update_candidate(self, current_user, candidate_id, data):
        """Update candidate details"""
        try:
            candidate = self.users_collection.find_one({"_id": ObjectId(candidate_id)})

            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            # Build update data
            update_data = {"updated_at": datetime.datetime.utcnow()}

            # Expanded allowed fields for comprehensive profile editing
            allowed_fields = [
                "name",
                "phone",
                "location",
                "title",
                "about",
                "skills",
                "linkedin",
                "github",
                "portfolio",
                "experience",
                "education",
                "resume_summary",
                "certifications",
                "languages",
                "availability",
            ]
            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]

            self.users_collection.update_one(
                {"_id": ObjectId(candidate_id)}, {"$set": update_data}
            )

            return {
                "message": f'Candidate {candidate.get("name")} updated successfully',
                "candidate_id": candidate_id,
            }, 200
        except Exception as e:
            print(f"Error updating candidate: {str(e)}")
            return {"error": "Failed to update candidate"}, 500

    def update_recruiter(self, current_user, recruiter_id, data):
        """Update recruiter details"""
        try:
            recruiter = self.users_collection.find_one({"_id": ObjectId(recruiter_id)})

            if not recruiter:
                return {"error": "Recruiter not found"}, 404

            if recruiter.get("user_type") != "recruiter":
                return {"error": "User is not a recruiter"}, 400

            # Build update data
            update_data = {"updated_at": datetime.datetime.utcnow()}

            allowed_fields = [
                "name",
                "phone",
                "location",
                "company_name",
                "company_description",
                "company_website",
                "company_size",
                "company_industry",
                "linkedin_profile",
            ]
            for field in allowed_fields:
                if field in data:
                    update_data[field] = data[field]

            self.users_collection.update_one(
                {"_id": ObjectId(recruiter_id)}, {"$set": update_data}
            )

            return {
                "message": f'Recruiter {recruiter.get("name")} updated successfully',
                "recruiter_id": recruiter_id,
            }, 200
        except Exception as e:
            print(f"Error updating recruiter: {str(e)}")
            return {"error": "Failed to update recruiter"}, 500

    def get_job_details(self, current_user, job_id):
        """Get comprehensive job details with all applicants"""
        try:
            job = self.jobs_collection.find_one({"_id": ObjectId(job_id)})

            if not job:
                return {"error": "Job not found"}, 404

            # Helper to safely format datetime
            def safe_isoformat(dt):
                if dt is None:
                    return None
                if isinstance(dt, datetime.datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt
                return str(dt)

            # Get recruiter info
            recruiter = (
                self.users_collection.find_one({"_id": ObjectId(job["created_by"])})
                if job.get("created_by")
                else None
            )

            # Get all applications for this job
            applications_cursor = self.applications_collection.find(
                {"job_id": str(job["_id"])}
            ).sort("applied_at", -1)

            applicants = []
            for app in applications_cursor:
                candidate = (
                    self.users_collection.find_one({"_id": ObjectId(app["student_id"])})
                    if app.get("student_id")
                    else None
                )

                applicants.append(
                    {
                        "id": str(app["_id"]),
                        "application_id": str(
                            app["_id"]
                        ),  # Explicit application ID for delete operations
                        "candidate_id": app.get("student_id"),
                        "name": app.get("student_name")
                        or (candidate.get("name") if candidate else "Unknown"),
                        "email": app.get("student_email")
                        or (candidate.get("email") if candidate else ""),
                        "status": app.get("status", "pending"),
                        "cv_score": app.get("cv_score"),
                        "interview_score": app.get("interview_score"),
                        "proctoring_score": app.get("proctoring_score"),
                        "applied_at": safe_isoformat(app.get("applied_at")),
                    }
                )

            return {
                "job": {
                    "id": str(job["_id"]),
                    "title": job.get("title"),
                    "department": job.get("department"),
                    "location": job.get("location"),
                    "type": job.get("type"),
                    "experience": job.get("experience"),
                    "salary": job.get("salary"),
                    "description": job.get("description"),
                    "skills": job.get("skills", []),
                    "responsibilities": job.get("responsibilities", []),
                    "qualifications": job.get("qualifications", []),
                    "benefits": job.get("benefits", []),
                    "status": job.get("status", "active"),
                    "created_at": safe_isoformat(job.get("created_at")),
                    "updated_at": safe_isoformat(job.get("updated_at")),
                    "deadline": safe_isoformat(job.get("deadline")),
                    "recruiter_name": recruiter.get("name") if recruiter else "Unknown",
                    "recruiter_id": str(recruiter["_id"]) if recruiter else None,
                },
                "applicants": applicants,
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting job details: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get job details"}, 500

    def delete_job(self, current_user, job_id):
        """Delete a job and its applications"""
        try:
            job = self.jobs_collection.find_one({"_id": ObjectId(job_id)})

            if not job:
                return {"error": "Job not found"}, 404

            # Delete all applications for this job
            self.applications_collection.delete_many({"job_id": str(job["_id"])})

            # Delete the job
            self.jobs_collection.delete_one({"_id": ObjectId(job_id)})

            return {
                "message": f'Job "{job.get("title")}" has been deleted',
                "job_id": job_id,
            }, 200
        except Exception as e:
            print(f"Error deleting job: {str(e)}")
            return {"error": "Failed to delete job"}, 500

    def update_application_status(self, current_user, application_id, status):
        """Update application status"""
        try:
            application = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )

            if not application:
                return {"error": "Application not found"}, 404

            valid_statuses = [
                "pending",
                "reviewed",
                "shortlisted",
                "interviewed",
                "selected",
                "rejected",
            ]
            if status not in valid_statuses:
                return {
                    "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                }, 400

            self.applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.datetime.utcnow(),
                        "updated_by": str(current_user["_id"]),
                    }
                },
            )

            return {
                "message": "Application status updated",
                "application_id": application_id,
                "new_status": status,
            }, 200
        except Exception as e:
            print(f"Error updating application status: {str(e)}")
            return {"error": "Failed to update application status"}, 500

    def get_all_jobs(self, current_user, filters=None):
        """Get all jobs with filters"""
        try:
            filters = filters or {}
            query = {}

            # Helper to safely format datetime
            def safe_isoformat(dt):
                if dt is None:
                    return None
                if isinstance(dt, datetime.datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt
                return str(dt)

            # Filter by status
            if filters.get("status"):
                query["status"] = filters["status"]

            # Filter by recruiter
            if filters.get("recruiter_id"):
                query["created_by"] = filters["recruiter_id"]

            # Search
            if filters.get("search"):
                search_term = filters["search"]
                query["$or"] = [
                    {"title": {"$regex": search_term, "$options": "i"}},
                    {"company": {"$regex": search_term, "$options": "i"}},
                    {"department": {"$regex": search_term, "$options": "i"}},
                ]

            # Pagination
            page = int(filters.get("page", 1))
            limit = int(filters.get("limit", 20))
            skip = (page - 1) * limit

            total_count = self.jobs_collection.count_documents(query)

            jobs_cursor = (
                self.jobs_collection.find(query)
                .sort("created_at", -1)
                .skip(skip)
                .limit(limit)
            )

            jobs = []
            for job in jobs_cursor:
                # Get recruiter info
                recruiter = (
                    self.users_collection.find_one({"_id": ObjectId(job["created_by"])})
                    if job.get("created_by")
                    else None
                )

                # Get application count
                app_count = self.applications_collection.count_documents(
                    {"job_id": str(job["_id"])}
                )

                jobs.append(
                    {
                        "id": str(job["_id"]),
                        "title": job.get("title"),
                        "company": job.get("company")
                        or (recruiter.get("company_name") if recruiter else ""),
                        "department": job.get("department"),
                        "location": job.get("location"),
                        "type": job.get("type"),
                        "status": job.get("status"),
                        "applicants": app_count,
                        "created_at": safe_isoformat(job.get("created_at")),
                        "recruiter_name": (
                            recruiter.get("name") if recruiter else "Unknown"
                        ),
                    }
                )

            return {
                "jobs": jobs,
                "pagination": {
                    "page": page,
                    "limit": limit,
                    "total": total_count,
                    "total_pages": (total_count + limit - 1) // limit,
                },
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting all jobs: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get jobs"}, 500

    def get_application_details(self, current_user, application_id):
        """Get comprehensive application details"""
        try:
            application = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )

            if not application:
                return {"error": "Application not found"}, 404

            # Helper to safely format datetime
            def safe_isoformat(dt):
                if dt is None:
                    return None
                if isinstance(dt, datetime.datetime):
                    return dt.isoformat()
                if isinstance(dt, str):
                    return dt
                return str(dt)

            # Get related data
            candidate = (
                self.users_collection.find_one(
                    {"_id": ObjectId(application["student_id"])}
                )
                if application.get("student_id")
                else None
            )
            job = (
                self.jobs_collection.find_one({"_id": ObjectId(application["job_id"])})
                if application.get("job_id")
                else None
            )
            recruiter = (
                self.users_collection.find_one(
                    {"_id": ObjectId(application["recruiter_id"])}
                )
                if application.get("recruiter_id")
                else None
            )

            return {
                "application": {
                    "id": str(application["_id"]),
                    "status": application.get("status", "pending"),
                    "cv_score": application.get("cv_score"),
                    "cv_score_breakdown": application.get("cv_score_breakdown"),
                    "interview_score": application.get("interview_score"),
                    "interview_feedback": application.get("interview_feedback"),
                    "proctoring_score": application.get("proctoring_score"),
                    "proctoring_report": application.get("proctoring_report"),
                    "cover_letter": application.get("cover_letter"),
                    "cv_path": application.get("cv_path"),
                    "processing_status": application.get("processing_status"),
                    "admin_notes": application.get("admin_notes"),
                    "applied_at": safe_isoformat(application.get("applied_at")),
                    "updated_at": safe_isoformat(application.get("updated_at")),
                    "interview_date": safe_isoformat(application.get("interview_date")),
                    "interview_completed": application.get(
                        "interview_completed", False
                    ),
                },
                "candidate": (
                    {
                        "id": str(candidate["_id"]) if candidate else None,
                        "name": candidate.get("name") if candidate else "Unknown",
                        "email": candidate.get("email") if candidate else None,
                        "phone": candidate.get("phone") if candidate else None,
                        "profile_photo": (
                            candidate.get("profile_photo") if candidate else None
                        ),
                    }
                    if candidate
                    else None
                ),
                "job": (
                    {
                        "id": str(job["_id"]) if job else None,
                        "title": job.get("title") if job else "Unknown",
                        "department": job.get("department") if job else None,
                        "company": job.get("company") if job else None,
                    }
                    if job
                    else None
                ),
                "recruiter": (
                    {
                        "id": str(recruiter["_id"]) if recruiter else None,
                        "name": recruiter.get("name") if recruiter else "Unknown",
                        "company_name": (
                            recruiter.get("company_name") if recruiter else None
                        ),
                    }
                    if recruiter
                    else None
                ),
            }, 200
        except Exception as e:
            import traceback

            print(f"Error getting application details: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get application details"}, 500

    def update_application(self, current_user, application_id, data):
        """Update application details"""
        try:
            application = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )

            if not application:
                return {"error": "Application not found"}, 404

            # Build update data
            update_data = {
                "updated_at": datetime.datetime.utcnow(),
                "updated_by": str(current_user["_id"]),
            }

            allowed_fields = [
                "status",
                "admin_notes",
                "cv_score",
                "interview_score",
                "proctoring_score",
            ]
            valid_statuses = [
                "pending",
                "reviewed",
                "shortlisted",
                "interviewed",
                "selected",
                "rejected",
            ]

            for field in allowed_fields:
                if field in data:
                    if field == "status" and data[field] not in valid_statuses:
                        return {
                            "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                        }, 400
                    update_data[field] = data[field]

            self.applications_collection.update_one(
                {"_id": ObjectId(application_id)}, {"$set": update_data}
            )

            return {
                "message": "Application updated successfully",
                "application_id": application_id,
            }, 200
        except Exception as e:
            print(f"Error updating application: {str(e)}")
            return {"error": "Failed to update application"}, 500

    def delete_application(self, current_user, application_id):
        """Delete an application"""
        try:
            application = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )

            if not application:
                return {"error": "Application not found"}, 404

            # Delete the application
            self.applications_collection.delete_one({"_id": ObjectId(application_id)})

            # Update job applicant count if job exists
            if application.get("job_id"):
                self.jobs_collection.update_one(
                    {"_id": ObjectId(application["job_id"])},
                    {"$inc": {"applicants": -1}},
                )

            return {
                "message": "Application deleted successfully",
                "application_id": application_id,
            }, 200
        except Exception as e:
            print(f"Error deleting application: {str(e)}")
            return {"error": "Failed to delete application"}, 500

    def update_job(self, current_user, job_id, data):
        """Update job details"""
        try:
            job = self.jobs_collection.find_one({"_id": ObjectId(job_id)})

            if not job:
                return {"error": "Job not found"}, 404

            # Build update data
            update_data = {"updated_at": datetime.datetime.utcnow()}

            allowed_fields = [
                "title",
                "department",
                "location",
                "type",
                "experience",
                "salary",
                "description",
                "skills",
                "responsibilities",
                "requirements",
                "benefits",
                "status",
                "minimum_cv_score",
            ]
            valid_statuses = ["draft", "active", "paused", "closed"]

            for field in allowed_fields:
                if field in data:
                    if field == "status" and data[field] not in valid_statuses:
                        return {
                            "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                        }, 400
                    update_data[field] = data[field]

            self.jobs_collection.update_one(
                {"_id": ObjectId(job_id)}, {"$set": update_data}
            )

            return {
                "message": f'Job "{job.get("title")}" updated successfully',
                "job_id": job_id,
            }, 200
        except Exception as e:
            print(f"Error updating job: {str(e)}")
            return {"error": "Failed to update job"}, 500

    def get_candidate_cv(self, current_user, candidate_id):
        """Get candidate CV details"""
        try:
            candidate = self.users_collection.find_one({"_id": ObjectId(candidate_id)})

            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            cv_uploads = candidate.get("cv_uploads", [])

            return {
                "candidate_id": candidate_id,
                "candidate_name": candidate.get("name"),
                "current_cv": candidate.get("cv_path"),
                "cv_details": candidate.get("cv_details"),
                "cv_uploads": cv_uploads,
                "total_uploads": len(cv_uploads),
            }, 200
        except Exception as e:
            print(f"Error getting candidate CV: {str(e)}")
            return {"error": "Failed to get candidate CV"}, 500

    def delete_candidate_cv(self, current_user, candidate_id):
        """Delete candidate CV"""
        try:
            candidate = self.users_collection.find_one({"_id": ObjectId(candidate_id)})

            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            # Clear CV data
            self.users_collection.update_one(
                {"_id": ObjectId(candidate_id)},
                {
                    "$set": {
                        "cv_path": None,
                        "cv_details": None,
                        "cv_uploads": [],
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )

            return {
                "message": f'CV deleted for {candidate.get("name")}',
                "candidate_id": candidate_id,
            }, 200
        except Exception as e:
            print(f"Error deleting candidate CV: {str(e)}")
            return {"error": "Failed to delete candidate CV"}, 500

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
                {"status": "selected"}
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
                    "selected": selected_applications,
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

    def get_candidate_practice_history(self, current_user, candidate_id):
        """Get practice interview history for a specific candidate"""
        try:
            # Verify candidate exists
            candidate = self.users_collection.find_one({"_id": ObjectId(candidate_id)})
            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            # Get practice sessions - same query as candidate portal
            sessions = list(
                self.practice_sessions_collection.find(
                    {"user_id": str(candidate_id), "is_practice": True}
                )
                .sort("created_at", -1)
                .limit(100)
            )

            # Convert ObjectId to string and format dates
            history = []
            for session in sessions:
                session_summary = {
                    "_id": str(session["_id"]),
                    "session_id": session.get("session_id"),
                    "role": session.get("role"),
                    "difficulty": session.get("difficulty"),
                    "status": session.get("status"),
                    "cv_score": session.get(
                        "cv_score", session.get("similarity_score", 0)
                    ),
                    "interview_score": session.get("interview_score", 0),
                    "proctoring_score": session.get("proctoring_score", 100),
                    "created_at": (
                        session.get("created_at").isoformat()
                        if session.get("created_at")
                        else None
                    ),
                    "completed_at": (
                        session.get("completed_at").isoformat()
                        if session.get("completed_at")
                        else None
                    ),
                    "is_practice": True,
                }
                history.append(session_summary)

            return {"sessions": history, "count": len(history)}, 200

        except Exception as e:
            import traceback

            print(f"Error getting candidate practice history: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get practice history"}, 500

    def get_application_report(self, current_user, application_id):
        """Get interview report for an application (admin access)"""
        try:
            print(f"[Admin] Getting application report for: {application_id}")

            try:
                app_doc = self.applications_collection.find_one(
                    {"_id": ObjectId(application_id)}
                )
            except Exception as e:
                print(f"[Admin] Invalid application ID format: {e}")
                return {"error": "Invalid application ID"}, 400

            if not app_doc:
                print(f"[Admin] Application not found: {application_id}")
                return {"error": "Application not found"}, 404

            print(
                f"[Admin] Found application, interview_score: {app_doc.get('interview_score')}"
            )

            # Try multiple approaches to find the interview report
            report = None

            # Approach 1: Query with string application_id (most common)
            try:
                cursor = (
                    self.interviews_collection.find(
                        {"application_id": application_id, "status": "completed"}
                    )
                    .sort("updated_at", -1)
                    .limit(1)
                )
                reports = list(cursor)
                if reports:
                    report = reports[0]
                    print(f"[Admin] Found report with string ID query")
            except Exception as e:
                print(f"[Admin] Error in string ID query: {e}")

            # Approach 2: Try without status filter
            if not report:
                try:
                    cursor = (
                        self.interviews_collection.find(
                            {"application_id": application_id}
                        )
                        .sort("updated_at", -1)
                        .limit(1)
                    )
                    reports = list(cursor)
                    if reports:
                        report = reports[0]
                        print(
                            f"[Admin] Found report without status filter, status: {report.get('status')}"
                        )
                except Exception as e:
                    print(f"[Admin] Error in no-status query: {e}")

            # Approach 3: Try with user_id from application
            if not report and app_doc.get("student_id"):
                try:
                    cursor = (
                        self.interviews_collection.find(
                            {"user_id": app_doc.get("student_id")}
                        )
                        .sort("updated_at", -1)
                        .limit(1)
                    )
                    reports = list(cursor)
                    if reports:
                        report = reports[0]
                        print(f"[Admin] Found report by user_id")
                except Exception as e:
                    print(f"[Admin] Error in user_id query: {e}")

            if not report:
                print(
                    f"[Admin] No interview report found for application: {application_id}"
                )
                # Debug: show sample interviews
                try:
                    sample = list(self.interviews_collection.find().limit(3))
                    for s in sample:
                        print(
                            f"[Admin] Sample interview: app_id={s.get('application_id')}, status={s.get('status')}, user_id={s.get('user_id')}"
                        )
                except Exception as e:
                    print(f"[Admin] Error getting sample: {e}")
                return {"error": "Interview report not found"}, 404

            print(
                f"[Admin] Found report with session_id: {report.get('session_id')}, status: {report.get('status')}"
            )

            # Return complete report with transcript
            payload = {
                "session_id": report.get("session_id"),
                "final_score": report.get("final_score"),
                "proctoring_score": report.get("proctoring_score"),
                "evaluation": report.get("evaluation"),
                "transcript": report.get("transcript", []),
                "usage_summary": report.get("usage_summary", {}),
                "usage_deduction": report.get("usage_deduction", {}),
                "cv_score": app_doc.get("cv_score", 0),
                "interview_score": app_doc.get("interview_score", 0),
            }
            return payload, 200

        except Exception as e:
            import traceback

            print(f"[Admin] Error getting application report: {str(e)}")
            print(traceback.format_exc())
            return {"error": f"Failed to get interview report: {str(e)}"}, 500

    def get_practice_report(self, current_user, session_id):
        """Get practice interview report (admin access)"""
        try:
            # Find the practice session
            session = self.practice_sessions_collection.find_one(
                {"session_id": session_id}
            )

            if not session:
                # Try with ObjectId
                try:
                    session = self.practice_sessions_collection.find_one(
                        {"_id": ObjectId(session_id)}
                    )
                except:
                    pass

            if not session:
                return {"error": "Practice session not found"}, 404

            # Get cv_score from session (convert to percentage)
            cv_score = session.get("cv_score", session.get("similarity_score", 0))
            if isinstance(cv_score, float) and cv_score <= 1:
                cv_score = int(cv_score * 100)  # Convert 0-1 to 0-100

            # Get evaluation - check multiple locations where it might be stored
            evaluation = session.get("evaluation", {})
            if not evaluation:
                # Try result.final_evaluation (old format)
                result = session.get("result", {})
                if isinstance(result, dict):
                    evaluation = result.get(
                        "final_evaluation", result.get("evaluation", {})
                    )
            if not isinstance(evaluation, dict):
                evaluation = {}

            # Get interview score
            interview_score = session.get("interview_score", 0)
            if not interview_score and evaluation:
                quantitative = evaluation.get(
                    "quantitative", evaluation.get("quantitative_scores", {})
                )
                if isinstance(quantitative, dict):
                    scores = [
                        v
                        for k, v in quantitative.items()
                        if isinstance(v, (int, float))
                    ]
                    if scores:
                        interview_score = sum(scores) / len(scores)

            # Get transcript from session
            transcript = session.get("transcript", [])
            if not transcript and "qa_history" in session:
                # Convert qa_history to transcript format
                qa_history = session.get("qa_history", [])
                if isinstance(qa_history, list):
                    transcript = []
                    for qa in qa_history:
                        if isinstance(qa, dict):
                            if qa.get("question"):
                                transcript.append(
                                    {"role": "assistant", "content": qa.get("question")}
                                )
                            if qa.get("answer"):
                                transcript.append(
                                    {"role": "user", "content": qa.get("answer")}
                                )

            report = {
                "session_id": session.get("session_id"),
                "cv_score": cv_score,
                "interview_score": interview_score,
                "proctoring_score": session.get("proctoring_score", 100),
                "evaluation": evaluation,
                "transcript": transcript,
                "usage_summary": session.get("usage_summary", {}),
                "usage_deduction": session.get("usage_deduction", {}),
                "role": session.get("role"),
                "difficulty": session.get("difficulty"),
                "status": session.get("status"),
                "created_at": (
                    session.get("created_at").isoformat()
                    if session.get("created_at")
                    else None
                ),
                "completed_at": (
                    session.get("completed_at").isoformat()
                    if session.get("completed_at")
                    else None
                ),
            }

            print(
                f"[Admin] Practice report for {session_id}: CV={cv_score}%, Interview={interview_score}%, Evaluation keys={list(evaluation.keys()) if evaluation else 'None'}"
            )

            return report, 200

        except Exception as e:
            import traceback

            print(f"Error getting practice report: {str(e)}")
            print(traceback.format_exc())
            return {"error": "Failed to get practice report"}, 500

    def get_cost_statistics(
        self, current_user, period="month", start_date=None, end_date=None
    ):
        """Get timeline-based admin cost and profitability statistics."""
        try:
            from config.database import db_config
            from interview.core.cost_tracker import CostTracker

            def _safe_iso(dt_val):
                return dt_val.isoformat() if dt_val else None

            def _round_money(value):
                return round(float(value or 0.0), 2)

            def _safe_div(num, den):
                return (num / den) if den else 0.0

            def _parse_date(date_value, end_of_day=False):
                if not date_value:
                    return None

                parsed = None
                try:
                    parsed = datetime.datetime.fromisoformat(
                        str(date_value).replace("Z", "+00:00")
                    )
                except Exception:
                    try:
                        parsed = datetime.datetime.strptime(str(date_value), "%Y-%m-%d")
                    except Exception:
                        return None

                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(datetime.timezone.utc).replace(
                        tzinfo=None
                    )

                if len(str(date_value)) <= 10:
                    parsed = parsed.replace(
                        hour=23 if end_of_day else 0,
                        minute=59 if end_of_day else 0,
                        second=59 if end_of_day else 0,
                        microsecond=999999 if end_of_day else 0,
                    )

                return parsed

            def _period_window(period_value):
                now = datetime.datetime.utcnow()
                normalized_period = (period_value or "month").lower()

                if normalized_period == "week":
                    start = now - datetime.timedelta(days=7)
                elif normalized_period == "quarter":
                    start = now - datetime.timedelta(days=90)
                elif normalized_period == "year":
                    start = now - datetime.timedelta(days=365)
                else:
                    normalized_period = "month"
                    start = now - datetime.timedelta(days=30)

                return normalized_period, start, now

            def _build_date_range_query(base_query, date_fields, start_dt, end_dt):
                if not date_fields:
                    return base_query

                date_conditions = [
                    {field_name: {"$gte": start_dt, "$lte": end_dt}}
                    for field_name in date_fields
                ]

                return {"$and": [base_query, {"$or": date_conditions}]}

            def _count_documents_with_window(
                collection, base_query, date_fields, start_dt, end_dt
            ):
                if collection is None:
                    return 0
                query = _build_date_range_query(
                    base_query, date_fields, start_dt, end_dt
                )
                return collection.count_documents(query)

            def _monthly_cost_for_window(monthly_cost, start_dt, end_dt):
                if not monthly_cost:
                    return 0.0
                total_days = max(1, (end_dt - start_dt).days)
                return (monthly_cost / 30.0) * total_days

            def _llm_cost_usd(
                pricing_map, model_key, prompt_tokens, completion_tokens, action_count
            ):
                rates = pricing_map.get(model_key, {})
                input_rate = rates.get("input", 0.0)
                output_rate = rates.get("output", 0.0)
                prompt_cost = (prompt_tokens / 1_000_000.0) * input_rate
                completion_cost = (completion_tokens / 1_000_000.0) * output_rate
                return (prompt_cost + completion_cost) * max(action_count, 0)

            normalized_period, period_start, period_end = _period_window(period)
            requested_start = _parse_date(start_date, end_of_day=False)
            requested_end = _parse_date(end_date, end_of_day=True) if end_date else None

            if start_date and requested_start is None:
                return {"error": "Invalid start_date format. Use YYYY-MM-DD."}, 400

            if end_date and requested_end is None:
                return {"error": "Invalid end_date format. Use YYYY-MM-DD."}, 400

            if requested_end is None:
                requested_end = datetime.datetime.utcnow()

            if requested_start:
                period_start = requested_start
                period_end = requested_end
                normalized_period = "custom"

            if period_start > period_end:
                return {
                    "error": "Invalid timeline. start_date cannot be after end_date."
                }, 400

            db = db_config.get_db()
            if db is None:
                return {"error": "Database connection unavailable."}, 500
            plans_collection = db.plans
            payments_collection = db.payments

            plans_list = list(plans_collection.find({}))
            plans_by_id = {plan_doc.get("_id"): plan_doc for plan_doc in plans_list}

            pricing = CostTracker.PRICING
            inr_per_usd = 83.0

            # User-provided assumptions
            monthly_infra_assumptions = {
                "cloudflare": 5000.0,
                "mongodb": 3000.0,
            }
            cloudflare_gpu_ratio = 245.0 / (245.0 + 100.0)

            action_assumptions = {
                "cv_scoring": {
                    "model": "gemini-1.5-flash-latest",
                    "prompt_tokens": 1800,
                    "completion_tokens": 600,
                },
                "ai_jd_generation": {
                    "model": "llama-3.3-70b-versatile",
                    "prompt_tokens": 1500,
                    "completion_tokens": 1200,
                },
                "ai_interview": {
                    "model": "gpt-4o",
                    "prompt_tokens": 4200,
                    "completion_tokens": 2100,
                    "stt_seconds": 900,
                    "tts_characters": 22000,
                },
                "evaluation": {
                    "model": "gpt-5-mini",
                    "prompt_tokens": 1500,
                    "completion_tokens": 1000,
                },
            }

            def _aggregate_line_item(key, title, model, formula, lines):
                total = sum(float(line.get('cost_inr', 0.0) or 0.0) for line in lines)
                count = len(lines)
                return {
                    'key': key,
                    'title': title,
                    'count': int(count),
                    'model': model,
                    'formula': formula,
                    'total_cost_inr': _round_money(total),
                    'avg_cost_inr': _round_money(_safe_div(total, count)),
                }

            cv_lines = []
            jd_lines = []
            interview_lines = []
            interview_eval_lines = []
            practice_lines = []
            practice_eval_lines = []

            cv_query = _build_date_range_query(
                {'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                cv_lines.append(
                    self._build_token_cost_line(
                        app,
                        'cv_scoring',
                        'Total CV Score Calculation Cost',
                        action_assumptions['cv_scoring'],
                        ['cv_score_calculated_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )
            if jd_events:
                for event in jd_events:
                    jd_lines.append(
                        self._build_token_cost_line(
                            event,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            action_assumptions['ai_jd_generation'],
                            ['occurred_at', 'created_at'],
                            source_meta=event.get('source') or {},
                        )
                    )
            else:
                jobs_query = _build_date_range_query(
                    {},
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    jd_lines.append(
                        self._build_token_cost_line(
                            job,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            action_assumptions['ai_jd_generation'],
                            ['updated_at', 'created_at'],
                            source_meta={
                                'type': 'job',
                                'id': str(job.get('_id') or ''),
                                'label': job.get('title') or 'Job',
                            }
                        )
                    )

            interview_query = _build_date_range_query(
                {'is_visible': True, 'status': {'$in': ['interviewed', 'selected', 'rejected']}},
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])

            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )

                interview_lines.append(
                    self._build_interview_cost_line(
                        app_with_context,
                        'ai_interview',
                        'Total AI Interview Cost',
                        action_assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    interview_eval_lines.append(
                        self._build_token_cost_line(
                            app_with_eval_context,
                            'ai_interview_evaluation',
                            'Total AI Interview Evaluation Cost',
                            action_assumptions['evaluation'],
                            ['completed_at', 'updated_at', 'created_at'],
                            source_meta={
                                'type': 'application',
                                'id': str(app.get('_id') or ''),
                                'label': app.get('job_title') or 'Application',
                            }
                        )
                    )

            practice_query = _build_date_range_query(
                {'is_practice': True},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            practice_sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []
            for session in practice_sessions:
                practice_lines.append(
                    self._build_interview_cost_line(
                        session,
                        'practice_interview',
                        'Practice Interview Cost',
                        action_assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

                session_with_eval_context = self._with_evaluation_context(session)
                practice_eval_lines.append(
                    self._build_token_cost_line(
                        session_with_eval_context,
                        'practice_interview_evaluation',
                        'Practice Interview Evaluation Cost',
                        action_assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

            cv_item = _aggregate_line_item(
                'cv_scoring',
                'Total CV Score Calculation Cost',
                action_assumptions['cv_scoring']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                cv_lines,
            )
            jd_item = _aggregate_line_item(
                'ai_jd_generation',
                'Total AI JD Generation Cost',
                action_assumptions['ai_jd_generation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                jd_lines,
            )
            interview_item = _aggregate_line_item(
                'ai_interview',
                'Total AI Interview Cost',
                action_assumptions['ai_interview']['model'],
                'count × [LLM token cost + STT(sec/60×rate) + TTS(chars/1M×rate)] × INR conversion',
                interview_lines,
            )
            interview_eval_item = _aggregate_line_item(
                'ai_interview_evaluation',
                'Total AI Interview Evaluation Cost',
                action_assumptions['evaluation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                interview_eval_lines,
            )
            practice_item = _aggregate_line_item(
                'practice_interview',
                'Practice Interview Cost',
                action_assumptions['ai_interview']['model'],
                'count × [LLM token cost + STT(sec/60×rate) + TTS(chars/1M×rate)] × INR conversion',
                practice_lines,
            )
            practice_eval_item = _aggregate_line_item(
                'practice_interview_evaluation',
                'Practice Interview Evaluation Cost',
                action_assumptions['evaluation']['model'],
                'count × ((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
                practice_eval_lines,
            )

            ai_cost_line_items = [
                cv_item,
                jd_item,
                interview_item,
                interview_eval_item,
                practice_item,
                practice_eval_item,
            ]
            total_ai_cost_inr = sum(
                item.get("total_cost_inr", 0.0) for item in ai_cost_line_items
            )

            cv_scoring_count = len(cv_lines)
            jd_generation_count = len(jd_lines)
            completed_interviews = len(interview_lines)
            interview_evaluation_count = len(interview_eval_lines)
            practice_interview_count = len(practice_lines)
            practice_evaluation_count = len(practice_eval_lines)

            cloudflare_total_prorated = _monthly_cost_for_window(monthly_infra_assumptions['cloudflare'], period_start, period_end)
            cloudflare_gpu_prorated = cloudflare_total_prorated * cloudflare_gpu_ratio
            cloudflare_base_prorated = (
                cloudflare_total_prorated - cloudflare_gpu_prorated
            )
            mongodb_prorated = _monthly_cost_for_window(
                monthly_infra_assumptions["mongodb"], period_start, period_end
            )

            infrastructure_costs = {
                "cloudflare": {
                    "monthly_assumption_inr": _round_money(
                        monthly_infra_assumptions["cloudflare"]
                    ),
                    "prorated_cost_inr": _round_money(cloudflare_total_prorated),
                    "gpu_component_inr": _round_money(cloudflare_gpu_prorated),
                    "base_component_inr": _round_money(cloudflare_base_prorated),
                    "note": "GPU share is a derived component inside Cloudflare cost (not added separately).",
                },
                "mongodb": {
                    "monthly_assumption_inr": _round_money(
                        monthly_infra_assumptions["mongodb"]
                    ),
                    "prorated_cost_inr": _round_money(mongodb_prorated),
                },
            }
            total_infrastructure_cost_inr = _round_money(
                cloudflare_total_prorated + mongodb_prorated
            )
            total_cost_inr = _round_money(
                total_ai_cost_inr + total_infrastructure_cost_inr
            )

            payments_query = {
                "$and": [
                    {"status": "succeeded"},
                    {
                        "$or": [
                            {
                                "completed_at": {
                                    "$gte": period_start,
                                    "$lte": period_end,
                                }
                            },
                            {"created_at": {"$gte": period_start, "$lte": period_end}},
                        ]
                    },
                ]
            }
            succeeded_payments = (
                list(payments_collection.find(payments_query))
                if payments_collection is not None
                else []
            )

            def _resolve_payment_plan(payment_doc):
                plan_doc = plans_by_id.get(payment_doc.get("plan_id"))
                snapshot = payment_doc.get("metadata", {}) or {}
                if not plan_doc:
                    fallback_snapshot = payment_doc.get("plan_snapshot") or {}
                    snapshot = {**fallback_snapshot, **snapshot}

                plan_name = (
                    (plan_doc or {}).get("name")
                    or snapshot.get("plan_name")
                    or snapshot.get("name")
                    or "Unknown Plan"
                )
                plan_slug = (
                    (plan_doc or {}).get("slug")
                    or snapshot.get("plan_slug")
                    or snapshot.get("slug")
                    or "unknown-plan"
                )
                audience = (
                    (plan_doc or {}).get("audience")
                    or snapshot.get("owner_type")
                    or snapshot.get("audience")
                    or "recruiter"
                )
                if audience not in {"candidate", "recruiter"}:
                    audience = "recruiter"

                price_paise = (
                    (plan_doc or {}).get("price_paise")
                    or snapshot.get("price_paise")
                    or 0
                )

                return {
                    "name": plan_name,
                    "slug": plan_slug,
                    "audience": audience,
                    "price_inr": _round_money((price_paise or 0) / 100.0),
                }

            incoming_summary = {
                "candidate": {
                    "plans": {},
                    "succeeded_payment_count": 0,
                    "migration_payment_count": 0,
                    "total_incoming_inr": 0.0,
                },
                "recruiter": {
                    "plans": {},
                    "succeeded_payment_count": 0,
                    "migration_payment_count": 0,
                    "total_incoming_inr": 0.0,
                },
            }

            for payment_doc in succeeded_payments:
                payment_amount_inr = (payment_doc.get("amount_paise", 0) or 0) / 100.0
                plan_data = _resolve_payment_plan(payment_doc)
                audience = plan_data["audience"]
                plan_key = f"{plan_data['slug']}::{plan_data['price_inr']}"
                payment_metadata = payment_doc.get("metadata", {}) or {}
                is_migration_payment = bool(payment_metadata.get("migration"))

                if plan_key not in incoming_summary[audience]["plans"]:
                    incoming_summary[audience]["plans"][plan_key] = {
                        "plan_name": plan_data["name"],
                        "plan_slug": plan_data["slug"],
                        "plan_price_inr": plan_data["price_inr"],
                        "succeeded_payment_count": 0,
                        "migration_payment_count": 0,
                        "incoming_amount_inr": 0.0,
                    }

                incoming_summary[audience]["plans"][plan_key][
                    "succeeded_payment_count"
                ] += 1
                if is_migration_payment:
                    incoming_summary[audience]["plans"][plan_key][
                        "migration_payment_count"
                    ] += 1
                incoming_summary[audience]["plans"][plan_key][
                    "incoming_amount_inr"
                ] += payment_amount_inr
                incoming_summary[audience]["succeeded_payment_count"] += 1
                if is_migration_payment:
                    incoming_summary[audience]["migration_payment_count"] += 1
                incoming_summary[audience]["total_incoming_inr"] += payment_amount_inr

            refund_query = {
                "$and": [
                    {"status": {"$in": ["refunded", "partially_refunded"]}},
                    {
                        "$or": [
                            {"updated_at": {"$gte": period_start, "$lte": period_end}},
                            {"created_at": {"$gte": period_start, "$lte": period_end}},
                        ]
                    },
                ]
            }
            refund_payments = (
                list(payments_collection.find(refund_query))
                if payments_collection is not None
                else []
            )
            refund_total_inr = _round_money(
                sum(
                    (p.get("refund_amount_paise", 0) or 0) / 100.0
                    for p in refund_payments
                )
            )

            candidate_plans = sorted(
                [
                    {
                        **plan_row,
                        "incoming_amount_inr": _round_money(
                            plan_row["incoming_amount_inr"]
                        ),
                    }
                    for plan_row in incoming_summary["candidate"]["plans"].values()
                ],
                key=lambda item: (-item["incoming_amount_inr"], item["plan_name"]),
            )
            recruiter_plans = sorted(
                [
                    {
                        **plan_row,
                        "incoming_amount_inr": _round_money(
                            plan_row["incoming_amount_inr"]
                        ),
                    }
                    for plan_row in incoming_summary["recruiter"]["plans"].values()
                ],
                key=lambda item: (-item["incoming_amount_inr"], item["plan_name"]),
            )

            candidate_total_incoming = _round_money(
                incoming_summary["candidate"]["total_incoming_inr"]
            )
            recruiter_total_incoming = _round_money(
                incoming_summary["recruiter"]["total_incoming_inr"]
            )
            total_incoming = _round_money(
                candidate_total_incoming + recruiter_total_incoming
            )
            net_incoming_after_refunds = _round_money(total_incoming - refund_total_inr)

            profit_gross = _round_money(total_incoming - total_cost_inr)
            profit_net = _round_money(net_incoming_after_refunds - total_cost_inr)
            margin_gross = (
                round((_safe_div(profit_gross, total_incoming) * 100.0), 2)
                if total_incoming > 0
                else 0.0
            )
            margin_net = (
                round((_safe_div(profit_net, net_incoming_after_refunds) * 100.0), 2)
                if net_incoming_after_refunds > 0
                else 0.0
            )

            return {
                "timeline": {
                    "period_mode": normalized_period,
                    "start_date": _safe_iso(period_start),
                    "end_date": _safe_iso(period_end),
                    "days": max(1, (period_end - period_start).days),
                },
                "cost_statistics": {
                    "currency": "INR",
                    "ai_costs": ai_cost_line_items,
                    "total_ai_cost_inr": _round_money(total_ai_cost_inr),
                    "infrastructure_costs": {
                        **infrastructure_costs,
                        "total_infrastructure_cost_inr": total_infrastructure_cost_inr,
                    },
                    "total_cost_inr": total_cost_inr,
                },
                "incoming_money": {
                    "candidate": {
                        "plans": candidate_plans,
                        "succeeded_payment_count": incoming_summary["candidate"][
                            "succeeded_payment_count"]
                        ,
                        "migration_payment_count": incoming_summary["candidate"][
                            "migration_payment_count"]
                        ,
                        "total_incoming_inr": candidate_total_incoming,
                    },
                    "recruiter": {
                        "plans": recruiter_plans,
                        "succeeded_payment_count": incoming_summary["recruiter"][
                            "succeeded_payment_count"]
                        ,
                        "migration_payment_count": incoming_summary["recruiter"][
                            "migration_payment_count"]
                        ,
                        "total_incoming_inr": recruiter_total_incoming,
                    },
                    "total_incoming_inr": total_incoming,
                    "refund_adjustments": {
                        "refund_events_count": len(refund_payments),
                        "total_refunded_inr": refund_total_inr,
                    },
                    "net_incoming_after_refunds_inr": net_incoming_after_refunds,
                },
                "profitability": {
                    "cost_total_inr": total_cost_inr,
                    "incoming_total_inr": total_incoming,
                    "net_incoming_after_refunds_inr": net_incoming_after_refunds,
                    "profit_gross_inr": profit_gross,
                    "profit_net_inr": profit_net,
                    "margin_gross_pct": margin_gross,
                    "margin_net_pct": margin_net,
                },
                "activity_counts": {
                    "cv_scoring": int(cv_scoring_count),
                    "ai_jd_generation": int(jd_generation_count),
                    "ai_interview": int(completed_interviews),
                    "ai_interview_evaluation": int(interview_evaluation_count),
                    "practice_interview": int(practice_interview_count),
                    "practice_interview_evaluation": int(practice_evaluation_count),
                },
                "assumptions": {
                    "pricing_reference": "interview/core/cost_tracker.py",
                    "inr_per_usd": inr_per_usd,
                    "timeline_fallback_period": period,
                    "evaluation_assumption_tokens": {
                        "prompt": action_assumptions["evaluation"]["prompt_tokens"],
                        "completion": action_assumptions["evaluation"]["completion_tokens"],
                    },
                    "monthly_infrastructure_assumptions_inr": monthly_infra_assumptions,
                    "cloudflare_gpu_ratio": round(cloudflare_gpu_ratio, 4),
                },
            }, 200

        except Exception as e:
            import traceback

            print(f"Error getting admin cost statistics: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get cost statistics'}, 500

    def _round_money(self, value):
        return round(float(value or 0.0), 2)

    def _safe_iso(self, dt_val):
        return dt_val.isoformat() if dt_val else None

    def _safe_div(self, num, den):
        return (num / den) if den else 0.0

    def _parse_date(self, date_value, end_of_day=False):
        if not date_value:
            return None

        parsed = None
        try:
            parsed = datetime.datetime.fromisoformat(str(date_value).replace("Z", "+00:00"))
        except Exception:
            try:
                parsed = datetime.datetime.strptime(str(date_value), "%Y-%m-%d")
            except Exception:
                return None

        if parsed.tzinfo is not None:
            parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)

        if len(str(date_value)) <= 10:
            parsed = parsed.replace(
                hour=23 if end_of_day else 0,
                minute=59 if end_of_day else 0,
                second=59 if end_of_day else 0,
                microsecond=999999 if end_of_day else 0,
            )

        return parsed

    def _period_window(self, period_value):
        now = datetime.datetime.utcnow()
        normalized_period = (period_value or "month").lower()

        if normalized_period == "week":
            start = now - datetime.timedelta(days=7)
        elif normalized_period == "quarter":
            start = now - datetime.timedelta(days=90)
        elif normalized_period == "year":
            start = now - datetime.timedelta(days=365)
        else:
            normalized_period = "month"
            start = now - datetime.timedelta(days=30)

        return normalized_period, start, now

    def _resolve_timeline_window(self, period='month', start_date=None, end_date=None):
        normalized_period, period_start, period_end = self._period_window(period)
        requested_start = self._parse_date(start_date, end_of_day=False)
        requested_end = self._parse_date(end_date, end_of_day=True) if end_date else None

        if start_date and requested_start is None:
            return None, None, None, {'error': 'Invalid start_date format. Use YYYY-MM-DD.'}, 400

        if end_date and requested_end is None:
            return None, None, None, {'error': 'Invalid end_date format. Use YYYY-MM-DD.'}, 400

        if requested_end is None:
            requested_end = datetime.datetime.utcnow()

        if requested_start:
            period_start = requested_start
            period_end = requested_end
            normalized_period = 'custom'

        if period_start > period_end:
            return None, None, None, {'error': 'Invalid timeline. start_date cannot be after end_date.'}, 400

        return normalized_period, period_start, period_end, None, 200

    def _build_date_range_query(self, base_query, date_fields, start_dt, end_dt):
        if not date_fields:
            return base_query

        date_conditions = [
            {field_name: {"$gte": start_dt, "$lte": end_dt}}
            for field_name in date_fields
        ]

        return {"$and": [base_query, {"$or": date_conditions}]}

    def _extract_numeric(self, value):
        if isinstance(value, (int, float)):
            return float(value)
        return None

    def _extract_usage_metric(self, doc, keys, nested_dict_keys=None):
        nested_dict_keys = nested_dict_keys or []

        for key in keys:
            value = self._extract_numeric(doc.get(key))
            if value is not None:
                return value, 'actual'

        for nested_key in nested_dict_keys:
            nested_value = doc.get(nested_key)
            if not isinstance(nested_value, dict):
                continue
            for key in keys:
                value = self._extract_numeric(nested_value.get(key))
                if value is not None:
                    return value, 'actual'

        return None, 'assumed'

    def _collect_text_fragments(self, value, sink):
        if value is None:
            return

        if isinstance(value, str):
            normalized = value.strip()
            if normalized:
                sink.append(normalized)
            return

        if isinstance(value, dict):
            for nested_value in value.values():
                self._collect_text_fragments(nested_value, sink)
            return

        if isinstance(value, list):
            for nested_value in value:
                self._collect_text_fragments(nested_value, sink)
            return

        if isinstance(value, (int, float, bool)):
            sink.append(str(value))

    def _estimate_text_tokens(self, text):
        if not text:
            return 0
        normalized_text = str(text)
        words = len(re.findall(r"\S+", normalized_text))
        chars = len(normalized_text)

        tokens_by_words = words / 0.75
        tokens_by_chars = chars / 4.0
        return int(round(max(tokens_by_words, tokens_by_chars)))

    def _estimate_token_count_from_value(self, value):
        chunks = []
        self._collect_text_fragments(value, chunks)
        if not chunks:
            return 0
        return self._estimate_text_tokens(' '.join(chunks))

    def _parse_datetime_value(self, value):
        if isinstance(value, datetime.datetime):
            return value
        if not isinstance(value, str):
            return None

        raw = value.strip()
        if not raw:
            return None

        for candidate in [raw, raw.replace('Z', '+00:00')]:
            try:
                parsed = datetime.datetime.fromisoformat(candidate)
                if parsed.tzinfo is not None:
                    parsed = parsed.astimezone(datetime.timezone.utc).replace(tzinfo=None)
                return parsed
            except Exception:
                continue

        for fmt in ['%a, %d %b %Y %H:%M:%S %Z', '%a, %d %b %Y %H:%M:%S GMT']:
            try:
                return datetime.datetime.strptime(raw, fmt)
            except Exception:
                continue

        return None

    def _qa_pairs(self, doc):
        if not isinstance(doc, dict):
            return []
        qa_pairs = doc.get('qa_pairs')
        if isinstance(qa_pairs, list) and qa_pairs:
            return qa_pairs

        qa_history = doc.get('qa_history')
        if isinstance(qa_history, list) and qa_history:
            return qa_history

        interview_data = doc.get('interview_data')
        if isinstance(interview_data, list) and interview_data:
            return interview_data

        return []

    def _transcript_messages(self, doc):
        transcript = doc.get('transcript') if isinstance(doc, dict) else None
        if isinstance(transcript, list) and transcript:
            return transcript

        messages = []
        for pair in self._qa_pairs(doc):
            if not isinstance(pair, dict):
                continue

            question = pair.get('question')
            answer = pair.get('answer')

            if isinstance(question, str) and question.strip():
                messages.append({'role': 'assistant', 'text': question})
            if isinstance(answer, str) and answer.strip():
                messages.append({'role': 'user', 'text': answer})

        return messages

    def _transcript_token_usage(self, doc):
        stats = self._interview_token_breakdown(doc)
        prompt_tokens = stats.get('cumulative_prompt_tokens') or 0
        completion_tokens = stats.get('question_tokens') or 0

        if prompt_tokens == 0 and completion_tokens == 0:
            return None, None

        return prompt_tokens, completion_tokens

    def _interview_token_breakdown(self, doc):
        messages = self._transcript_messages(doc)
        if not messages:
            return {
                'question_tokens': 0,
                'answer_tokens': 0,
                'qa_total_tokens': 0,
                'cumulative_prompt_tokens': 0,
            }

        pairs = []
        current_question_tokens = None

        question_roles = {'assistant', 'ai', 'bot', 'interviewer', 'system'}

        for item in messages:
            if not isinstance(item, dict):
                continue

            role = str(item.get('role') or '').strip().lower()
            text = item.get('text')
            if not isinstance(text, str):
                text = item.get('content')
            if not isinstance(text, str):
                continue

            token_count = self._estimate_text_tokens(text)
            if token_count <= 0:
                continue

            if role in question_roles:
                if current_question_tokens is not None:
                    pairs.append((current_question_tokens, 0))
                current_question_tokens = token_count
            else:
                if current_question_tokens is None:
                    pairs.append((0, token_count))
                else:
                    pairs.append((current_question_tokens, token_count))
                    current_question_tokens = None

        if current_question_tokens is not None:
            pairs.append((current_question_tokens, 0))

        question_tokens = sum(question for question, _ in pairs)
        answer_tokens = sum(answer for _, answer in pairs)
        qa_total_tokens = question_tokens + answer_tokens

        running_history = 0
        cumulative_prompt_tokens = 0
        for question, answer in pairs:
            pair_total = question + answer
            cumulative_prompt_tokens += running_history + pair_total
            running_history += pair_total

        return {
            'question_tokens': int(question_tokens),
            'answer_tokens': int(answer_tokens),
            'qa_total_tokens': int(qa_total_tokens),
            'cumulative_prompt_tokens': int(cumulative_prompt_tokens),
        }

    def _transcript_tts_characters(self, doc):
        # Per requested accounting rule, TTS proxy uses total question tokens.
        question_tokens = self._interview_token_breakdown(doc).get('question_tokens') or 0
        return int(question_tokens) if question_tokens > 0 else None

    def _derived_stt_seconds(self, doc):
        # Per requested accounting rule, STT uses answer tokens converted to seconds.
        answer_tokens = self._interview_token_breakdown(doc).get('answer_tokens') or 0
        if answer_tokens > 0:
            return float(answer_tokens) * 0.4

        created_at = self._parse_datetime_value(doc.get('created_at') if isinstance(doc, dict) else None)
        completed_at = self._parse_datetime_value(doc.get('completed_at') if isinstance(doc, dict) else None)
        updated_at = self._parse_datetime_value(doc.get('updated_at') if isinstance(doc, dict) else None)

        if isinstance(created_at, datetime.datetime) and isinstance(completed_at, datetime.datetime):
            return max(0.0, (completed_at - created_at).total_seconds())

        if isinstance(created_at, datetime.datetime) and isinstance(updated_at, datetime.datetime):
            return max(0.0, (updated_at - created_at).total_seconds())

        first_ts = None
        last_ts = None
        for pair in self._qa_pairs(doc):
            if not isinstance(pair, dict):
                continue
            ts = self._parse_datetime_value(pair.get('timestamp'))
            if ts is None:
                continue
            if first_ts is None or ts < first_ts:
                first_ts = ts
            if last_ts is None or ts > last_ts:
                last_ts = ts

        if first_ts and last_ts:
            return max(0.0, (last_ts - first_ts).total_seconds())

        return None

    def _derive_token_usage_from_doc(self, doc, action_type):
        if not isinstance(doc, dict):
            return None, None

        normalized_action = str(action_type or '').strip().lower()

        interview_stats = self._interview_token_breakdown(doc)

        if normalized_action in {'ai_interview', 'practice_interview'}:
            prompt_tokens = interview_stats.get('cumulative_prompt_tokens') or 0
            completion_tokens = interview_stats.get('question_tokens') or 0
            return (
                int(prompt_tokens) if prompt_tokens > 0 else None,
                int(completion_tokens) if completion_tokens > 0 else None,
            )

        if normalized_action in {'ai_interview_evaluation', 'practice_interview_evaluation'}:
            prompt_tokens = interview_stats.get('qa_total_tokens') or 0
            eval_tokens = self._estimate_token_count_from_value(doc.get('evaluation'))
            return (
                int(prompt_tokens) if prompt_tokens > 0 else None,
                int(eval_tokens) if eval_tokens > 0 else None,
            )

        if normalized_action == 'cv_scoring':
            cv_text = (((doc.get('cv_snapshot') or {}).get('text')) or '').strip()
            jd_text = (((doc.get('jd_snapshot') or {}).get('text')) or '').strip()
            prompt_tokens = self._estimate_text_tokens(f"{cv_text}\n{jd_text}".strip())
            completion_tokens = self._estimate_token_count_from_value(doc.get('cv_score_breakdown'))

            if prompt_tokens <= 0:
                prompt_tokens = None
            if completion_tokens <= 0:
                completion_tokens = None

            return prompt_tokens, completion_tokens

        if normalized_action == 'ai_jd_generation':
            metadata = doc.get('metadata') if isinstance(doc.get('metadata'), dict) else {}
            prompt_text = (metadata.get('prompt_text') or '').strip()
            generated_jd_text = (metadata.get('generated_jd_text') or '').strip()

            if prompt_text or generated_jd_text:
                prompt_tokens = self._estimate_text_tokens(prompt_text)
                completion_tokens = self._estimate_text_tokens(generated_jd_text)
                return (
                    int(prompt_tokens) if prompt_tokens > 0 else None,
                    int(completion_tokens) if completion_tokens > 0 else None,
                )

            prompt_seed = {
                'title': doc.get('title'),
                'department': doc.get('department'),
                'location': doc.get('location'),
                'type': doc.get('type'),
                'experience': doc.get('experience'),
                'salary': doc.get('salary'),
            }
            completion_seed = {
                'description': doc.get('description'),
                'skills': doc.get('skills'),
                'responsibilities': doc.get('responsibilities'),
                'requirements': doc.get('requirements'),
                'benefits': doc.get('benefits'),
            }
            prompt_tokens = self._estimate_token_count_from_value(prompt_seed)
            completion_tokens = self._estimate_token_count_from_value(completion_seed)

            if prompt_tokens <= 0:
                prompt_tokens = None
            if completion_tokens <= 0:
                completion_tokens = None

            return prompt_tokens, completion_tokens

        return None, None

    def _latest_interview_reports_by_application(self, application_ids):
        if self.interviews_collection is None:
            return {}

        ids = [str(app_id) for app_id in application_ids if app_id is not None]
        if not ids:
            return {}

        reports = list(self.interviews_collection.find({'application_id': {'$in': ids}}))
        latest_map = {}

        for report in reports:
            app_id = str(report.get('application_id') or '')
            if not app_id:
                continue

            existing = latest_map.get(app_id)
            report_ts = report.get('updated_at') or report.get('created_at')
            existing_ts = (existing or {}).get('updated_at') or (existing or {}).get('created_at')

            if existing is None or (report_ts and (not existing_ts or report_ts > existing_ts)):
                latest_map[app_id] = report

        return latest_map

    def _merge_application_interview_context(self, app_doc, interview_report):
        if not isinstance(app_doc, dict):
            return app_doc

        if not isinstance(interview_report, dict):
            return app_doc

        merged = dict(app_doc)

        if not merged.get('transcript') and isinstance(interview_report.get('transcript'), list):
            merged['transcript'] = interview_report.get('transcript')

        if not merged.get('qa_pairs') and isinstance(interview_report.get('qa_pairs'), list):
            merged['qa_pairs'] = interview_report.get('qa_pairs')

        if merged.get('evaluation') in [None, '', {}] and isinstance(interview_report.get('evaluation'), dict):
            merged['evaluation'] = interview_report.get('evaluation')

        if merged.get('usage_summary') in [None, '', {}] and isinstance(interview_report.get('usage_summary'), dict):
            merged['usage_summary'] = interview_report.get('usage_summary')

        if merged.get('usage_source') in [None, ''] and interview_report.get('usage_source'):
            merged['usage_source'] = interview_report.get('usage_source')

        usage_doc = interview_report.get('usage') if isinstance(interview_report.get('usage'), dict) else None
        if usage_doc:
            if merged.get('prompt_tokens') is None and usage_doc.get('prompt_tokens') is not None:
                merged['prompt_tokens'] = usage_doc.get('prompt_tokens')
            if merged.get('completion_tokens') is None and usage_doc.get('completion_tokens') is not None:
                merged['completion_tokens'] = usage_doc.get('completion_tokens')

        for dt_key in ['created_at', 'completed_at', 'updated_at']:
            if merged.get(dt_key) is None and interview_report.get(dt_key) is not None:
                merged[dt_key] = interview_report.get(dt_key)

        return merged

    def _extract_evaluation_payload(self, doc):
        if not isinstance(doc, dict):
            return None

        candidates = [
            doc.get('evaluation'),
            doc.get('final_evaluation'),
        ]

        result = doc.get('result')
        if isinstance(result, dict):
            candidates.extend([
                result.get('evaluation'),
                result.get('final_evaluation'),
            ])

        for value in candidates:
            if value in [None, '', {}, []]:
                continue
            return value

        return None

    def _with_evaluation_context(self, doc):
        if not isinstance(doc, dict):
            return doc

        evaluation_payload = self._extract_evaluation_payload(doc)
        if evaluation_payload is None:
            return doc

        if doc.get('evaluation') not in [None, '', {}, []]:
            return doc

        merged = dict(doc)
        merged['evaluation'] = evaluation_payload
        return merged

    def _has_interview_evaluation(self, doc):
        if not isinstance(doc, dict):
            return False

        if self._extract_evaluation_payload(doc) is not None:
            return True

        if doc.get('interview_score') not in [None, '']:
            return True

        if doc.get('final_score') not in [None, '']:
            return True

        status = str(doc.get('status') or '').strip().lower()
        if status in {'interviewed', 'selected', 'rejected', 'completed'}:
            return True

        interview_stats = self._interview_token_breakdown(doc)
        return (interview_stats.get('qa_total_tokens') or 0) > 0

    def _build_token_cost_line(self, doc, action_type, title, cfg, timestamp_fields, source_id=None, source_meta=None):
        source_meta = source_meta or {}

        from interview.core.cost_tracker import CostTracker, calculate_cost
        pricing = CostTracker.PRICING
        inr_per_usd = 83.0

        prompt_tokens, prompt_source = self._extract_usage_metric(
            doc,
            ['prompt_tokens', 'input_tokens', 'llm_prompt_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        completion_tokens, completion_source = self._extract_usage_metric(
            doc,
            ['completion_tokens', 'output_tokens', 'llm_completion_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )

        if str(doc.get('usage_source') or '').strip().lower() == 'assumed':
            prompt_tokens = None
            completion_tokens = None
            prompt_source = 'assumed'
            completion_source = 'assumed'

        if prompt_tokens is not None and prompt_tokens <= 0:
            prompt_tokens = None
            prompt_source = 'assumed'
        if completion_tokens is not None and completion_tokens <= 0:
            completion_tokens = None
            completion_source = 'assumed'

        if prompt_tokens is None or completion_tokens is None:
            derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
            if prompt_tokens is None and derived_prompt_tokens is not None:
                prompt_tokens = derived_prompt_tokens
                prompt_source = 'actual'
            if completion_tokens is None and derived_completion_tokens is not None:
                completion_tokens = derived_completion_tokens
                completion_source = 'actual'

        # If stored values look like known defaults, prefer transcript-derived values.
        derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
        if (
            derived_prompt_tokens is not None
            and int(prompt_tokens or 0) == int(cfg['prompt_tokens'])
        ):
            prompt_tokens = derived_prompt_tokens
            prompt_source = 'actual'
        if (
            derived_completion_tokens is not None
            and int(completion_tokens or 0) == int(cfg['completion_tokens'])
        ):
            completion_tokens = derived_completion_tokens
            completion_source = 'actual'

        prompt_tokens = int(prompt_tokens if prompt_tokens is not None else cfg['prompt_tokens'])
        completion_tokens = int(completion_tokens if completion_tokens is not None else cfg['completion_tokens'])

        rates = pricing.get(cfg['model'], {})
        input_rate = rates.get('input', 0.0)
        output_rate = rates.get('output', 0.0)

        llm_usd = ((prompt_tokens / 1_000_000.0) * input_rate) + ((completion_tokens / 1_000_000.0) * output_rate)
        calculated_cost_inr = llm_usd * inr_per_usd

        actual_llm_usd = None
        if prompt_source == 'actual' or completion_source == 'actual':
            actual_llm_usd = calculate_cost(
                cfg['model'],
                {
                    'prompt_tokens': prompt_tokens,
                    'completion_tokens': completion_tokens,
                },
            )
        actual_cost_inr = (
            self._round_money(actual_llm_usd * inr_per_usd)
            if actual_llm_usd is not None
            else None
        )

        timestamp = None
        for field_name in timestamp_fields:
            dt_val = self._parse_datetime_value(doc.get(field_name))
            if isinstance(dt_val, datetime.datetime):
                timestamp = dt_val
                break

        usage_source = 'actual' if prompt_source == 'actual' or completion_source == 'actual' else 'assumed'

        return {
            'id': str(source_id or doc.get('_id') or ''),
            'action_type': action_type,
            'title': title,
            'timestamp': self._safe_iso(timestamp),
            'model': cfg['model'],
            'usage_source': usage_source,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'stt_seconds': 0,
            'tts_characters': 0,
            'rates': {
                'input_usd_per_1m_tokens': input_rate,
                'output_usd_per_1m_tokens': output_rate,
            },
            'formula': '((prompt/1M × input_rate) + (completion/1M × output_rate)) × INR conversion',
            'cost_inr': self._round_money(calculated_cost_inr),
            'calculated_cost_inr': self._round_money(calculated_cost_inr),
            'actual_cost_inr': actual_cost_inr,
            'source': {
                'type': source_meta.get('type', ''),
                'id': source_meta.get('id', ''),
                'label': source_meta.get('label', ''),
            }
        }

    def _build_interview_cost_line(self, doc, action_type, title, cfg, timestamp_fields, source_id=None, source_meta=None):
        source_meta = source_meta or {}

        from interview.core.cost_tracker import CostTracker
        pricing = CostTracker.PRICING
        inr_per_usd = 83.0

        prompt_tokens, prompt_source = self._extract_usage_metric(
            doc,
            ['prompt_tokens', 'input_tokens', 'llm_prompt_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        completion_tokens, completion_source = self._extract_usage_metric(
            doc,
            ['completion_tokens', 'output_tokens', 'llm_completion_tokens'],
            nested_dict_keys=['usage', 'token_usage', 'cost_usage']
        )
        stt_seconds, stt_source = self._extract_usage_metric(
            doc,
            ['stt_seconds', 'audio_seconds', 'speech_seconds'],
            nested_dict_keys=['usage', 'audio_usage', 'cost_usage']
        )
        tts_characters, tts_source = self._extract_usage_metric(
            doc,
            ['tts_characters', 'character_count', 'tts_chars'],
            nested_dict_keys=['usage', 'audio_usage', 'cost_usage']
        )

        if str(doc.get('usage_source') or '').strip().lower() == 'assumed':
            prompt_tokens = None
            completion_tokens = None
            stt_seconds = None
            tts_characters = None
            prompt_source = 'assumed'
            completion_source = 'assumed'
            stt_source = 'assumed'
            tts_source = 'assumed'

        if prompt_tokens is not None and prompt_tokens <= 0:
            prompt_tokens = None
            prompt_source = 'assumed'
        if completion_tokens is not None and completion_tokens <= 0:
            completion_tokens = None
            completion_source = 'assumed'
        if stt_seconds is not None and stt_seconds <= 0:
            stt_seconds = None
            stt_source = 'assumed'
        if tts_characters is not None and tts_characters <= 0:
            tts_characters = None
            tts_source = 'assumed'

        if prompt_tokens is None or completion_tokens is None:
            derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
            if prompt_tokens is None and derived_prompt_tokens is not None:
                prompt_tokens = derived_prompt_tokens
                prompt_source = 'actual'
            if completion_tokens is None and derived_completion_tokens is not None:
                completion_tokens = derived_completion_tokens
                completion_source = 'actual'

        # If stored values look like default assumptions, prefer transcript-derived values.
        derived_prompt_tokens, derived_completion_tokens = self._derive_token_usage_from_doc(doc, action_type)
        if (
            derived_prompt_tokens is not None
            and int(prompt_tokens or 0) == int(cfg['prompt_tokens'])
        ):
            prompt_tokens = derived_prompt_tokens
            prompt_source = 'actual'
        if (
            derived_completion_tokens is not None
            and int(completion_tokens or 0) == int(cfg['completion_tokens'])
        ):
            completion_tokens = derived_completion_tokens
            completion_source = 'actual'

        if stt_seconds is None:
            derived_stt = self._derived_stt_seconds(doc)
            if derived_stt is not None:
                stt_seconds = derived_stt
                stt_source = 'actual'

        derived_stt = self._derived_stt_seconds(doc)
        if (
            derived_stt is not None
            and (stt_seconds is None or float(stt_seconds or 0.0) == float(cfg['stt_seconds']))
        ):
            stt_seconds = derived_stt
            stt_source = 'actual'

        if tts_characters is None:
            derived_tts_chars = self._transcript_tts_characters(doc)
            if derived_tts_chars is not None:
                tts_characters = derived_tts_chars
                tts_source = 'actual'

        derived_tts_chars = self._transcript_tts_characters(doc)
        if (
            derived_tts_chars is not None
            and (tts_characters is None or int(tts_characters or 0) == int(cfg['tts_characters']))
        ):
            tts_characters = derived_tts_chars
            tts_source = 'actual'

        prompt_tokens = int(prompt_tokens if prompt_tokens is not None else cfg['prompt_tokens'])
        completion_tokens = int(completion_tokens if completion_tokens is not None else cfg['completion_tokens'])
        stt_seconds = float(stt_seconds if stt_seconds is not None else cfg['stt_seconds'])
        tts_characters = int(tts_characters if tts_characters is not None else cfg['tts_characters'])

        rates = pricing.get(cfg['model'], {})
        input_rate = rates.get('input', 0.0)
        output_rate = rates.get('output', 0.0)
        stt_rate_per_15s = pricing.get('gcp_stt', {}).get('default', 0.006)
        tts_rates = pricing.get('gcp_tts', {})
        tts_voice_type = str(doc.get('tts_voice_type') or 'standard').lower()
        tts_rate = tts_rates.get(tts_voice_type, tts_rates.get('standard', 0.000004))

        llm_usd = ((prompt_tokens / 1_000_000.0) * input_rate) + ((completion_tokens / 1_000_000.0) * output_rate)
        stt_billed_units = math.ceil(stt_seconds / 15.0) if stt_seconds > 0 else 0
        stt_usd = stt_billed_units * stt_rate_per_15s
        tts_usd = tts_characters * tts_rate
        calculated_cost_inr = (llm_usd + stt_usd + tts_usd) * inr_per_usd

        actual_llm_usd = None
        usage_summary = doc.get('usage_summary') if isinstance(doc, dict) else None
        if isinstance(usage_summary, dict):
            summary_actual = usage_summary.get('total_actual_cost')
            summary_actual_val = self._extract_numeric(summary_actual)
            if summary_actual_val is not None and summary_actual_val > 0:
                actual_llm_usd = summary_actual_val
        actual_cost_inr = (
            self._round_money((actual_llm_usd + stt_usd + tts_usd) * inr_per_usd)
            if actual_llm_usd is not None
            else None
        )

        timestamp = None
        for field_name in timestamp_fields:
            dt_val = self._parse_datetime_value(doc.get(field_name))
            if isinstance(dt_val, datetime.datetime):
                timestamp = dt_val
                break

        usage_source = 'actual' if 'actual' in [prompt_source, completion_source, stt_source, tts_source] else 'assumed'

        return {
            'id': str(source_id or doc.get('_id') or ''),
            'action_type': action_type,
            'title': title,
            'timestamp': self._safe_iso(timestamp),
            'model': cfg['model'],
            'usage_source': usage_source,
            'prompt_tokens': prompt_tokens,
            'completion_tokens': completion_tokens,
            'stt_seconds': stt_seconds,
            'tts_characters': tts_characters,
            'rates': {
                'input_usd_per_1m_tokens': input_rate,
                'output_usd_per_1m_tokens': output_rate,
                'stt_usd_per_15_seconds': stt_rate_per_15s,
                'tts_usd_per_character': tts_rate,
            },
            'formula': '[LLM token cost + STT(ceil(sec/15)×rate) + TTS(chars×rate)] × INR conversion',
            'cost_inr': self._round_money(calculated_cost_inr),
            'calculated_cost_inr': self._round_money(calculated_cost_inr),
            'actual_cost_inr': actual_cost_inr,
            'source': {
                'type': source_meta.get('type', ''),
                'id': source_meta.get('id', ''),
                'label': source_meta.get('label', ''),
            }
        }

    def _action_assumptions(self):
        return {
            'cv_scoring': {
                'model': 'gemini-1.5-flash-latest',
                'prompt_tokens': 1800,
                'completion_tokens': 600,
            },
            'ai_jd_generation': {
                'model': 'llama-3.3-70b-versatile',
                'prompt_tokens': 1500,
                'completion_tokens': 1200,
            },
            'ai_interview': {
                'model': 'gpt-4o',
                'prompt_tokens': 4200,
                'completion_tokens': 2100,
                'stt_seconds': 900,
                'tts_characters': 22000,
            },
            'evaluation': {
                'model': 'gpt-5-mini',
                'prompt_tokens': 1500,
                'completion_tokens': 1000,
            },
        }

    def _find_matching_user_id(self, user_id_map, raw_user_id):
        if raw_user_id is None:
            return None
        user_id_str = str(raw_user_id)
        return user_id_str if user_id_str in user_id_map else None

    def _user_succeeded_incoming_map(self, period_start, period_end, audience='candidate'):
        payments_collection = self.users_collection.database.get_collection('payments')
        plans_collection = self.users_collection.database.get_collection('plans')
        if payments_collection is None:
            return {}

        plans = list(plans_collection.find({})) if plans_collection is not None else []
        plans_by_id = {plan_doc.get("_id"): plan_doc for plan_doc in plans}

        query = {
            '$and': [
                {'status': 'succeeded'},
                {
                    '$or': [
                        {'completed_at': {'$gte': period_start, '$lte': period_end}},
                        {'created_at': {'$gte': period_start, '$lte': period_end}},
                    ]
                }
            ]
        }
        payments = list(payments_collection.find(query))

        incoming_map = defaultdict(float)
        for payment in payments:
            employer_id = payment.get('employer_id')
            if employer_id is None:
                continue

            plan_doc = plans_by_id.get(payment.get('plan_id'))
            snapshot = payment.get('metadata', {}) or {}
            if not plan_doc:
                fallback_snapshot = payment.get('plan_snapshot') or {}
                snapshot = {**fallback_snapshot, **snapshot}

            payment_audience = (
                (plan_doc or {}).get('audience')
                or snapshot.get('owner_type')
                or snapshot.get('audience')
                or 'recruiter'
            )
            if payment_audience not in {'candidate', 'recruiter'}:
                payment_audience = 'recruiter'

            if payment_audience != audience:
                continue

            incoming_map[str(employer_id)] += float((payment.get('amount_paise', 0) or 0) / 100.0)

        return {key: self._round_money(value) for key, value in incoming_map.items()}

    def _active_plan_name_map(self, audience='candidate'):
        subscriptions_collection = self.users_collection.database.get_collection('subscriptions')
        if subscriptions_collection is None:
            return {}

        audience_filter = (
            {'plan_snapshot.audience': 'candidate'}
            if audience == 'candidate'
            else {
                '$or': [
                    {'plan_snapshot.audience': 'recruiter'},
                    {'plan_snapshot.audience': {'$exists': False}},
                ]
            }
        )

        subscriptions = list(subscriptions_collection.find({'status': 'active', '$and': [audience_filter]}).sort('created_at', -1))
        plan_map = {}
        for subscription in subscriptions:
            owner_id = str(subscription.get('employer_id'))
            if owner_id in plan_map:
                continue
            snapshot = subscription.get('plan_snapshot') or {}
            plan_map[owner_id] = snapshot.get('name') or snapshot.get('slug') or 'Free'
        return plan_map

    def _line_category_summary(self, key, title, lines):
        total_cost = sum(float(line.get('cost_inr', 0) or 0.0) for line in lines)
        total_calculated_cost = sum(float(line.get('calculated_cost_inr', line.get('cost_inr', 0)) or 0.0) for line in lines)
        actual_values = [line.get('actual_cost_inr') for line in lines if line.get('actual_cost_inr') is not None]
        total_actual_cost = sum(float(value or 0.0) for value in actual_values)
        count = len(lines)
        return {
            'key': key,
            'title': title,
            'count': count,
            'total_cost_inr': self._round_money(total_cost),
            'total_calculated_cost_inr': self._round_money(total_calculated_cost),
            'total_actual_cost_inr': self._round_money(total_actual_cost) if actual_values else None,
            'avg_cost_inr': self._round_money(self._safe_div(total_cost, count)),
            'avg_calculated_cost_inr': self._round_money(self._safe_div(total_calculated_cost, count)),
            'avg_actual_cost_inr': self._round_money(self._safe_div(total_actual_cost, count)) if actual_values else None,
            'lines': sorted(lines, key=lambda item: item.get('timestamp') or '', reverse=True),
        }

    def _usage_events_collection(self):
        return self.users_collection.database.get_collection('ai_usage_events')

    def _get_usage_events(self, actor_type, actor_id=None, action_types=None, period_start=None, period_end=None):
        events_collection = self._usage_events_collection()
        if events_collection is None:
            return []

        query = {
            'actor_type': actor_type,
        }
        if actor_id is not None:
            query['actor_id'] = str(actor_id)

        if action_types:
            query['action_type'] = {'$in': action_types}

        if period_start and period_end:
            query['occurred_at'] = {'$gte': period_start, '$lte': period_end}

        return list(events_collection.find(query))

    def _search_and_paginate_lines(self, lines, search='', page=1, limit=50):
        normalized_search = (search or '').strip().lower()
        if normalized_search:
            def _matches(line):
                haystack = ' '.join([
                    str(line.get('title') or ''),
                    str(line.get('model') or ''),
                    str((line.get('source') or {}).get('label') or ''),
                    str((line.get('source') or {}).get('type') or ''),
                    str(line.get('formula') or ''),
                ]).lower()
                return normalized_search in haystack

            filtered = [line for line in lines if _matches(line)]
        else:
            filtered = lines

        safe_page = max(1, int(page or 1))
        safe_limit = max(1, min(500, int(limit or 50)))
        total = len(filtered)
        start_index = (safe_page - 1) * safe_limit
        end_index = start_index + safe_limit
        paged = filtered[start_index:end_index]

        return {
            'items': paged,
            'pagination': {
                'page': safe_page,
                'limit': safe_limit,
                'total': total,
                'total_pages': (total + safe_limit - 1) // safe_limit if total > 0 else 0,
                'has_next': end_index < total,
                'has_prev': safe_page > 1,
            }
        }

    def get_candidate_usage_summary(self, current_user, period='month', start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            assumptions = self._action_assumptions()

            candidate_docs = list(self.users_collection.find({'user_type': 'candidate'}, {'name': 1, 'email': 1}))
            candidate_map = {str(doc['_id']): doc for doc in candidate_docs}
            summary_map = {
                candidate_id: {
                    'candidate_id': candidate_id,
                    'name': doc.get('name', 'Unknown Candidate'),
                    'email': doc.get('email', ''),
                    'practice_interview_count': 0,
                    'practice_interview_total_cost_inr': 0.0,
                    'practice_interview_actual_total_cost_inr': 0.0,
                    'practice_interview_evaluation_count': 0,
                    'practice_interview_evaluation_total_cost_inr': 0.0,
                    'practice_interview_evaluation_actual_total_cost_inr': 0.0,
                }
                for candidate_id, doc in candidate_map.items()
            }

            candidate_ids = list(candidate_map.keys())
            practice_query = self._build_date_range_query(
                {'is_practice': True, 'user_id': {'$in': candidate_ids}},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            practice_sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []

            for session in practice_sessions:
                candidate_id = self._find_matching_user_id(candidate_map, session.get('user_id'))
                if not candidate_id:
                    continue

                practice_line = self._build_interview_cost_line(
                    session,
                    'practice_interview',
                    'Practice Interview Cost',
                    assumptions['ai_interview'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'practice_session',
                        'id': session.get('session_id') or str(session.get('_id') or ''),
                        'label': session.get('role') or 'Practice Session',
                    }
                )
                summary_map[candidate_id]['practice_interview_count'] += 1
                summary_map[candidate_id]['practice_interview_total_cost_inr'] += float(practice_line['cost_inr'])
                summary_map[candidate_id]['practice_interview_actual_total_cost_inr'] += float(practice_line.get('actual_cost_inr') or 0.0)

                session_with_eval_context = self._with_evaluation_context(session)
                evaluation_line = self._build_token_cost_line(
                    session_with_eval_context,
                    'practice_interview_evaluation',
                    'Practice Interview Evaluation Cost',
                    assumptions['evaluation'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'practice_session',
                        'id': session.get('session_id') or str(session.get('_id') or ''),
                        'label': session.get('role') or 'Practice Session',
                    }
                )
                summary_map[candidate_id]['practice_interview_evaluation_count'] += 1
                summary_map[candidate_id]['practice_interview_evaluation_total_cost_inr'] += float(evaluation_line['cost_inr'])
                summary_map[candidate_id]['practice_interview_evaluation_actual_total_cost_inr'] += float(evaluation_line.get('actual_cost_inr') or 0.0)

            incoming_map = self._user_succeeded_incoming_map(period_start, period_end, audience='candidate')
            plan_map = self._active_plan_name_map(audience='candidate')

            rows = []
            for candidate_id, row in summary_map.items():
                practice_total = float(row['practice_interview_total_cost_inr'])
                eval_total = float(row['practice_interview_evaluation_total_cost_inr'])
                practice_actual_total = float(row['practice_interview_actual_total_cost_inr'])
                eval_actual_total = float(row['practice_interview_evaluation_actual_total_cost_inr'])
                practice_count = int(row['practice_interview_count'])
                eval_count = int(row['practice_interview_evaluation_count'])
                total_actions = practice_count + eval_count
                total_cost = practice_total + eval_total
                total_actual_cost = practice_actual_total + eval_actual_total

                rows.append({
                    'candidate_id': candidate_id,
                    'name': row['name'],
                    'email': row['email'],
                    'enrolled_plan': plan_map.get(candidate_id, 'Free'),
                    'incoming_amount_inr': incoming_map.get(candidate_id, 0.0),
                    'practice_interview_count': practice_count,
                    'practice_interview_total_cost_inr': self._round_money(practice_total),
                    'practice_interview_actual_total_cost_inr': self._round_money(practice_actual_total),
                    'practice_interview_avg_cost_inr': self._round_money(self._safe_div(practice_total, practice_count)),
                    'practice_interview_evaluation_count': eval_count,
                    'practice_interview_evaluation_total_cost_inr': self._round_money(eval_total),
                    'practice_interview_evaluation_actual_total_cost_inr': self._round_money(eval_actual_total),
                    'practice_interview_evaluation_avg_cost_inr': self._round_money(self._safe_div(eval_total, eval_count)),
                    'total_actions': total_actions,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if total_actual_cost > 0 else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_actions)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_actions)) if total_actual_cost > 0 else None,
                })

            rows.sort(key=lambda item: (-item['total_usage_cost_inr'], item['name']))

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_candidates': len(rows),
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting candidate usage summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate usage summary'}, 500

    def get_candidate_usage_lines(self, current_user, candidate_id, period='month', start_date=None, end_date=None, page=1, limit=50, search=''):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                candidate_doc = self.users_collection.find_one({'_id': ObjectId(candidate_id), 'user_type': 'candidate'}, {'name': 1, 'email': 1})
            except Exception:
                candidate_doc = self.users_collection.find_one({'_id': candidate_id, 'user_type': 'candidate'}, {'name': 1, 'email': 1})

            if not candidate_doc:
                return {'error': 'Candidate not found'}, 404

            assumptions = self._action_assumptions()

            candidate_id_str = str(candidate_doc.get('_id'))
            candidate_id_variants = [candidate_id_str]
            if ObjectId.is_valid(candidate_id_str):
                candidate_id_variants.append(ObjectId(candidate_id_str))

            practice_query = self._build_date_range_query(
                {'is_practice': True, 'user_id': {'$in': candidate_id_variants}},
                ['created_at', 'updated_at', 'completed_at'],
                period_start,
                period_end,
            )
            sessions = list(self.practice_sessions_collection.find(practice_query)) if self.practice_sessions_collection is not None else []

            practice_lines = []
            practice_eval_lines = []

            for session in sessions:
                practice_lines.append(
                    self._build_interview_cost_line(
                        session,
                        'practice_interview',
                        'Practice Interview Cost',
                        assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )
                session_with_eval_context = self._with_evaluation_context(session)
                practice_eval_lines.append(
                    self._build_token_cost_line(
                        session_with_eval_context,
                        'practice_interview_evaluation',
                        'Practice Interview Evaluation Cost',
                        assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'practice_session',
                            'id': session.get('session_id') or str(session.get('_id') or ''),
                            'label': session.get('role') or 'Practice Session',
                        }
                    )
                )

            raw_categories = [
                self._line_category_summary('practice_interview', 'Practice Interview Cost', practice_lines),
                self._line_category_summary('practice_interview_evaluation', 'Practice Interview Evaluation Cost', practice_eval_lines),
            ]

            categories = []
            for category in raw_categories:
                paged = self._search_and_paginate_lines(category['lines'], search=search, page=page, limit=limit)
                categories.append({
                    **category,
                    'lines': paged['items'],
                    'line_pagination': paged['pagination'],
                })

            total_count = sum(category['count'] for category in categories)
            total_cost = sum(float(category['total_cost_inr']) for category in categories)
            actual_cost_values = [category.get('total_actual_cost_inr') for category in categories if category.get('total_actual_cost_inr') is not None]
            total_actual_cost = sum(float(value or 0.0) for value in actual_cost_values)
            actual_cost_values = [category.get('total_actual_cost_inr') for category in categories if category.get('total_actual_cost_inr') is not None]
            total_actual_cost = sum(float(value or 0.0) for value in actual_cost_values)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'candidate': {
                    'id': str(candidate_doc.get('_id')),
                    'name': candidate_doc.get('name', 'Unknown Candidate'),
                    'email': candidate_doc.get('email', ''),
                },
                'categories': categories,
                'summary': {
                    'total_actions': total_count,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if actual_cost_values else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_count)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_count)) if actual_cost_values else None,
                }
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting candidate usage lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate usage lines'}, 500

    def _recruiter_id_from_job(self, job_doc):
        return str(job_doc.get('recruiter_id') or job_doc.get('created_by') or '')

    def _recruiter_id_from_application(self, application_doc):
        recruiter_id = application_doc.get('recruiter_id')
        if recruiter_id:
            return str(recruiter_id)

        job_id = application_doc.get('job_id')
        if not job_id:
            return ''

        job_doc = None
        try:
            job_doc = self.jobs_collection.find_one({'_id': ObjectId(job_id)}, {'recruiter_id': 1, 'created_by': 1})
        except Exception:
            job_doc = self.jobs_collection.find_one({'_id': job_id}, {'recruiter_id': 1, 'created_by': 1})

        if not job_doc:
            return ''

        return self._recruiter_id_from_job(job_doc)

    def get_recruiter_usage_summary(self, current_user, period='month', start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            assumptions = self._action_assumptions()

            recruiter_docs = list(self.users_collection.find({'user_type': 'recruiter'}, {'name': 1, 'email': 1}))
            recruiter_map = {str(doc['_id']): doc for doc in recruiter_docs}
            recruiter_ids = list(recruiter_map.keys())

            summary_map = {
                recruiter_id: {
                    'recruiter_id': recruiter_id,
                    'name': doc.get('name', 'Unknown Recruiter'),
                    'email': doc.get('email', ''),
                    'real_interview_count': 0,
                    'real_interview_total_cost_inr': 0.0,
                    'real_interview_actual_total_cost_inr': 0.0,
                    'real_interview_evaluation_count': 0,
                    'real_interview_evaluation_total_cost_inr': 0.0,
                    'real_interview_evaluation_actual_total_cost_inr': 0.0,
                    'ai_jd_generation_count': 0,
                    'ai_jd_generation_total_cost_inr': 0.0,
                    'ai_jd_generation_actual_total_cost_inr': 0.0,
                    'cv_score_count': 0,
                    'cv_score_total_cost_inr': 0.0,
                    'cv_score_actual_total_cost_inr': 0.0,
                }
                for recruiter_id, doc in recruiter_map.items()
            }

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )

            if jd_events:
                for event in jd_events:
                    recruiter_id = self._find_matching_user_id(recruiter_map, event.get('actor_id'))
                    if not recruiter_id:
                        continue
                    jd_line = self._build_token_cost_line(
                        event,
                        'ai_jd_generation',
                        'Total AI JD Generation Cost',
                        assumptions['ai_jd_generation'],
                        ['occurred_at', 'created_at'],
                        source_meta=event.get('source') or {},
                    )
                    summary_map[recruiter_id]['ai_jd_generation_count'] += 1
                    summary_map[recruiter_id]['ai_jd_generation_total_cost_inr'] += float(jd_line['cost_inr'])
                    summary_map[recruiter_id]['ai_jd_generation_actual_total_cost_inr'] += float(jd_line.get('actual_cost_inr') or 0.0)
            else:
                jobs_query = self._build_date_range_query(
                    {
                        '$or': [
                            {'created_by': {'$in': recruiter_ids}},
                            {'recruiter_id': {'$in': recruiter_ids}},
                        ]
                    },
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_job(job))
                    if not recruiter_id:
                        continue
                    jd_line = self._build_token_cost_line(
                        job,
                        'ai_jd_generation',
                        'Total AI JD Generation Cost',
                        assumptions['ai_jd_generation'],
                        ['updated_at', 'created_at'],
                        source_meta={
                            'type': 'job',
                            'id': str(job.get('_id') or ''),
                            'label': job.get('title') or 'Job',
                        }
                    )
                    summary_map[recruiter_id]['ai_jd_generation_count'] += 1
                    summary_map[recruiter_id]['ai_jd_generation_total_cost_inr'] += float(jd_line['cost_inr'])
                    summary_map[recruiter_id]['ai_jd_generation_actual_total_cost_inr'] += float(jd_line.get('actual_cost_inr') or 0.0)

            cv_query = self._build_date_range_query(
                {'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_application(app))
                if not recruiter_id:
                    continue
                cv_line = self._build_token_cost_line(
                    app,
                    'cv_scoring',
                    'Total CV Score Calculation Cost',
                    assumptions['cv_scoring'],
                    ['cv_score_calculated_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'application',
                        'id': str(app.get('_id') or ''),
                        'label': app.get('job_title') or 'Application',
                    }
                )
                summary_map[recruiter_id]['cv_score_count'] += 1
                summary_map[recruiter_id]['cv_score_total_cost_inr'] += float(cv_line['cost_inr'])
                summary_map[recruiter_id]['cv_score_actual_total_cost_inr'] += float(cv_line.get('actual_cost_inr') or 0.0)

            base_app_query = {
                'recruiter_id': {'$in': recruiter_ids}
            }
            interview_query = self._build_date_range_query(
                {
                    **base_app_query,
                    'is_visible': True,
                    'status': {'$in': ['interviewed', 'selected', 'rejected']},
                },
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])
            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )
                recruiter_id = self._find_matching_user_id(recruiter_map, self._recruiter_id_from_application(app))
                if not recruiter_id:
                    continue
                interview_line = self._build_interview_cost_line(
                    app_with_context,
                    'ai_interview',
                    'Total Real Interview Cost',
                    assumptions['ai_interview'],
                    ['completed_at', 'updated_at', 'created_at'],
                    source_meta={
                        'type': 'application',
                        'id': str(app.get('_id') or ''),
                        'label': app.get('job_title') or 'Application',
                    }
                )
                summary_map[recruiter_id]['real_interview_count'] += 1
                summary_map[recruiter_id]['real_interview_total_cost_inr'] += float(interview_line['cost_inr'])
                summary_map[recruiter_id]['real_interview_actual_total_cost_inr'] += float(interview_line.get('actual_cost_inr') or 0.0)

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    eval_line = self._build_token_cost_line(
                        app_with_eval_context,
                        'ai_interview_evaluation',
                        'Total Real Interview Evaluation Cost',
                        assumptions['evaluation'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                    summary_map[recruiter_id]['real_interview_evaluation_count'] += 1
                    summary_map[recruiter_id]['real_interview_evaluation_total_cost_inr'] += float(eval_line['cost_inr'])
                    summary_map[recruiter_id]['real_interview_evaluation_actual_total_cost_inr'] += float(eval_line.get('actual_cost_inr') or 0.0)

            incoming_map = self._user_succeeded_incoming_map(period_start, period_end, audience='recruiter')
            plan_map = self._active_plan_name_map(audience='recruiter')

            rows = []
            for recruiter_id, row in summary_map.items():
                interview_total = float(row['real_interview_total_cost_inr'])
                interview_eval_total = float(row['real_interview_evaluation_total_cost_inr'])
                jd_total = float(row['ai_jd_generation_total_cost_inr'])
                cv_total = float(row['cv_score_total_cost_inr'])
                interview_actual_total = float(row['real_interview_actual_total_cost_inr'])
                interview_eval_actual_total = float(row['real_interview_evaluation_actual_total_cost_inr'])
                jd_actual_total = float(row['ai_jd_generation_actual_total_cost_inr'])
                cv_actual_total = float(row['cv_score_actual_total_cost_inr'])
                interview_count = int(row['real_interview_count'])
                interview_eval_count = int(row['real_interview_evaluation_count'])
                jd_count = int(row['ai_jd_generation_count'])
                cv_count = int(row['cv_score_count'])

                total_actions = interview_count + interview_eval_count + jd_count + cv_count
                total_cost = interview_total + interview_eval_total + jd_total + cv_total
                total_actual_cost = interview_actual_total + interview_eval_actual_total + jd_actual_total + cv_actual_total

                rows.append({
                    'recruiter_id': recruiter_id,
                    'name': row['name'],
                    'email': row['email'],
                    'enrolled_plan': plan_map.get(recruiter_id, 'Free'),
                    'incoming_amount_inr': incoming_map.get(recruiter_id, 0.0),
                    'real_interview_count': interview_count,
                    'real_interview_total_cost_inr': self._round_money(interview_total),
                    'real_interview_actual_total_cost_inr': self._round_money(interview_actual_total),
                    'real_interview_avg_cost_inr': self._round_money(self._safe_div(interview_total, interview_count)),
                    'real_interview_evaluation_count': interview_eval_count,
                    'real_interview_evaluation_total_cost_inr': self._round_money(interview_eval_total),
                    'real_interview_evaluation_actual_total_cost_inr': self._round_money(interview_eval_actual_total),
                    'real_interview_evaluation_avg_cost_inr': self._round_money(self._safe_div(interview_eval_total, interview_eval_count)),
                    'ai_jd_generation_count': jd_count,
                    'ai_jd_generation_total_cost_inr': self._round_money(jd_total),
                    'ai_jd_generation_actual_total_cost_inr': self._round_money(jd_actual_total),
                    'ai_jd_generation_avg_cost_inr': self._round_money(self._safe_div(jd_total, jd_count)),
                    'cv_score_count': cv_count,
                    'cv_score_total_cost_inr': self._round_money(cv_total),
                    'cv_score_actual_total_cost_inr': self._round_money(cv_actual_total),
                    'cv_score_avg_cost_inr': self._round_money(self._safe_div(cv_total, cv_count)),
                    'total_actions': total_actions,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if total_actual_cost > 0 else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_actions)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_actions)) if total_actual_cost > 0 else None,
                })

            rows.sort(key=lambda item: (-item['total_usage_cost_inr'], item['name']))

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_recruiters': len(rows),
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting recruiter usage summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter usage summary'}, 500

    def get_recruiter_usage_lines(self, current_user, recruiter_id, period='month', start_date=None, end_date=None, page=1, limit=50, search=''):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window(period, start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                recruiter_doc = self.users_collection.find_one({'_id': ObjectId(recruiter_id), 'user_type': 'recruiter'}, {'name': 1, 'email': 1})
            except Exception:
                recruiter_doc = self.users_collection.find_one({'_id': recruiter_id, 'user_type': 'recruiter'}, {'name': 1, 'email': 1})

            if not recruiter_doc:
                return {'error': 'Recruiter not found'}, 404

            recruiter_id_str = str(recruiter_doc.get('_id'))
            assumptions = self._action_assumptions()

            jd_lines = []
            cv_lines = []
            interview_lines = []
            interview_eval_lines = []

            recruiter_id_variants = [recruiter_id_str]
            if ObjectId.is_valid(recruiter_id_str):
                recruiter_id_variants.append(ObjectId(recruiter_id_str))

            jd_events = self._get_usage_events(
                actor_type='recruiter',
                actor_id=recruiter_id_str,
                action_types=['ai_jd_generation'],
                period_start=period_start,
                period_end=period_end,
            )

            if jd_events:
                for event in jd_events:
                    jd_lines.append(
                        self._build_token_cost_line(
                            event,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            assumptions['ai_jd_generation'],
                            ['occurred_at', 'created_at'],
                            source_meta=event.get('source') or {},
                        )
                    )
            else:
                jobs_query = self._build_date_range_query(
                    {
                        '$or': [
                            {'created_by': {'$in': recruiter_id_variants}},
                            {'recruiter_id': {'$in': recruiter_id_variants}},
                        ]
                    },
                    ['created_at', 'updated_at'],
                    period_start,
                    period_end,
                )
                jobs = list(self.jobs_collection.find(jobs_query)) if self.jobs_collection is not None else []
                for job in jobs:
                    jd_lines.append(
                        self._build_token_cost_line(
                            job,
                            'ai_jd_generation',
                            'Total AI JD Generation Cost',
                            assumptions['ai_jd_generation'],
                            ['updated_at', 'created_at'],
                            source_meta={
                                'type': 'job',
                                'id': str(job.get('_id') or ''),
                                'label': job.get('title') or 'Job',
                            }
                        )
                    )

            base_app_query = {
                '$or': [
                    {'recruiter_id': recruiter_id_str},
                    {'recruiter_id': ObjectId(recruiter_id_str)} if ObjectId.is_valid(recruiter_id_str) else {'recruiter_id': recruiter_id_str}
                ]
            }

            cv_query = self._build_date_range_query(
                {**base_app_query, 'cv_score': {'$exists': True, '$ne': None}},
                ['cv_score_calculated_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            cv_apps = list(self.applications_collection.find(cv_query)) if self.applications_collection is not None else []
            for app in cv_apps:
                cv_lines.append(
                    self._build_token_cost_line(
                        app,
                        'cv_scoring',
                        'Total CV Score Calculation Cost',
                        assumptions['cv_scoring'],
                        ['cv_score_calculated_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

            interview_query = self._build_date_range_query(
                {
                    **base_app_query,
                    'is_visible': True,
                    'status': {'$in': ['interviewed', 'selected', 'rejected']},
                },
                ['completed_at', 'updated_at', 'created_at'],
                period_start,
                period_end,
            )
            interview_apps = list(self.applications_collection.find(interview_query)) if self.applications_collection is not None else []
            interview_reports = self._latest_interview_reports_by_application([app.get('_id') for app in interview_apps])
            for app in interview_apps:
                app_with_context = self._merge_application_interview_context(
                    app,
                    interview_reports.get(str(app.get('_id') or ''))
                )
                interview_lines.append(
                    self._build_interview_cost_line(
                        app_with_context,
                        'ai_interview',
                        'Total Real Interview Cost',
                        assumptions['ai_interview'],
                        ['completed_at', 'updated_at', 'created_at'],
                        source_meta={
                            'type': 'application',
                            'id': str(app.get('_id') or ''),
                            'label': app.get('job_title') or 'Application',
                        }
                    )
                )

                if self._has_interview_evaluation(app_with_context):
                    app_with_eval_context = self._with_evaluation_context(app_with_context)
                    interview_eval_lines.append(
                        self._build_token_cost_line(
                            app_with_eval_context,
                            'ai_interview_evaluation',
                            'Total Real Interview Evaluation Cost',
                            assumptions['evaluation'],
                            ['completed_at', 'updated_at', 'created_at'],
                            source_meta={
                                'type': 'application',
                                'id': str(app.get('_id') or ''),
                                'label': app.get('job_title') or 'Application',
                            }
                        )
                    )

            raw_categories = [
                self._line_category_summary('ai_interview', 'Total Real Interview Cost', interview_lines),
                self._line_category_summary('ai_interview_evaluation', 'Total Real Interview Evaluation Cost', interview_eval_lines),
                self._line_category_summary('ai_jd_generation', 'Total AI JD Generation Cost', jd_lines),
                self._line_category_summary('cv_scoring', 'Total CV Score Calculation Cost', cv_lines),
            ]

            categories = []
            for category in raw_categories:
                paged = self._search_and_paginate_lines(category['lines'], search=search, page=page, limit=limit)
                categories.append({
                    **category,
                    'lines': paged['items'],
                    'line_pagination': paged['pagination'],
                })

            total_count = sum(category['count'] for category in categories)
            total_cost = sum(float(category['total_cost_inr']) for category in categories)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'recruiter': {
                    'id': recruiter_id_str,
                    'name': recruiter_doc.get('name', 'Unknown Recruiter'),
                    'email': recruiter_doc.get('email', ''),
                },
                'categories': categories,
                'summary': {
                    'total_actions': total_count,
                    'total_usage_cost_inr': self._round_money(total_cost),
                    'total_actual_usage_cost_inr': self._round_money(total_actual_cost) if actual_cost_values else None,
                    'avg_usage_cost_inr': self._round_money(self._safe_div(total_cost, total_count)),
                    'avg_actual_usage_cost_inr': self._round_money(self._safe_div(total_actual_cost, total_count)) if actual_cost_values else None,
                }
            }, 200

        except Exception as e:
            import traceback
            print(f"Error getting recruiter usage lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter usage lines'}, 500

    def _get_wallet_service(self):
        if getattr(self, '_wallet_service', None) is None:
            self._wallet_service = WalletService(self.users_collection.database)
        return self._wallet_service

    def _credit_description(self, transaction):
        metadata = transaction.get('metadata') or {}
        parts = []
        plan_name = metadata.get('plan_name') or metadata.get('plan_slug') or metadata.get('name') or metadata.get('slug')
        if plan_name:
            parts.append(str(plan_name))
        reason = metadata.get('reason') or metadata.get('description')
        if reason:
            parts.append(str(reason))

        reference_type = transaction.get('reference_type')
        reference_id = transaction.get('reference_id')
        if not parts and (reference_type or reference_id):
            parts.append(f"{reference_type or 'reference'}:{reference_id or ''}".strip(':'))

        if not parts:
            return str(transaction.get('transaction_type') or 'Credit transaction')

        return ' - '.join(parts)

    def _format_tx_timestamp(self, value):
        if isinstance(value, datetime.datetime):
            return value.strftime("%Y-%m-%d %H:%M")
        text = str(value or "")
        try:
            parsed = datetime.datetime.fromisoformat(text.replace("Z", "+00:00"))
            return parsed.strftime("%Y-%m-%d %H:%M")
        except Exception:
            return text

    def _is_proctored_tx(self, tx):
        metadata = tx.get("metadata") or {}
        if "proctoring_enabled" in metadata:
            return bool(metadata.get("proctoring_enabled"))
        proctoring_config = metadata.get("proctoring_config")
        if isinstance(proctoring_config, dict):
            return any(bool(value) for value in proctoring_config.values())
        return False

    def _credit_activity_label(self, tx):
        tx_type = str(tx.get("transaction_type") or "")
        if tx_type == "practice_interview":
            return (
                "Practice Interview (Proctored)"
                if self._is_proctored_tx(tx)
                else "Practice Interview (Non-Proctored)"
            )
        if tx_type == "real_interview_recruiter":
            return (
                "Real Interview (Proctored)"
                if self._is_proctored_tx(tx)
                else "Real Interview (Non-Proctored)"
            )
        if tx_type == "ai_jd_generation":
            return "AI JD Generation"
        if tx_type == "migration_recharge":
            return "Migration Recharge"
        return str(tx_type or "activity").replace("_", " ").title()

    def _format_activity_row(self, tx):
        delta = int(tx.get("delta_credits", 0) or 0)
        credits_deducted = abs(delta) if delta < 0 else 0
        return {
            "id": tx.get("id"),
            "activity_type": self._credit_activity_label(tx),
            "transaction_type": tx.get("transaction_type"),
            "credits_deducted": credits_deducted,
            "delta_credits": delta,
            "balance_after": int(tx.get("balance_after", 0) or 0),
            "remaining_balance": int(tx.get("balance_after", 0) or 0),
            "timestamp": self._format_tx_timestamp(tx.get("created_at")),
        }

    def _credit_summary_rows(self, audience, start_dt, end_dt):
        wallet_service = self._get_wallet_service()
        transaction_collection = wallet_service.transaction_collection
        recharge_types = list(wallet_service.RECHARGE_TRANSACTION_TYPES)

        user_docs = list(self.users_collection.find({'user_type': audience}, {'name': 1, 'email': 1}))
        rows = []

        for user in user_docs:
            owner_id = str(user.get('_id'))
            wallet_summary = wallet_service.get_wallet_summary(owner_id, audience)
            current_balance = int(wallet_summary.get('credits_balance', 0) or 0)

            last_recharge_tx = transaction_collection.find_one(
                {
                    'owner_id': owner_id,
                    'audience': audience,
                    'transaction_type': {'$in': recharge_types},
                },
                sort=[('created_at', -1)],
            )
            last_recharge_date = self._safe_iso(last_recharge_tx.get('created_at')) if last_recharge_tx else None
            last_recharge_meta = last_recharge_tx.get('metadata') if last_recharge_tx else {}
            last_recharge_plan = None
            if last_recharge_meta:
                last_recharge_plan = last_recharge_meta.get('plan_name') or last_recharge_meta.get('plan_slug')

            usage_query = {
                'owner_id': owner_id,
                'audience': audience,
                'created_at': {'$gte': start_dt, '$lte': end_dt},
                'delta_credits': {'$lt': 0},
            }
            usage_docs = transaction_collection.find(usage_query, {'delta_credits': 1})
            total_usage = sum(abs(int(doc.get('delta_credits', 0) or 0)) for doc in usage_docs)

            rows.append({
                f'{audience}_id': owner_id,
                'name': user.get('name', ''),
                'email': user.get('email', ''),
                'current_balance_inr': float(current_balance),
                'last_recharge_date': last_recharge_date,
                'last_recharge_plan': last_recharge_plan,
                'total_usage_inr': float(total_usage),
            })

        rows.sort(key=lambda item: (-item.get('current_balance_inr', 0), item.get('name') or ''))
        return rows

    def _credit_lines_for_owner(self, owner_id, audience, start_dt, end_dt):
        wallet_service = self._get_wallet_service()
        tx_list = wallet_service.get_transactions(
            owner_id,
            audience,
            limit=100,
            kind="deductions",
        )

        recent_activity = [
            self._format_activity_row(tx)
            for tx in tx_list
            if int(tx.get("delta_credits", 0) or 0) < 0
        ][:50]

        total_amount = sum(int(row.get("credits_deducted", 0) or 0) for row in recent_activity)

        return [
            {
                "key": "deductions",
                "title": "Recent Credit Activity",
                "count": len(recent_activity),
                "total_amount_inr": self._round_money(total_amount),
                "lines": [
                    {
                        "id": row.get("id") or "",
                        "timestamp": row.get("timestamp"),
                        "activity_type": row.get("activity_type"),
                        "credits_deducted": row.get("credits_deducted"),
                        "remaining_balance": row.get("remaining_balance"),
                        "balance_after": row.get("balance_after"),
                        "amount_inr": row.get("credits_deducted"),
                    }
                    for row in recent_activity
                ],
            }
        ]

    def get_candidate_credit_summary(self, current_user, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            rows = self._credit_summary_rows('candidate', period_start, period_end)
            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_candidates': len(rows),
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting candidate credit summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate credit summary'}, 500

    def get_candidate_credit_lines(self, current_user, candidate_id, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                candidate_doc = self.users_collection.find_one({'_id': ObjectId(candidate_id), 'user_type': 'candidate'}, {'name': 1, 'email': 1})
            except Exception:
                candidate_doc = self.users_collection.find_one({'_id': candidate_id, 'user_type': 'candidate'}, {'name': 1, 'email': 1})

            if not candidate_doc:
                return {'error': 'Candidate not found'}, 404

            candidate_id_str = str(candidate_doc.get('_id'))
            categories = self._credit_lines_for_owner(candidate_id_str, 'candidate', period_start, period_end)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'candidate': {
                    'id': candidate_id_str,
                    'name': candidate_doc.get('name', 'Unknown Candidate'),
                    'email': candidate_doc.get('email', ''),
                },
                'categories': categories,
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting candidate credit lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get candidate credit lines'}, 500

    def get_recruiter_credit_summary(self, current_user, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            rows = self._credit_summary_rows('recruiter', period_start, period_end)
            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'rows': rows,
                'total_recruiters': len(rows),
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting recruiter credit summary: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter credit summary'}, 500

    def get_recruiter_credit_lines(self, current_user, recruiter_id, start_date=None, end_date=None):
        try:
            period_mode, period_start, period_end, error_response, error_status = self._resolve_timeline_window('month', start_date, end_date)
            if error_response:
                return error_response, error_status

            try:
                recruiter_doc = self.users_collection.find_one({'_id': ObjectId(recruiter_id), 'user_type': 'recruiter'}, {'name': 1, 'email': 1})
            except Exception:
                recruiter_doc = self.users_collection.find_one({'_id': recruiter_id, 'user_type': 'recruiter'}, {'name': 1, 'email': 1})

            if not recruiter_doc:
                return {'error': 'Recruiter not found'}, 404

            recruiter_id_str = str(recruiter_doc.get('_id'))
            categories = self._credit_lines_for_owner(recruiter_id_str, 'recruiter', period_start, period_end)

            return {
                'timeline': {
                    'period_mode': period_mode,
                    'start_date': self._safe_iso(period_start),
                    'end_date': self._safe_iso(period_end),
                    'days': max(1, (period_end - period_start).days),
                },
                'recruiter': {
                    'id': recruiter_id_str,
                    'name': recruiter_doc.get('name', 'Unknown Recruiter'),
                    'email': recruiter_doc.get('email', ''),
                },
                'categories': categories,
            }, 200
        except Exception as e:
            import traceback
            print(f"Error getting recruiter credit lines: {str(e)}")
            print(traceback.format_exc())
            return {'error': 'Failed to get recruiter credit lines'}, 500

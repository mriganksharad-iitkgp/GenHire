"""Candidate/user administration: listing, details, permissions, CV, deletion."""

import datetime
from models.user import AVAILABLE_PERMISSIONS


class UserAdmin:
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

    def get_user_details(self, current_user, user_id):
        """Get detailed information about a specific user"""
        try:
            user = self.user_repo.find_one_by_id(user_id)

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

    def update_user_permissions(self, current_user, user_id, permissions):
        """Update user permissions (and promote to admin if granting admin-level permissions)"""
        try:
            user = self.user_repo.find_one_by_id(user_id)

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
            self.user_repo.update_by_id(user_id, {"$set": update_data}
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
            user = self.user_repo.find_one_by_id(user_id)

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

            self.user_repo.update_by_id(user_id, {"$set": update_data}
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
            user = self.user_repo.find_one_by_id(user_id)

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
            self.user_repo.delete_by_id(user_id)

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
            candidate = self.user_repo.find_one_by_id(candidate_id)

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
                        job = self.job_repo.find_one_by_id(app["job_id"])
                    if app.get("recruiter_id"):
                        recruiter = self.user_repo.find_one_by_id(app["recruiter_id"])
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
                "screening_cleared": sum(
                    1
                    for app in applications
                    if app["status"] in ("screening_cleared", "selected")
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

    def update_candidate(self, current_user, candidate_id, data):
        """Update candidate details"""
        try:
            candidate = self.user_repo.find_one_by_id(candidate_id)

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

            self.user_repo.update_by_id(candidate_id, {"$set": update_data}
            )

            return {
                "message": f'Candidate {candidate.get("name")} updated successfully',
                "candidate_id": candidate_id,
            }, 200
        except Exception as e:
            print(f"Error updating candidate: {str(e)}")
            return {"error": "Failed to update candidate"}, 500

    def get_candidate_cv(self, current_user, candidate_id):
        """Get candidate CV details"""
        try:
            candidate = self.user_repo.find_one_by_id(candidate_id)

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
            candidate = self.user_repo.find_one_by_id(candidate_id)

            if not candidate:
                return {"error": "Candidate not found"}, 404

            if candidate.get("user_type") != "candidate":
                return {"error": "User is not a candidate"}, 400

            # Clear CV data
            self.user_repo.update_by_id(candidate_id,
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

    def get_candidate_practice_history(self, current_user, candidate_id):
        """Get practice interview history for a specific candidate"""
        try:
            # Verify candidate exists
            candidate = self.user_repo.find_one_by_id(candidate_id)
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

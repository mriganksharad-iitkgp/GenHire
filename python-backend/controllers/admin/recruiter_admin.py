"""Recruiter administration: pending queue, verification, details, updates."""

import datetime
from bson import ObjectId


class RecruiterAdmin:
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
                        "rejection_reason": None,
                    }
                },
            )

            # Send approval email (non-blocking — failure doesn't fail the request)
            try:
                self.email_service.send_recruiter_approved_email(
                    to_email=recruiter.get("email", ""),
                    recruiter_name=recruiter.get("name", ""),
                    company_name=recruiter.get("company_name", ""),
                )
            except Exception as email_err:
                print(f"[admin] approval email failed for {recruiter_id}: {email_err}")

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

            stored_reason = reason or "Account verification rejected by admin"

            # Update to unverified status with rejection reason
            self.users_collection.update_one(
                {"_id": ObjectId(recruiter_id)},
                {
                    "$set": {
                        "is_verified": False,
                        "rejection_reason": stored_reason,
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )

            # Send rejection email (non-blocking — failure doesn't fail the request)
            try:
                self.email_service.send_recruiter_rejected_email(
                    to_email=recruiter.get("email", ""),
                    recruiter_name=recruiter.get("name", ""),
                    company_name=recruiter.get("company_name", ""),
                    rejection_reason=stored_reason,
                )
            except Exception as email_err:
                print(f"[admin] rejection email failed for {recruiter_id}: {email_err}")

            return {
                "message": f'Recruiter {recruiter.get("name")} has been rejected',
                "recruiter_id": recruiter_id,
            }, 200
        except Exception as e:
            print(f"Error rejecting recruiter: {str(e)}")
            return {"error": "Failed to reject recruiter"}, 500

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
                    1
                    for app in job_applications
                    if app.get("status") in ("screening_cleared", "selected")
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
                        "screening_cleared": selected_count,
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
                "total_screening_cleared": total_selected,
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

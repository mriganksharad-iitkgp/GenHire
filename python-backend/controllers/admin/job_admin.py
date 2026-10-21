"""Job moderation: listing, details, updates, deletion."""

import datetime


class JobAdmin:
    def get_job_details(self, current_user, job_id):
        """Get comprehensive job details with all applicants"""
        try:
            job = self.job_repo.find_one_by_id(job_id)

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
                self.user_repo.find_one_by_id(job["created_by"])
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
                    self.user_repo.find_one_by_id(app["student_id"])
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
            job = self.job_repo.find_one_by_id(job_id)

            if not job:
                return {"error": "Job not found"}, 404

            if job.get('workflow_version_id') or job.get('hiring_setup_version_id'):
                return {'error': 'Workflow jobs must be closed rather than deleted.', 'error_code': 'workflow_action_required'}, 409

            # Delete all applications for this job
            self.applications_collection.delete_many({"job_id": str(job["_id"])})

            # Delete the job
            self.job_repo.delete_by_id(job_id)

            return {
                "message": f'Job "{job.get("title")}" has been deleted',
                "job_id": job_id,
            }, 200
        except Exception as e:
            print(f"Error deleting job: {str(e)}")
            return {"error": "Failed to delete job"}, 500

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
                    self.user_repo.find_one_by_id(job["created_by"])
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

    def update_job(self, current_user, job_id, data):
        """Update job details"""
        try:
            job = self.job_repo.find_one_by_id(job_id)

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

            from services.job_setup_service import require_publishable_setup
            from models.hiring_workflow import WorkflowError
            try:
                require_publishable_setup(self.jobs_collection.database, job, update_data.get('status', job.get('status')))
            except WorkflowError as exc:
                return {'error': str(exc), 'error_code': exc.code}, exc.status
            changed = self.jobs_collection.update_one({'_id': job['_id'],
                'hiring_setup_version_id': job.get('hiring_setup_version_id'), 'status': job.get('status')}, {'$set': update_data})
            if changed.matched_count == 0:
                return {'error': 'Job changed; reload before saving.', 'error_code': 'stale_revision'}, 409

            return {
                "message": f'Job "{job.get("title")}" updated successfully',
                "job_id": job_id,
            }, 200
        except Exception as e:
            print(f"Error updating job: {str(e)}")
            return {"error": "Failed to update job"}, 500

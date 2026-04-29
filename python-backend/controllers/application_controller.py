import datetime
from bson import ObjectId
import sys
import os
import logging


def _coerce_objectids(value):
    """Recursively replace bson.ObjectId values with their string form so the
    result is JSON-serializable. Touches dicts and lists in place."""
    if isinstance(value, ObjectId):
        return str(value)
    if isinstance(value, dict):
        for k, v in list(value.items()):
            value[k] = _coerce_objectids(v)
        return value
    if isinstance(value, list):
        for i, item in enumerate(value):
            value[i] = _coerce_objectids(item)
        return value
    return value

sys.path.append(os.path.join(os.path.dirname(__file__), ".."))
from services.cv_scoring_service import CVScoringService
from controllers.cv_controller import CVController
from services.background_processor import get_background_processor

logger = logging.getLogger(__name__)


class ApplicationController:
    def __init__(self, db_collections):
        self.applications_collection = db_collections["applications"]
        self.jobs_collection = db_collections["jobs"]
        self.users_collection = db_collections["users"]
        self.interviews_collection = db_collections["interviews"]
        self.db_collections = db_collections  # Store for background tasks

        # Initialize CV scoring service
        try:
            self.cv_scoring_service = CVScoringService()
        except Exception as e:
            logger.warning(f"CV scoring service initialization failed: {e}")
            self.cv_scoring_service = None

        # Initialize CV controller for accessing CV PDFs
        try:
            self.cv_controller = CVController(db_collections)
        except Exception as e:
            logger.warning(f"CV controller initialization failed: {e}")
            self.cv_controller = None

        # Get background processor instance
        self.background_processor = get_background_processor()

    def apply_for_job(
        self, job_id, user_id, application_data, user_profile, cv_id=None
    ):
        """
        Submit job application with INSTANT SUBMISSION + Background CV Scoring

        Flow:
        1. Validate job and CV requirements
        2. Save application IMMEDIATELY with status='pending', is_visible=False
        3. Queue CV scoring task in background
        4. Return success to user instantly
        5. Background worker processes CV scoring and updates application

        Args:
            job_id: Job ID to apply for
            user_id: User ID applying
            application_data: Application data (cover letter, etc.)
            user_profile: User profile data
            cv_id: Optional CV ID to use (if not provided, uses primary CV or manual entry)

        Returns:
            tuple: (response_dict, status_code)
        """
        # Check if job exists
        job = self.jobs_collection.find_one({"_id": ObjectId(job_id)})
        if not job:
            return {"error": "Job not found"}, 404

        # Invite-only (burner) accounts can only apply to jobs they were invited to.
        if user_profile and user_profile.get("is_invite_only"):
            invited_ids = [str(j) for j in (user_profile.get("invited_job_ids") or [])]
            if str(job_id) not in invited_ids:
                return {
                    "error": "This account can only apply to jobs you were invited to.",
                    "error_code": "invite_only_scope",
                }, 403

        # Check if already applied. An invite skeleton (created with no CV yet) is
        # NOT a real application — we update it in place when the candidate submits.
        existing_application = self.applications_collection.find_one(
            {"job_id": job_id, "student_id": user_id}
        )
        is_invite_skeleton = bool(
            existing_application
            and not existing_application.get("cv_snapshot")
            and (
                existing_application.get("processing_status") == "awaiting_candidate"
                or existing_application.get("invite_type") in ("apply", "interview")
                or existing_application.get("auto_shortlisted_via_invite")
            )
        )
        if existing_application and not is_invite_skeleton:
            return {"error": "You have already applied for this job"}, 400

        # Get CV content (PDF or manual entry)
        cv_text = None
        cv_source = None  # Track where CV came from
        selected_cv = None  # Store CV metadata for snapshot

        # Priority order: Selected CV → Primary CV → Manual CV details
        if cv_id:
            # User explicitly selected a CV PDF
            if self.cv_controller:
                selected_cv = self.cv_controller.get_cv_by_id(user_id, cv_id)
                if selected_cv:
                    cv_text = selected_cv.get("extracted_text", "")
                    cv_source = "cv_pdf_selected"
                    logger.info(f"Using selected CV PDF: {cv_id}")
                else:
                    return {"error": f"CV with ID {cv_id} not found"}, 404
            else:
                return {"error": "CV management system not available"}, 500

        elif user_profile.get("cv_uploads"):
            # No CV selected, try primary CV
            if self.cv_controller:
                primary_cv = self.cv_controller.get_primary_cv(user_id)
                if primary_cv:
                    selected_cv = primary_cv
                    cv_text = primary_cv.get("extracted_text", "")
                    cv_source = "cv_pdf_primary"
                    cv_id = primary_cv.get("cv_id")
                    logger.info(f"Using primary CV PDF: {cv_id}")

        # Fallback to manual CV details if no PDF CV found
        cv_details = user_profile.get("cv_details")
        if not cv_text:
            if not cv_details:
                return {
                    "error": "CV is required before applying for jobs. Please upload a CV PDF or complete your CV details.",
                    "redirect": "/profile/cv-details",
                }, 400

            # Validate required CV sections for manual entry
            validation_errors = self._validate_cv_completion(cv_details)
            if validation_errors:
                return {
                    "error": "Please complete the following required CV sections before applying:\n"
                    + "\n".join(validation_errors),
                    "redirect": "/profile/cv-details",
                }, 400

            cv_source = "cv_manual_entry"
            logger.info("Using manual CV details")

        # Create CV snapshot (preserve CV content at application time)
        cv_snapshot = None
        if selected_cv:
            cv_snapshot = {
                'cv_id': selected_cv.get('cv_id'),
                'filename': selected_cv.get('filename'),
                'file_path': selected_cv.get('file_path'),
                'text': cv_text,
                'upload_date': selected_cv.get('upload_date'),
                'source': cv_source,
                'metadata': selected_cv.get('metadata', {})
            }
        elif cv_text:
            # Manual entry formatted as text
            cv_snapshot = {"text": cv_text, "source": cv_source}

        # Create JD snapshot (preserve JD content at application time)
        jd_text = job.get("jd_extracted_text") or job.get("description", "")
        jd_snapshot = {
            "text": jd_text,
            "job_title": job.get("title", ""),
            "company": job.get("company", ""),
            "has_pdf": bool(job.get("jd_pdf_path")),
        }

        # Determine status for new applies. For invite skeletons, preserve the
        # pre-shortlisted status set by the recruiter so a low CV score can't
        # auto-reject an interview invitee.
        was_auto_shortlisted = bool(
            existing_application
            and existing_application.get("auto_shortlisted_via_invite")
        )
        new_status = "shortlisted" if was_auto_shortlisted else "pending"
        new_status_reason = (
            "Pre-shortlisted via recruiter interview invite"
            if was_auto_shortlisted
            else "Application submitted, CV scoring in progress"
        )

        # Build the field set the candidate is contributing now (CV + cover letter
        # + profile snapshot). Reused for both insert and skeleton-update paths.
        candidate_fields = {
            "student_name": user_profile.get("name", ""),
            "student_email": user_profile.get("email", ""),
            "cover_letter": application_data.get("cover_letter", ""),
            "updated_at": datetime.datetime.utcnow(),
            "minimum_cv_score_required": job.get("minimum_cv_score", 50.0),
            "student_profile": {
                "bio": user_profile.get("bio", ""),
                "skills": user_profile.get("skills", []),
                "experience": user_profile.get("experience", ""),
                "education": user_profile.get("education", ""),
                "phone": user_profile.get("phone", ""),
                "location": user_profile.get("location", ""),
            },
            "cv_id": cv_id,
            "cv_snapshot": cv_snapshot,
            "jd_snapshot": jd_snapshot,
            "cv_source": cv_source,
            "processing_status": "pending",
            "is_visible": True,
            "cv_score_calculated_at": None,
            "processing_error": None,
            "auto_processed": True,
            "status": new_status,
            "status_reason": new_status_reason,
        }

        if is_invite_skeleton:
            # Update the skeleton in place rather than insert a duplicate row.
            self.applications_collection.update_one(
                {"_id": existing_application["_id"]},
                {"$set": candidate_fields},
            )
            application_id = str(existing_application["_id"])
            application_doc = {**existing_application, **candidate_fields, "_id": application_id}
            # Bump applicants counter only now that the candidate actually
            # submitted; skeleton creation no longer touches the counter.
            self.jobs_collection.update_one(
                {"_id": ObjectId(job_id)}, {"$inc": {"applicants": 1}}
            )
        else:
            # Fresh application: build the full doc and insert.
            application_doc = {
                "job_id": job_id,
                "student_id": user_id,
                "applied_at": datetime.datetime.utcnow(),
                "job_title": job.get("title", ""),
                "recruiter_id": job.get("created_by", ""),
                "cv_score": None,
                "cv_score_breakdown": None,
                "interview_score": None,
                **candidate_fields,
            }

            result = self.applications_collection.insert_one(application_doc)
            application_id = str(result.inserted_id)
            application_doc["_id"] = application_id

            self.jobs_collection.update_one(
                {"_id": ObjectId(job_id)}, {"$inc": {"applicants": 1}}
            )

        # Enqueue CV scoring task for background processing
        logger.info(f"Enqueueing CV scoring task for application {application_id}")

        cv_data = {"cv_text": cv_text, "cv_details": cv_details, "cv_source": cv_source}

        jd_data = {
            "jd_text": jd_text,
            "job": job,
            "job_id": job_id,
            "minimum_cv_score": job.get("minimum_cv_score", 50.0),
        }

        # Queue the scoring task (non-blocking)
        self.background_processor.enqueue_cv_scoring(
            application_id=application_id,
            cv_data=cv_data,
            jd_data=jd_data,
            db_collections=self.db_collections,
            cv_scoring_service=self.cv_scoring_service,
        )

        # Return success IMMEDIATELY!
        return {
            "message": "Application submitted successfully! CV scoring is being processed.",
            "application_id": application_id,
            "processing_status": "pending",
            "info": "Your application will appear in your dashboard once CV scoring is complete (usually within 30-60 seconds).",
        }, 201

    def withdraw_application(self, job_id, user_id):
        """Withdraw job application"""
        # Check if application exists
        application = self.applications_collection.find_one(
            {"job_id": job_id, "student_id": user_id}
        )
        if not application:
            return {"error": "No application found for this job"}, 404

        # Check if application can be withdrawn (only pending or applied status)
        status = application.get("status", "").lower()
        if status not in ["pending", "applied"]:
            return {
                "error": "Cannot withdraw application. Application is already being processed."
            }, 400

        # Delete the application
        self.applications_collection.delete_one(
            {"job_id": job_id, "student_id": user_id}
        )

        # Update job applicant count
        self.jobs_collection.update_one(
            {"_id": ObjectId(job_id)}, {"$inc": {"applicants": -1, "pending": -1}}
        )

        return {"message": "Application withdrawn successfully"}, 200

    def get_applications(self, user_id, user_type):
        """Retrieve applications based on user type"""
        if user_type in ["candidate", "student"]:
            # Students see all their applications including pending ones
            applications = list(
                self.applications_collection.find({"student_id": user_id})
            )

            # Convert ObjectId to string and fetch job details
            for app in applications:
                _coerce_objectids(app)
                app["_id"] = str(app["_id"])

                # Normalize datetime serialization for frontend
                if isinstance(app.get("applied_at"), datetime.datetime):
                    app["applied_at"] = app["applied_at"].isoformat()
                if isinstance(app.get("updated_at"), datetime.datetime):
                    app["updated_at"] = app["updated_at"].isoformat()
                # Keep cv_score as None for pending apps so frontend shows 'Processing'
                # Only use fallback for legacy data that has completed processing
                if (
                    app.get("cv_score") is None
                    and app.get("processing_status") == "completed"
                ):
                    app["cv_score"] = 85.0  # fallback placeholder for legacy data
                # Expose processing_status for frontend
                if "processing_status" not in app:
                    app["processing_status"] = (
                        "completed"  # legacy docs are already processed
                    )
                # expose interview_score if present (legacy docs may miss it)
                if "interview_score" not in app:
                    app["interview_score"] = None

                job = self.jobs_collection.find_one({"_id": ObjectId(app["job_id"])})
                if job:
                    app["job_details"] = {
                        "title": job.get("title"),
                        "company": job.get("company", "TechCorp Solutions"),
                        "location": job.get("location"),
                        "type": job.get("type"),
                        "department": job.get("department"),
                        "logo": job.get("logo"),
                    }

                # Use proctoring_score from application if available, otherwise get from interview
                completed_interview = self.interviews_collection.find_one(
                    {"application_id": app["_id"], "status": "completed"},
                    sort=[("updated_at", -1)],
                )
                
                # Check if job has gaze proctoring enabled
                gaze_proctoring_enabled = job.get('gaze_proctoring', False) if job else False
                
                # Prioritize scores stored directly in the application (from interview end process)
                if not gaze_proctoring_enabled:
                    app['proctoring_score'] = None
                elif 'proctoring_score' not in app or app.get('proctoring_score') is None:
                    # Fallback to interview collection if not in application
                    if completed_interview and completed_interview.get(
                        "proctoring_score"
                    ):
                        proctoring_score = completed_interview.get("proctoring_score")
                        # Handle both numeric and string values, exclude 'N/A'
                        if isinstance(proctoring_score, (int, float)):
                            app["proctoring_score"] = proctoring_score
                        elif (
                            isinstance(proctoring_score, str)
                            and proctoring_score.replace(".", "", 1).isdigit()
                        ):
                            app["proctoring_score"] = float(proctoring_score)
                        else:
                            app["proctoring_score"] = None
                    else:
                        app["proctoring_score"] = None

                # Ensure interview_score is also preserved from application
                if "interview_score" not in app:
                    app["interview_score"] = None

                # Whether an interview report is available
                app["report_available"] = completed_interview is not None

            return applications, 200

        elif user_type == "recruiter":
            # Recruiters see applications for their jobs - ONLY VISIBLE ONES (CV scoring completed)
            recruiter_jobs = list(
                self.jobs_collection.find({"created_by": user_id}, {"_id": 1})
            )
            job_ids = [str(job["_id"]) for job in recruiter_jobs]

            applications = list(
                self.applications_collection.find(
                    {
                        "job_id": {"$in": job_ids},
                        "is_visible": True,  # Only show applications where CV scoring is complete
                    }
                )
            )

            # Convert ObjectId to string and add job details
            for app in applications:
                _coerce_objectids(app)
                app["_id"] = str(app["_id"])
                # Normalize datetime serialization for frontend
                if isinstance(app.get("applied_at"), datetime.datetime):
                    app["applied_at"] = app["applied_at"].isoformat()
                if isinstance(app.get("updated_at"), datetime.datetime):
                    app["updated_at"] = app["updated_at"].isoformat()
                if app.get("cv_score") is None:
                    app["cv_score"] = 85.0
                if "interview_score" not in app:
                    app["interview_score"] = None

                job = self.jobs_collection.find_one({"_id": ObjectId(app["job_id"])})
                if job:
                    app["job_details"] = {
                        "title": job.get("title"),
                        "department": job.get("department"),
                        "location": job.get("location"),
                        "logo": job.get("logo"),
                        "company": job.get("company", "TechCorp Solutions"),
                    }

                # Provide base URL for CV retrieval; the frontend can append '?token=...'
                app["cv_url"] = f"/api/applications/{app['_id']}/cv"

                # Get proctoring score from most recent completed interview
                completed_interview = self.interviews_collection.find_one(
                    {"application_id": app["_id"], "status": "completed"},
                    sort=[("updated_at", -1)],
                )
                
                # Check if job has gaze proctoring enabled
                gaze_proctoring_enabled = job.get('gaze_proctoring', False) if job else False
                
                if not gaze_proctoring_enabled:
                    app['proctoring_score'] = None
                elif completed_interview and completed_interview.get('proctoring_score'):
                    proctoring_score = completed_interview.get('proctoring_score')
                    # Handle both numeric and string values, exclude 'N/A'
                    if isinstance(proctoring_score, (int, float)):
                        app["proctoring_score"] = proctoring_score
                    elif (
                        isinstance(proctoring_score, str)
                        and proctoring_score.replace(".", "", 1).isdigit()
                    ):
                        app["proctoring_score"] = float(proctoring_score)
                    else:
                        app["proctoring_score"] = None
                else:
                    app["proctoring_score"] = None

                # Whether a report is available
                app["report_available"] = completed_interview is not None

            return applications, 200

        else:
            return {"error": "Unauthorized"}, 403

    def update_application_status(self, application_id, recruiter_id, new_status):
        """Update application status (recruiters only)"""
        if new_status not in [
            "pending",
            "reviewed",
            "shortlisted",
            "interviewed",
            "selected",
            "rejected",
        ]:
            return {"error": "Invalid status"}, 400

        # Find application
        application = self.applications_collection.find_one(
            {"_id": ObjectId(application_id)}
        )
        if not application:
            return {"error": "Application not found"}, 404

        # Verify the job belongs to current recruiter
        job = self.jobs_collection.find_one(
            {"_id": ObjectId(application["job_id"]), "created_by": recruiter_id}
        )
        if not job:
            return {"error": "Unauthorized to update this application"}, 403

        old_status = application.get("status", "pending")

        # Update application status
        self.applications_collection.update_one(
            {"_id": ObjectId(application_id)},
            {
                "$set": {
                    "status": new_status,
                    "updated_at": datetime.datetime.utcnow(),
                    "updated_by": recruiter_id,
                }
            },
        )

        # Update job statistics
        # Build proper increments for known job counters
        job_update = {}
        status_counters = [
            "pending",
            "interviewed",
            "selected",
            "rejected",
        ]  # keep only fields that exist on jobs

        if old_status in status_counters:
            job_update[old_status] = -1
        if new_status in status_counters:
            job_update[new_status] = job_update.get(new_status, 0) + 1

        if job_update:
            self.jobs_collection.update_one(
                {"_id": ObjectId(application["job_id"])}, {"$inc": job_update}
            )

        return {"message": "Application status updated successfully"}, 200

    def get_application_by_id(self, application_id, user_id, user_type):
        """Get a single application document by id with job details"""
        try:
            app_doc = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )
        except Exception:
            return {"error": "Invalid application id"}, 400

        if not app_doc:
            return {"error": "Application not found"}, 404

        if user_type in ["candidate", "student"]:
            if app_doc.get("student_id") != user_id:
                return {"error": "Unauthorized"}, 403
        elif user_type == "recruiter":
            job = self.jobs_collection.find_one({"_id": ObjectId(app_doc["job_id"])})
            if not job or job.get("created_by") != user_id:
                return {"error": "Unauthorized"}, 403
        else:
            return {"error": "Unauthorized"}, 403

        # shape response
        _coerce_objectids(app_doc)
        app_doc["_id"] = str(app_doc["_id"])
        if isinstance(app_doc.get("applied_at"), datetime.datetime):
            app_doc["applied_at"] = app_doc["applied_at"].isoformat()
        if isinstance(app_doc.get("updated_at"), datetime.datetime):
            app_doc["updated_at"] = app_doc["updated_at"].isoformat()
        if app_doc.get("cv_score") is None:
            app_doc["cv_score"] = 85.0
        if "interview_score" not in app_doc:
            app_doc["interview_score"] = None

        job = self.jobs_collection.find_one({"_id": ObjectId(app_doc["job_id"])})
        if job:
            app_doc["job_details"] = {
                "title": job.get("title"),
                "company": job.get("company", "TechCorp Solutions"),
                "location": job.get("location"),
                "type": job.get("type"),
                "department": job.get("department"),
                "logo": job.get("logo"),
            }

        # whether report exists
        app_doc["report_available"] = (
            self.interviews_collection.find_one(
                {"application_id": app_doc["_id"], "status": "completed"}
            )
            is not None
        )

        return app_doc, 200

    def get_interview_report(self, application_id, user_id, user_type):
        """Return the latest interview report for a given application"""
        try:
            app_doc = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )
        except Exception:
            return {"error": "Invalid application id"}, 400

        if not app_doc:
            return {"error": "Application not found"}, 404
        if user_type in ["candidate", "student"]:
            if app_doc.get("student_id") != user_id:
                return {"error": "Unauthorized"}, 403
        elif user_type == "recruiter":
            job = self.jobs_collection.find_one({'_id': ObjectId(app_doc['job_id'])})
            if not job or job.get('created_by') != user_id:
                return {'error': 'Unauthorized'}, 403
        else:
            return {"error": "Unauthorized"}, 403

        report = self.interviews_collection.find_one(
            {
                "application_id": application_id,
                "status": "completed",
            },
            sort=[("updated_at", -1)],
        )
        if not report:
            return {"error": "Report not found"}, 404

        # Return complete report with transcript and proctoring details
        payload = {
            "session_id": report.get("session_id"),
            "final_score": report.get("final_score"),
            "proctoring_score": report.get("proctoring_score"),
            "evaluation": report.get("evaluation"),
            "transcript": report.get(
                "transcript", []
            ),  # Include conversation transcript
            "usage_summary": report.get("usage_summary", {}),
            "usage_deduction": report.get("usage_deduction", {}),
            # Proctoring details for the report modal
            "proctoring_config": report.get("proctoring_config", {
                "voice_detection": True,
                "eyeball_tracking": True,
                "gaze_heatmap": True,
            }),
            "gaze_metrics": report.get("gaze_metrics"),
            "manual_infractions": report.get("manual_infractions", []),
            "gaze_plot_path": report.get("gaze_plot_path"),
            "gaze_recorder_analysis": report.get("gaze_recorder_analysis"),
            "gaze_recorder_score": report.get("gaze_recorder_score"),
            "gaze_recorder_analysis_path": report.get("gaze_recorder_analysis_path"),
            "gaze_recorder_points_path": report.get("gaze_recorder_points_path"),
        }
        return payload, 200

    def _validate_cv_completion(self, cv_details):
        if not has_valid_education:
            errors.append("- At least one complete education entry is required")

        # Skills validation
        skills = cv_details.get("skills", {})
        technical_skills = skills.get("technical", [])
        if not technical_skills or len(technical_skills) == 0:
            errors.append("- Technical Skills are required")

        # Projects validation
        projects = cv_details.get("projects", [])
        has_valid_project = any(
            project.get("title", "").strip() and project.get("description", "").strip()
            for project in projects
        )
        if not has_valid_project:
            errors.append("- At least one complete project entry is required")

        # Salary Expectations validation
        salary_expectations = cv_details.get("salaryExpectations", {})
        if not salary_expectations.get("expectedSalary"):
            errors.append("- Expected Salary is required")

        return errors

    def recalculate_cv_score(self, application_id, user_id, user_type):
        """Recalculate CV score for an existing application"""
        try:
            # Find application
            application = self.applications_collection.find_one(
                {"_id": ObjectId(application_id)}
            )
            if not application:
                return {"error": "Application not found"}, 404

            # Authorization check
            if user_type == "recruiter":
                job = self.jobs_collection.find_one(
                    {"_id": ObjectId(application["job_id"])}
                )
                if not job or job.get("created_by") != user_id:
                    return {"error": "Unauthorized"}, 403
            elif user_type in ["candidate", "student"]:
                if application.get("student_id") != user_id:
                    return {"error": "Unauthorized"}, 403
            else:
                return {"error": "Unauthorized"}, 403

            # Get student profile and CV details
            student = self.users_collection.find_one(
                {"_id": ObjectId(application["student_id"])}
            )
            if not student:
                return {"error": "Student profile not found"}, 404

            cv_details = student.get("cv_details")
            if not cv_details:
                return {"error": "CV details not found for this student"}, 400

            # Get job details
            job = self.jobs_collection.find_one(
                {"_id": ObjectId(application["job_id"])}
            )
            if not job:
                return {"error": "Job not found"}, 404

            # Calculate new CV score
            if not self.cv_scoring_service:
                return {"error": "CV scoring service not available"}, 503

            try:
                scoring_result = self.cv_scoring_service.calculate_cv_score(
                    cv_details, job
                )
                new_cv_score = scoring_result.get("total_score", 75.0)
                new_cv_score_breakdown = scoring_result.get("score_breakdown")

                # Determine new application status based on CV score vs minimum threshold
                minimum_cv_score = job.get(
                    "minimum_cv_score", 50.0
                )  # Default to 50 if not set
                old_status = application.get("status", "pending")

                # Interview-invitees are pre-shortlisted by the recruiter; a low
                # CV score should never auto-reject them.
                auto_shortlisted_via_invite = bool(
                    application.get("auto_shortlisted_via_invite")
                )

                if auto_shortlisted_via_invite:
                    new_status = "shortlisted"
                    status_reason = (
                        f"CV score ({new_cv_score:.1f}); status preserved from recruiter interview invite"
                    )
                elif new_cv_score >= minimum_cv_score:
                    new_status = "shortlisted"
                    status_reason = f"CV score ({new_cv_score:.1f}) meets minimum requirement ({minimum_cv_score:.1f})"
                else:
                    new_status = "rejected"
                    status_reason = f"CV score ({new_cv_score:.1f}) below minimum requirement ({minimum_cv_score:.1f})"

                # Update application with new score and status
                update_data = {
                    "cv_score": new_cv_score,
                    "cv_score_breakdown": new_cv_score_breakdown,
                    "minimum_cv_score_required": minimum_cv_score,
                    "updated_at": datetime.datetime.utcnow(),
                }

                # Only update status if it changed and wasn't manually overridden
                if new_status != old_status and application.get("auto_processed", True):
                    update_data["status"] = new_status
                    update_data["status_reason"] = status_reason
                    update_data["auto_processed"] = True

                    # Update job statistics if status changed
                    job_update = {}
                    status_counters = ["pending", "interviewed", "selected", "rejected"]

                    if old_status in status_counters:
                        job_update[old_status] = -1

                    # Map new status to job counter
                    if new_status in status_counters:
                        job_update[new_status] = job_update.get(new_status, 0) + 1

                    if job_update:
                        self.jobs_collection.update_one(
                            {"_id": ObjectId(application["job_id"])},
                            {"$inc": job_update},
                        )

                self.applications_collection.update_one(
                    {"_id": ObjectId(application_id)}, {"$set": update_data}
                )

                return {
                    "message": "CV score recalculated successfully",
                    "cv_score": new_cv_score,
                    "cv_score_breakdown": new_cv_score_breakdown,
                    "minimum_cv_score_required": minimum_cv_score,
                    "status": update_data.get("status", old_status),
                    "status_reason": update_data.get(
                        "status_reason", "Status unchanged"
                    ),
                    "status_changed": new_status != old_status
                    and application.get("auto_processed", True),
                }, 200

            except Exception as e:
                print(f"Error recalculating CV score: {e}")
                return {"error": f"Failed to recalculate CV score: {str(e)}"}, 500

        except Exception as e:
            return {"error": f"Internal error: {str(e)}"}, 500

    def update_interview_score(
        self, application_id, user_id, user_type, interview_score
    ):
        """Update the interview score for an application"""
        try:
            # Validate application ID
            try:
                app_doc = self.applications_collection.find_one(
                    {"_id": ObjectId(application_id)}
                )
            except Exception:
                return {"error": "Invalid application ID"}, 400

            if not app_doc:
                return {"error": "Application not found"}, 404

            # Authorization check
            if user_type in ["candidate", "student"]:
                if app_doc.get("student_id") != user_id:
                    return {"error": "Unauthorized access"}, 403
            elif user_type == "recruiter":
                job = self.jobs_collection.find_one(
                    {"_id": ObjectId(app_doc["job_id"])}
                )
                if not job or job.get("created_by") != user_id:
                    return {"error": "Unauthorized access"}, 403
            else:
                return {"error": "Invalid user type"}, 403

            # Update the interview score
            update_result = self.applications_collection.update_one(
                {"_id": ObjectId(application_id)},
                {
                    "$set": {
                        "interview_score": interview_score,
                        "updated_at": datetime.datetime.utcnow(),
                    }
                },
            )

            if update_result.modified_count > 0:
                print(
                    f"✅ Interview score updated for application {application_id}: {interview_score}%"
                )
                return {
                    "message": "Interview score updated successfully",
                    "interview_score": interview_score,
                }, 200
            else:
                return {"error": "Failed to update interview score"}, 500

        except Exception as e:
            print(f"Error updating interview score: {e}")
            return {"error": f"Failed to update interview score: {str(e)}"}, 500

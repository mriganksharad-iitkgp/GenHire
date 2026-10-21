"""Application oversight: status, details, reports, practice reports."""

import datetime
from bson import ObjectId
from config.workflow import managed


class ApplicationAdmin:
    def update_application_status(self, current_user, application_id, status):
        """Update application status"""
        try:
            application = self.application_repo.find_one_by_id(application_id)

            if not application:
                return {"error": "Application not found"}, 404
            if managed(application):
                return {"error": "Managed applications require audited workflow actions; history cannot be deleted.",
                        "error_code": "workflow_action_required"}, 409

            if status == "selected":  # legacy name for screening_cleared
                status = "screening_cleared"
            valid_statuses = [
                "pending",
                "reviewed",
                "shortlisted",
                "interviewed",
                "screening_cleared",
                "rejected",
            ]
            if status not in valid_statuses:
                return {
                    "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                }, 400

            changed = self.application_repo.update_by_id(application_id,
                {
                    "$set": {
                        "status": status,
                        "updated_at": datetime.datetime.utcnow(),
                        "updated_by": str(current_user["_id"]),
                    }
                },
            )

            if not changed.matched_count:
                return {"error": "Application changed; use the current workflow action.", "error_code": "stale_revision"}, 409
            return {
                "message": "Application status updated",
                "application_id": application_id,
                "new_status": status,
            }, 200
        except Exception as e:
            print(f"Error updating application status: {str(e)}")
            return {"error": "Failed to update application status"}, 500

    def get_application_details(self, current_user, application_id):
        """Get comprehensive application details"""
        try:
            application = self.application_repo.find_one_by_id(application_id)

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
                self.user_repo.find_one_by_id(application["student_id"])
                if application.get("student_id")
                else None
            )
            job = (
                self.job_repo.find_one_by_id(application["job_id"])
                if application.get("job_id")
                else None
            )
            recruiter = (
                self.user_repo.find_one_by_id(application["recruiter_id"])
                if application.get("recruiter_id")
                else None
            )

            return {
                "application": {
                    "id": str(application["_id"]),
                    "status": application.get("status", "pending"),
                    "workflow_version_id": application.get("workflow_version_id"),
                    "workflow": application.get("workflow"),
                    "workflow_label": application.get("workflow_label"),
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
            application = self.application_repo.find_one_by_id(application_id)

            if not application:
                return {"error": "Application not found"}, 404
            if managed(application):
                return {"error": "Managed applications require audited workflow actions; history cannot be deleted.",
                        "error_code": "workflow_action_required"}, 409

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
                "screening_cleared",
                "rejected",
            ]

            for field in allowed_fields:
                if field in data:
                    if field == "status" and data[field] == "selected":
                        data[field] = "screening_cleared"  # legacy name
                    if field == "status" and data[field] not in valid_statuses:
                        return {
                            "error": f'Invalid status. Must be one of: {", ".join(valid_statuses)}'
                        }, 400
                    update_data[field] = data[field]

            changed = self.application_repo.update_by_id(application_id, {"$set": update_data}
            )

            if not changed.matched_count:
                return {"error": "Application changed; use the current workflow action.", "error_code": "stale_revision"}, 409
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
            application = self.application_repo.find_one_by_id(application_id)

            if not application:
                return {"error": "Application not found"}, 404
            if managed(application):
                return {"error": "Managed applications require audited workflow actions; history cannot be deleted.",
                        "error_code": "workflow_action_required"}, 409

            # Delete the application
            deleted = self.application_repo.delete_by_id(application_id)
            if not deleted.deleted_count:
                return {"error": "Application changed; history was retained.", "error_code": "stale_revision"}, 409

            # Update job applicant count if job exists
            if application.get("job_id"):
                self.job_repo.update_by_id(application["job_id"],
                    {"$inc": {"applicants": -1}},
                )

            return {
                "message": "Application deleted successfully",
                "application_id": application_id,
            }, 200
        except Exception as e:
            print(f"Error deleting application: {str(e)}")
            return {"error": "Failed to delete application"}, 500

    def get_application_report(self, current_user, application_id):
        """Get interview report for an application (admin access)"""
        try:
            print(f"[Admin] Getting application report for: {application_id}")

            try:
                app_doc = self.application_repo.find_one_by_id(application_id)
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

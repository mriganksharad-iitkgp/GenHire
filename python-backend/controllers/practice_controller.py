import os
import uuid
import threading
from datetime import datetime
from werkzeug.utils import secure_filename
from bson import ObjectId
from interview.api import InterviewAPI
from interview.config.settings import LLMProvider
from interview.core.cost_tracker import CostTracker
import logging
from services.pdf_parser_service import get_pdf_parser
from controllers.cv_controller import CVController
from services.usage_telemetry_service import record_usage_event
from services.llm_fallback_service import default_model_for, get_provider_priority
from services import interview_credit_service
from payment_module.services.wallet_service import WalletService
from payment_module.config.settings import PaymentConfig
from services.interview_flow_service import percentage, result_payload, evaluation_percentage, cached_answer_result, schedule_evaluation_refresh, stop_companion
from services.proctoring_service import build_proctoring_report

logger = logging.getLogger(__name__)


class PracticeController:
    """Controller for handling practice interview sessions"""

    # Predefined job descriptions for common roles
    ROLE_JD_MAP = {
        "software-engineer": "technical_question_bank/SoftwareEngineer_JD.txt",
        "data-scientist": "technical_question_bank/DataScientist_JD.txt",
        "product-manager": "technical_question_bank/ProductManager_JD.txt",
        "business-analyst": "technical_question_bank/BusinessAnalyst_JD.txt",
        "fullstack-developer": "technical_question_bank/FullStackDeveloper_JD.txt",
        "devops-engineer": "technical_question_bank/DevOpsEngineer_JD.txt",
        "finance-analyst": "technical_question_bank/BusinessAnalyst_JD.txt",
        "ui-ux-designer": "technical_question_bank/ProductManager_JD.txt",
    }

    def __init__(self, collections):
        self.collections = collections
        # Transient staging only (prompt .txt files the interview engine reads
        # during a session) â€” rooted in the OS temp dir, never the app tree.
        import tempfile
        self.upload_folder = os.path.join(tempfile.gettempdir(), "genhire_staging", "practice")
        self.cv_folder = os.path.join(self.upload_folder, "cv")
        self.jd_folder = os.path.join(self.upload_folder, "jd")

        # Role name mapping
        self.role_names = {
            "software-engineer": "Software Engineer",
            "data-scientist": "Data Scientist",
            "product-manager": "Product Manager",
            "business-analyst": "Business Analyst",
            "fullstack-developer": "Full Stack Developer",
            "devops-engineer": "DevOps Engineer",
            "finance-analyst": "Finance Analyst",
            "ui-ux-designer": "UI/UX Designer",
        }

        # Ensure upload directories exist
        os.makedirs(self.cv_folder, exist_ok=True)
        os.makedirs(self.jd_folder, exist_ok=True)

        # Initialize PDF parser
        try:
            self.pdf_parser = get_pdf_parser()
        except Exception as e:
            logger.warning(f"PDF parser initialization failed: {e}")
            self.pdf_parser = None

        # Initialize CV controller for accessing CV PDFs
        try:
            self.cv_controller = CVController(collections)
        except Exception as e:
            logger.warning(f"CV controller initialization failed: {e}")
            self.cv_controller = None

        # Initialize Interview API
        try:
            self.interview_api = InterviewAPI()
        except Exception as e:
            logger.error(f"Failed to initialize Interview API: {e}")
            self.interview_api = None

        self.wallet_service = WalletService(self.collections["users"].database)

    def _score_cv_background(self, session_id, cv_text, jd_text):
        from services.cv_scoring_service import CVScoringService
        try:
            result = CVScoringService().calculate_cv_score_from_text(cv_text, jd_text)
            score = None if result.get("is_fallback") else percentage(result.get("total_score"))
            update = {"cv_score": score / 100 if score is not None else None,
                "similarity_score": score / 100 if score is not None else None,
                "cv_score_status": "complete" if score is not None else "unavailable"}
        except Exception:
            logger.warning("Background practice CV scoring failed", exc_info=True)
            update = {"cv_score": None, "cv_score_status": "unavailable"}
        self.collections["practice_sessions"].update_one({"session_id": session_id}, {"$set": update})

    def start_practice(self, user_id, jd_file, role, difficulty, cv_id=None, proctoring_enabled=False):
        """
        Start a practice interview session

        Args:
            user_id: User ID
            jd_file: Optional uploaded JD file
            role: Role type (software-engineer, custom, etc.)
            difficulty: Interview difficulty
            cv_id: Optional CV ID to use (if not provided, uses primary CV or manual entry)

        Returns:
            tuple: (response_dict, status_code)
        """
        try:
            if not self.interview_api:
                return {"error": "Interview system not available"}, 500

            # Validate inputs
            if not role:
                return {"error": "Role selection is required"}, 400

            # Get candidate's profile
            user = self.collections["users"].find_one({"_id": ObjectId(user_id)})
            if not user:
                return {"error": "User not found"}, 404

            required_credits = (
                int(PaymentConfig.CANDIDATE_PRACTICE_PROCTORED_CREDITS)
                if proctoring_enabled
                else int(PaymentConfig.CANDIDATE_PRACTICE_CREDITS)
            )
            credit_snapshot = self.wallet_service.check_credit_availability(
                owner_id=user_id,
                audience="candidate",
                min_required_credits=required_credits,
            )
            if not credit_snapshot.get("can_start_interview", False):
                return {
                    "error": "Insufficient credits for practice interview.",
                    "error_code": credit_snapshot.get("error_code", "insufficient_credits"),
                    "credits_required": required_credits,
                    "credits_remaining": int(credit_snapshot.get("credits_remaining", 0) or 0),
                    "redirect": "/candidate/subscription",
                }, 402

            # Get CV content (PDF or manual entry)
            cv_text = None
            cv_source = None
            selected_cv = None

            # Priority order: Selected CV â†’ Primary CV â†’ Manual CV details
            if cv_id:
                # User explicitly selected a CV PDF
                if self.cv_controller:
                    selected_cv = self.cv_controller.get_cv_by_id(user_id, cv_id)
                    if selected_cv:
                        cv_text = selected_cv.get("extracted_text", "")
                        cv_source = "cv_pdf_selected"
                        logger.info(
                            f"Practice interview using selected CV PDF: {cv_id}"
                        )
                    else:
                        return {"error": f"CV with ID {cv_id} not found"}, 404
                else:
                    return {"error": "CV management system not available"}, 500

            elif user.get("cv_uploads"):
                # No CV selected, try primary CV
                if self.cv_controller:
                    primary_cv = self.cv_controller.get_primary_cv(user_id)
                    if primary_cv:
                        selected_cv = primary_cv
                        cv_text = primary_cv.get("extracted_text", "")
                        cv_source = "cv_pdf_primary"
                        logger.info(
                            f"Practice interview using primary CV PDF: {primary_cv.get('cv_id')}"
                        )

            # Fallback to manual CV details if no PDF CV found
            cv_details = user.get("cv_details")
            if not cv_text:
                if not cv_details:
                    return {
                        "error": "CV is required for practice interviews. Please upload a CV PDF or complete your CV details.",
                        "redirect": "/profile/cv-details",
                    }, 400

                # Import CV service to format CV details
                from services.cv_scoring_service import CVScoringService

                try:
                    cv_service = CVScoringService()
                except Exception as e:
                    logger.warning(
                        f"CVScoringService not available, using fallback: {e}"
                    )
                    cv_service = None

                # Format CV details to text (same as real interview)
                if cv_service:
                    cv_text = cv_service.format_cv_details(cv_details)
                else:
                    # Fallback formatter
                    cv_text = self._format_cv_from_details(cv_details)

                cv_source = "cv_manual_entry"
                logger.info("Practice interview using manual CV details")

            # Determine JD path and format based on role
            jd_text = None
            if role == "custom":
                # Custom role requires uploaded JD
                if not jd_file:
                    return {
                        "error": "Job description file is required for custom practice"
                    }, 400

                jd_filename = secure_filename(
                    f"practice_{user_id}_{uuid.uuid4().hex[:8]}_{jd_file.filename}"
                )
                jd_path = os.path.join(self.jd_folder, jd_filename)
                jd_file.save(jd_path)

                # Extract text from file (PDF or TXT) using PDF parser
                try:
                    if self.pdf_parser:
                        jd_text = self.pdf_parser.extract_text(jd_path)
                        logger.info(
                            f"Extracted {len(jd_text)} characters from uploaded JD: {jd_filename}"
                        )
                    else:
                        # Fallback: try reading as text
                        with open(jd_path, "r", encoding="utf-8") as f:
                            jd_text = f.read()
                except Exception as e:
                    logger.error(f"Failed to extract text from uploaded JD: {e}")
                    return {
                        "error": f"Failed to process job description file: {str(e)}"
                    }, 400
            else:
                # Use predefined JD for the role
                predefined_jd = self.ROLE_JD_MAP.get(role)
                if predefined_jd:
                    jd_file_path = os.path.join("question_bank", predefined_jd)
                    if os.path.exists(jd_file_path):
                        # Read JD text from predefined file (usually .txt)
                        try:
                            if self.pdf_parser:
                                jd_text = self.pdf_parser.extract_text(jd_file_path)
                            else:
                                with open(jd_file_path, "r", encoding="utf-8") as f:
                                    jd_text = f.read()
                        except Exception as e:
                            logger.error(f"Failed to read predefined JD: {e}")
                            jd_text = self._create_generic_jd_text(role)
                    else:
                        # Create generic JD text
                        jd_text = self._create_generic_jd_text(role)
                else:
                    return {"error": "Invalid role selected"}, 400

            # Create temporary .txt files for CV and JD (same as real interview)
            import uuid as _uuid

            tmp_folder = os.path.join(self.upload_folder, "tmp")
            os.makedirs(tmp_folder, exist_ok=True)

            cv_txt_path = os.path.join(tmp_folder, f"{_uuid.uuid4()}_practice_cv.txt")
            jd_txt_path = os.path.join(tmp_folder, f"{_uuid.uuid4()}_practice_jd.txt")

            with open(cv_txt_path, "w", encoding="utf-8") as f:
                f.write(cv_text)
            with open(jd_txt_path, "w", encoding="utf-8") as f:
                f.write(jd_text)

            logger.info(
                f"Starting practice interview - CV: {cv_txt_path}, JD: {jd_txt_path}, Role: {role}"
            )

            # Calculate CV score BEFORE starting interview (using CVScoringService - same as real applications)
            # CV scoring runs after persistence, off the startup path.
            cv_score = None
            cv_score_normalized = None

            # Start interview session using the interview API
            session_result = self.interview_api.start_interview(
                cv_file_path=cv_txt_path,
                job_description_path=jd_txt_path,
                reference_documents=[],
                proctoring_config={"voice_detection": bool(proctoring_enabled),
                    "object_detection": bool(proctoring_enabled), "eyeball_tracking": bool(proctoring_enabled),
                    "gaze_heatmap": False, "ai_detection": False, "dual_camera": False},
            )

            if "error" in session_result:
                return session_result, 500

            session_id = session_result["session_id"]

            usage_deduction = self.wallet_service.debit_wallet(
                owner_id=user_id,
                audience="candidate",
                credits=required_credits,
                transaction_type="practice_interview",
                reference_type="practice_session",
                reference_id=session_id,
                metadata={
                    "session_id": session_id,
                    "role": role,
                    "difficulty": difficulty,
                    "proctoring_enabled": bool(proctoring_enabled),
                },
                idempotency_key=f"practice-session:{session_id}",
            )
            if not usage_deduction.get("success"):
                return {
                    "error": "Insufficient credits for practice interview.",
                    "error_code": usage_deduction.get("error_code", "insufficient_credits"),
                    "credits_required": required_credits,
                    "credits_remaining": int(usage_deduction.get("credits_remaining", 0) or 0),
                    "redirect": "/candidate/subscription",
                }, 402

            # Use pre-calculated CV score (normalized to 0-1 for storage)
            logger.info(
                f"Practice session created: {session_id}, CV Score: {cv_score} (normalized: {cv_score_normalized})"
            )

            # Save practice session to database with comprehensive structure (matching real interviews)
            practice_session = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "difficulty": difficulty,
                "cv_path": cv_txt_path,
                "jd_path": jd_txt_path,
                "source_documents": {"cv_text": cv_text, "jd_text": jd_text},
                "engine_checkpoint": self.interview_api.session_manager.checkpoint(session_id),
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "setup",
                "is_practice": True,
                "similarity_score": cv_score_normalized,  # Pre-calculated CV-JD similarity (0-1)
                "cv_score": cv_score_normalized,  # CV-JD match score (0-1)
                "interview_score": None,  # Will be set when interview ends
                "proctoring_score": None,
                "proctoring_status": "pending" if proctoring_enabled else "disabled",
                "cv_score_status": "pending",
                "dual_proctoring_required": False,
                "proctoring_config": {"voice_detection": bool(proctoring_enabled),
                    "object_detection": bool(proctoring_enabled), "eyeball_tracking": bool(proctoring_enabled),
                    "gaze_heatmap": False, "ai_detection": False, "dual_camera": False},
                "qa_pairs": [],
                "transcript": [],  # Conversation transcript
                "evaluation": None,  # Final evaluation
                "final_score": None,  # Overall score
                "manual_infractions": [],
                "gaze_metrics": None,
                "gaze_plot_path": None,
                "proctoring_enabled": bool(proctoring_enabled),
                "usage_deduction": usage_deduction,
            }

            # Anything failing after the debit must give the credits back â€”
            # the candidate never got a usable session.
            try:
                self.collections["practice_sessions"].insert_one(practice_session)

                # Get first question
                question_result = {"question": session_result.get("first_question", "")}
                if "error" in (question_result or {}):
                    raise RuntimeError(
                        f"Failed to generate first question: {question_result.get('error')}"
                    )
            except Exception as post_debit_error:
                logger.error(
                    f"Practice start failed after debit, refunding: {post_debit_error}"
                )
                interview_credit_service.refund_practice_debit(
                    self.collections["users"].database,
                    {
                        "usage_deduction": usage_deduction,
                        "user_id": user_id,
                        "session_id": session_id,
                    },
                    reason="start_failed",
                )
                self.collections["practice_sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "abandoned",
                            "abandoned_reason": "start_failed",
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                self.interview_api.session_manager.sessions.pop(session_id, None)
                return {
                    "error": "Failed to start practice interview. Your credits have been refunded.",
                }, 500

            threading.Thread(target=self._score_cv_background,
                args=(session_id, cv_text, jd_text), daemon=True).start()
            return {
                "session_id": session_id,
                "status": "setup", "setup_required": True,
                "dual_proctoring_required": False, "mobile_recording_enabled": False,
                "cv_score_status": "pending",
                "proctoring_config": practice_session["proctoring_config"],
                "similarity_score": cv_score_normalized,  # Return normalized CV score (0-1)
                "cv_score": cv_score,  # Return CV score as percentage (0-100) for display
                "initial_questions": [question_result.get("question", "")],
                # Timing/progress config so practice interviews run with the
                # same client-side pacing as real ones.
                "question_timeout_seconds": session_result.get("question_timeout_seconds"),
                "question_deadline": session_result.get("question_deadline"),
                "max_questions": session_result.get("max_questions"),
                "message": "Practice interview session started successfully",
                "credits_required": required_credits,
                "usage_deduction": usage_deduction,
                "proctoring_enabled": bool(proctoring_enabled),
                "quota": {
                    "credits_allocated": int(
                        (usage_deduction or {}).get("credits_allocated", 0) or 0
                    ),
                    "credits_used": int(
                        (usage_deduction or {}).get("credits_used", 0) or 0
                    ),
                    "credits_remaining": int(
                        (usage_deduction or {}).get("credits_remaining", 0) or 0
                    ),
                },
            }, 200

        except Exception as e:
            logger.error(f"Error starting practice interview: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to start practice interview: {str(e)}"}, 500

    def submit_answer(self, session_id, user_id, question, answer):
        """Submit an answer in a practice interview"""
        try:
            if not self.interview_api:
                return {"error": "Interview system not available"}, 500

            # Verify session belongs to user
            session = self.collections["practice_sessions"].find_one(
                {"session_id": session_id, "user_id": user_id, "is_practice": True}
            )

            if not session:
                return {"error": "Practice session not found"}, 404

            from services import interview_integrity_service as integrity
            policy = integrity.check_health(self.collections["practice_sessions"], session)
            if policy["terminated"]:
                return {"error": "Restore interview monitoring before answering.", "error_code": "monitoring_required", "integrity": policy}, 409
            from routes.interview_routes import _restore_engine
            _restore_engine(session, self.interview_api.session_manager)

            if session.get("status") != "active":
                cached = cached_answer_result(session, question, answer)
                if cached:
                    return cached, 200
                return {"error": "Complete setup and start the interview before answering.",
                    "error_code": "session_not_active"}, 409

            if not isinstance(question, str) or not isinstance(answer, str) or len(question) > 12000 or len(answer) > 30000:
                return {"error": "Question and answer must be text within the allowed length."}, 400
            cached = cached_answer_result(session, question, answer)
            if cached:
                return cached, 200

            # Submit answer to interview API
            result = self.interview_api.submit_answer(session_id, question, answer)

            if "error" in result:
                return result, 500

            # Deep JSON serialization function to handle all types (same as real interview)
            def make_json_serializable(obj):
                """Recursively convert an object to be JSON serializable."""
                from enum import Enum
                import datetime

                if isinstance(obj, dict):
                    return {
                        key: make_json_serializable(value) for key, value in obj.items()
                    }
                elif isinstance(obj, list):
                    return [make_json_serializable(item) for item in obj]
                elif isinstance(obj, Enum):
                    return obj.value
                elif hasattr(obj, "isoformat"):  # datetime objects
                    return obj.isoformat()
                elif hasattr(obj, "__dict__"):  # custom objects with __dict__
                    return make_json_serializable(obj.__dict__)
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                else:
                    # Convert other types to string as fallback
                    return str(obj)

            # Apply deep serialization to the result
            serializable_result = make_json_serializable(result)
            if serializable_result.get("repeated_question"):
                return serializable_result, 200

            # Update practice session with Q&A pair and transcript
            self.collections["practice_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$push": {
                        "qa_pairs": {
                            "question": question,
                            "answer": answer,
                            "evaluation": (
                                serializable_result.get("current_evaluation")
                                if isinstance(serializable_result, dict)
                                else None
                            ),
                            "timestamp": datetime.utcnow(),
                        },
                        "transcript": {
                            "$each": [
                                {"role": "assistant", "text": question},
                                {
                                    "role": "user", 
                                    "text": answer,
                                    "ai_probability": (
                                        serializable_result.get("current_evaluation") or {}
                                    ).get("ai_probability") if isinstance(serializable_result, dict) else None
                                },
                            ]
                        },
                    },
                    "$set": {"updated_at": datetime.utcnow(), "engine_checkpoint": self.interview_api.session_manager.checkpoint(session_id), "last_answer": {
                        "question": question, "answer": answer, "result": serializable_result}},
                },
            )

            # Check if interview is complete
            if isinstance(serializable_result, dict) and serializable_result.get(
                "interview_complete"
            ):
                self.collections["practice_sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "finishing",
                            "completed_at": datetime.utcnow(),
                            "evaluation": serializable_result.get("final_evaluation"),
                        }
                    },
                )

            return serializable_result, 200

        except Exception as e:
            logger.error(f"Error submitting practice answer: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to submit answer: {str(e)}"}, 500

    def end_practice(self, session_id, user_id):
        """End a practice interview session"""
        try:
            # Verify session belongs to user
            session = self.collections["practice_sessions"].find_one(
                {"session_id": session_id, "user_id": user_id, "is_practice": True}
            )

            if not session:
                return {"error": "Practice session not found"}, 404
            if session.get("status") in {"completed", "abandoned", "terminated"}:
                return result_payload(session), 200
            claimed = self.collections["practice_sessions"].update_one({"_id": session["_id"], "status": {"$in": ["setup", "active"]}},
                {"$set": {"status": "finishing"}})
            if not claimed.matched_count:
                latest = self.collections["practice_sessions"].find_one({"_id": session["_id"]})
                if latest and latest.get("status") == "terminated":
                    return result_payload(latest), 200
            from interview.runtime import live_sessions
            if self.interview_api:
                from routes.interview_routes import _restore_engine
                _restore_engine(session, self.interview_api.session_manager)
            if live_sessions.get(session_id):
                live_sessions[session_id]["monitoring"] = False
            stop_companion(session)

            # Zero-answer discard: if the candidate never gave a single
            # substantive answer, refund the practice credits and abandon the
            # session instead of producing an empty report.
            internal_answered = 0
            session_manager = self.interview_api.session_manager if self.interview_api else None
            _internal = session_manager._get_session(session_id) if session_manager else None
            if _internal is not None and getattr(_internal, "interview_data", None):
                internal_answered = sum(
                    1
                    for qa in _internal.interview_data
                    if str((qa or {}).get("answer") or "").strip()
                )
            doc_answered = sum(
                1
                for qa in (session.get("qa_pairs") or [])
                if str((qa or {}).get("answer") or "").strip()
            )
            if max(internal_answered, doc_answered) == 0 and session.get("status") in {"setup", "active", "finishing"}:
                refund = interview_credit_service.refund_practice_debit(
                    self.collections["users"].database,
                    session,
                    reason="ended_no_answers",
                )
                self.collections["practice_sessions"].update_one(
                    {"session_id": session_id},
                    {
                        "$set": {
                            "status": "abandoned",
                            "abandoned_reason": "ended_no_answers",
                            "credits_refund": refund,
                            "updated_at": datetime.utcnow(),
                        }
                    },
                )
                if session_manager:
                    session_manager.sessions.pop(session_id, None)
                live_sessions.pop(session_id, None)
                CostTracker().end_session(session_id, clear_events=True)
                refunded_credits = 0
                if refund and refund.get("success"):
                    _txn = refund.get("transaction") or {}
                    refunded_credits = abs(int(_txn.get("delta_credits") or 0))
                return {
                    "status": "interview_discarded",
                    "message": "No answers were recorded, so this practice session was discarded and your credits were refunded.",
                    "refund": {
                        "success": bool(refund and refund.get("success")),
                        "credits_refunded": refunded_credits,
                    },
                    "session_id": session_id,
                }, 200

            # End interview via API
            result = self.interview_api.end_interview(session_id) if self.interview_api else {
                "final_evaluation": {"score_status": "unavailable", "final_score": None,
                    "qualitative_assessment": "The interview service was interrupted. Your answers are retained for review."}}
            from interview.runtime import live_sessions
            if live_sessions.get(session_id):
                live_sessions[session_id]["monitoring"] = False
            usage_summary = CostTracker().end_session(session_id, clear_events=True)
            usage_deduction = None

            # Deep JSON serialization function (same as real interview)
            def make_json_serializable(obj):
                """Recursively convert an object to be JSON serializable."""
                from enum import Enum
                import datetime as dt

                if isinstance(obj, dict):
                    return {
                        key: make_json_serializable(value) for key, value in obj.items()
                    }
                elif isinstance(obj, list):
                    return [make_json_serializable(item) for item in obj]
                elif isinstance(obj, Enum):
                    return obj.value
                elif hasattr(obj, "isoformat"):  # datetime objects
                    return obj.isoformat()
                elif hasattr(obj, "__dict__"):  # custom objects with __dict__
                    return make_json_serializable(obj.__dict__)
                elif isinstance(obj, (str, int, float, bool, type(None))):
                    return obj
                else:
                    # Convert other types to string as fallback
                    return str(obj)

            # Apply deep serialization to the result
            final_evaluation = (
                make_json_serializable(result.get("final_evaluation", {}))
                if isinstance(result, dict)
                else {}
            )

            # Log evaluation structure for debugging
            logger.info(
                f"Final evaluation keys: {list(final_evaluation.keys()) if isinstance(final_evaluation, dict) else 'N/A'}"
            )
            if isinstance(final_evaluation, dict):
                logger.info(
                    f"Has qualitative_assessment: {'qualitative_assessment' in final_evaluation}"
                )
                logger.info(f"Has quantitative: {'quantitative' in final_evaluation}")
                logger.info(
                    f"Has quantitative_scores: {'quantitative_scores' in final_evaluation}"
                )

            # Get the session manager's internal session data to extract interview_data
            # This contains the complete Q&A pairs from the interview
            internal_session = session_manager._get_session(session_id) if session_manager else None

            # Build proper transcript from interview_data (same as real interviews)
            transcript = list(session.get("transcript") or [])
            if internal_session and hasattr(internal_session, "interview_data"):
                transcript = []
                for item in internal_session.interview_data:
                    # Add question from assistant
                    transcript.append(
                        {"role": "assistant", "text": item.get("question", "")}
                    )
                    # Add answer from candidate
                    transcript.append({"role": "user", "text": item.get("answer", "")})

            logger.info(
                f"Built transcript with {len(transcript)} messages from interview_data"
            )

            completed_at = datetime.utcnow()

            # STT time must reflect the candidate's SPOKEN answers, never
            # wall-clock session duration â€” a practice tab left open (or a
            # session finalized later) used to record days' worth of "audio
            # seconds" and produce â‚¹28k/session rows in the cost statistics.
            tts_characters = sum(
                len(((item.get("text") or item.get("content") or "")).strip())
                for item in transcript
                if item.get("role") == "assistant"
            )
            answer_chars = sum(
                len(((item.get("text") or item.get("content") or "")).strip())
                for item in transcript
                if item.get("role") == "user"
            )
            # ~4 chars/token, ~0.4 s of speech per token (â‰ˆ150 wpm), 2 h cap.
            stt_seconds = min((answer_chars / 4.0) * 0.4, 7200.0)

            usage_summary = CostTracker().end_session(
                session_id,
                clear_events=True,
                fallback={
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_stt_seconds": stt_seconds,
                    "total_tts_characters": int(tts_characters or 0),
                    "model": default_model_for(get_provider_priority()[0]),
                },
            )

            # Prefer the tracker's real measured totals (populated by actual
            # STT/TTS calls during the session) over the transcript estimate.
            stt_seconds = float(usage_summary.get("total_stt_seconds") or stt_seconds)
            tts_characters = int(usage_summary.get("total_tts_characters") or tts_characters or 0)

            usage_deduction = session.get("usage_deduction")
            if not usage_deduction:
                practice_cost = (
                    int(PaymentConfig.CANDIDATE_PRACTICE_PROCTORED_CREDITS)
                    if bool(session.get("proctoring_enabled", False))
                    else int(PaymentConfig.CANDIDATE_PRACTICE_CREDITS)
                )
                usage_deduction = self.wallet_service.debit_wallet(
                    owner_id=user_id,
                    audience="candidate",
                    credits=practice_cost,
                    transaction_type="practice_interview",
                    reference_type="practice_session",
                    reference_id=session_id,
                    metadata={
                        "session_id": session_id,
                        "proctoring_enabled": bool(session.get("proctoring_enabled", False)),
                        "charged_at": "end_legacy_fallback",
                    },
                    idempotency_key=f"practice-session:{session_id}",
                )

            interview_score = evaluation_percentage(final_evaluation)
            from interview.runtime import live_sessions
            proctoring_report = build_proctoring_report(live_sessions.get(session_id), session)
            proctoring_score = proctoring_report.get("final_score")
            # Get CV score from session
            cv_score = session.get("cv_score", session.get("similarity_score", 0))

            # Update session status with comprehensive data (matching real interviews)
            self.collections["practice_sessions"].update_one(
                {"session_id": session_id},
                {
                    "$set": {
                        "status": "completed",
                        "updated_at": datetime.utcnow(),
                        "completed_at": completed_at,
                        "evaluation": final_evaluation,
                        "interview_score": interview_score,
                        "proctoring_score": proctoring_score,
                        "proctoring_report": proctoring_report,
                        "proctoring_status": proctoring_report.get("status"),
                        "stt_seconds": stt_seconds,
                        "tts_characters": int(tts_characters or 0),
                        "usage_summary": usage_summary,
                        "usage_deduction": usage_deduction,
                        "usage_source": "actual",
                        "final_score": interview_score,  # Overall performance
                        "transcript": transcript,  # Store properly formatted transcript
                    }
                },
            )

            record_usage_event(
                self.collections,
                action_type="practice_interview",
                actor_type="candidate",
                actor_id=user_id,
                model=default_model_for(get_provider_priority()[0]),
                stt_seconds=stt_seconds,
                tts_characters=int(tts_characters or 0),
                usage_source="actual",
                source={
                    "type": "practice_session",
                    "id": session_id,
                    "label": session.get("role") or "Practice Interview",
                },
                occurred_at=completed_at,
            )

            if final_evaluation:
                record_usage_event(
                    self.collections,
                    action_type="practice_interview_evaluation",
                    actor_type="candidate",
                    actor_id=user_id,
                    model=default_model_for(get_provider_priority()[0]),
                    usage_source="assumed",
                    source={
                        "type": "practice_session",
                        "id": session_id,
                        "label": session.get("role") or "Practice Evaluation",
                    },
                    occurred_at=completed_at,
                )

            logger.info(
                f"Practice interview {session_id} completed - CV: {cv_score}, Interview: {interview_score}%, Transcript messages: {len(transcript)}"
            )

            if internal_session and final_evaluation.get("pending_answers"):
                schedule_evaluation_refresh(session_manager, internal_session,
                    self.collections["practice_sessions"])
            elif session_manager:
                session_manager.sessions.pop(session_id, None)
            live_sessions.pop(session_id, None)
            return {
                "status": "interview_ended",
                "message": "Practice interview ended successfully",
                "evaluation": final_evaluation,
                "interview_score": interview_score,
                "proctoring_score": proctoring_score,
                "cv_score": percentage(cv_score, normalized=True),
                "cv_score_status": session.get("cv_score_status"),
                "proctoring_report": proctoring_report,
                "proctoring_status": proctoring_report.get("status"),
                "transcript": transcript,  # Return the formatted transcript
                "usage_summary": usage_summary,
                "usage_deduction": usage_deduction,
                "session_id": session_id,
            }, 200

        except Exception as e:
            logger.error(f"Error ending practice interview: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to end practice interview: {str(e)}"}, 500

    def get_practice_report(self, session_id, user_id):
        """Get detailed report for a specific practice interview"""
        try:
            # Find the practice session
            session = self.collections["practice_sessions"].find_one(
                {"session_id": session_id, "user_id": user_id, "is_practice": True}
            )

            if not session:
                return {"error": "Practice interview not found"}, 404

            # Convert ObjectId to string
            session["_id"] = str(session["_id"])

            # Format dates
            if "created_at" in session:
                session["created_at"] = session["created_at"].isoformat()
            if "updated_at" in session:
                session["updated_at"] = session["updated_at"].isoformat()
            if "completed_at" in session:
                session["completed_at"] = session["completed_at"].isoformat()

            # Build comprehensive report (matching real interview structure)
            report = {
                "session_id": session_id,
                "role": session.get("role"),
                "difficulty": session.get("difficulty"),
                "status": session.get("status"),
                "cv_score": percentage(session.get("cv_score"), normalized=True),
                "cv_score_status": session.get("cv_score_status"),
                "interview_score": session.get("interview_score", 0),
                "proctoring_score": session.get("proctoring_score"),
                "proctoring_status": session.get("proctoring_status", "incomplete"),
                "proctoring_report": session.get("proctoring_report") or {},
                "evaluation": session.get("evaluation", {}),
                "transcript": session.get("transcript", []),
                "qa_pairs": session.get("qa_pairs", []),
                "usage_summary": session.get("usage_summary", {}),
                "usage_deduction": session.get("usage_deduction", {}),
                "created_at": session.get("created_at"),
                "completed_at": session.get("completed_at"),
                "is_practice": True,
            }

            logger.info(
                f"Practice report for {session_id}: CV={report['cv_score']}%, Interview={report['interview_score']}%, Evaluation keys={list(report['evaluation'].keys()) if isinstance(report['evaluation'], dict) else 'N/A'}"
            )

            return report, 200

        except Exception as e:
            logger.error(f"Error fetching practice report: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to fetch practice report: {str(e)}"}, 500

    def get_history(self, user_id):
        """Get practice interview history for a user"""
        try:
            sessions = list(
                self.collections["practice_sessions"]
                .find({"user_id": user_id, "is_practice": True})
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
                    "proctoring_score": session.get("proctoring_score"),
                    "proctoring_status": session.get("proctoring_status", "incomplete"),
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
                usage_summary = session.get("usage_summary", {})
                if not isinstance(usage_summary, dict):
                    usage_summary = {}
                session_summary["calculated_cost_usd"] = float(
                    usage_summary.get("total_calculated_cost", usage_summary.get("total_cost", 0.0))
                    or 0.0
                )
                actual_cost = usage_summary.get("total_actual_cost")
                session_summary["actual_cost_usd"] = (
                    float(actual_cost or 0.0) if actual_cost is not None else None
                )
                history.append(session_summary)

            return {"sessions": history, "count": len(history)}, 200

        except Exception as e:
            logger.error(f"Error fetching practice history: {e}")
            import traceback

            traceback.print_exc()
            return {"error": f"Failed to fetch practice history: {str(e)}"}, 500

    def _create_generic_jd(self, role):
        """Create a generic job description for a role"""
        # Generic JD templates
        jd_templates = {
            "software-engineer": """
            Job Title: Software Engineer
            
            We are looking for a talented Software Engineer to join our team.
            
            Responsibilities:
            - Design, develop, and maintain software applications
            - Write clean, maintainable code
            - Collaborate with cross-functional teams
            - Participate in code reviews
            - Debug and resolve technical issues
            
            Requirements:
            - Bachelor's degree in Computer Science or related field
            - Proficiency in programming languages (Python, Java, JavaScript, etc.)
            - Strong problem-solving skills
            - Experience with version control (Git)
            - Good communication skills
            """,
            "data-scientist": """
            Job Title: Data Scientist
            
            We are seeking a Data Scientist to help us make data-driven decisions.
            
            Responsibilities:
            - Analyze large datasets to extract insights
            - Build and deploy machine learning models
            - Create data visualizations and reports
            - Collaborate with stakeholders
            
            Requirements:
            - Strong background in statistics and mathematics
            - Proficiency in Python, R, or similar
            - Experience with ML frameworks (TensorFlow, PyTorch, scikit-learn)
            - Knowledge of SQL and data manipulation
            """,
            # Add more templates as needed
        }

        template = jd_templates.get(role, jd_templates["software-engineer"])

        # Save to temp file
        jd_filename = f"generic_{role}_{uuid.uuid4().hex[:8]}.txt"
        jd_path = os.path.join(self.jd_folder, jd_filename)

        with open(jd_path, "w") as f:
            f.write(template)

        return jd_path

    def _create_generic_jd_text(self, role):
        """Create a generic job description text for a role"""
        jd_templates = {
            "software-engineer": """Job Title: Software Engineer

We are looking for a talented Software Engineer to join our team.

Responsibilities:
- Design, develop, and maintain software applications
- Write clean, maintainable code
- Collaborate with cross-functional teams
- Participate in code reviews
- Debug and resolve technical issues

Requirements:
- Bachelor's degree in Computer Science or related field
- Proficiency in programming languages (Python, Java, JavaScript, etc.)
- Strong problem-solving skills
- Experience with version control (Git)
- Good communication skills""",
            "data-scientist": """Job Title: Data Scientist

We are seeking a Data Scientist to help us make data-driven decisions.

Responsibilities:
- Analyze large datasets to extract insights
- Build and deploy machine learning models
- Create data visualizations and reports
- Collaborate with stakeholders

Requirements:
- Strong background in statistics and mathematics
- Proficiency in Python, R, or similar
- Experience with ML frameworks (TensorFlow, PyTorch, scikit-learn)
- Knowledge of SQL and data manipulation""",
            "product-manager": """Job Title: Product Manager

We are looking for a Product Manager to lead our product development.

Responsibilities:
- Define product vision and strategy
- Gather and prioritize product requirements
- Work with engineering and design teams
- Analyze market trends and customer feedback

Requirements:
- 3+ years of product management experience
- Strong analytical and communication skills
- Experience with agile methodologies
- Technical background preferred""",
            "business-analyst": """Job Title: Business Analyst

We need a Business Analyst to help improve our business processes.

Responsibilities:
- Analyze business requirements and processes
- Create documentation and reports
- Work with stakeholders across departments
- Identify opportunities for improvement

Requirements:
- Bachelor's degree in Business or related field
- Strong analytical and problem-solving skills
- Experience with data analysis tools
- Excellent communication skills""",
            "fullstack-developer": """Job Title: Full Stack Developer

We are seeking a Full Stack Developer to build modern web applications.

Responsibilities:
- Develop front-end and back-end components
- Build responsive user interfaces
- Design and implement APIs
- Ensure application performance and scalability

Requirements:
- Proficiency in JavaScript, HTML, CSS
- Experience with React, Node.js, or similar
- Knowledge of databases (SQL and NoSQL)
- Understanding of RESTful APIs""",
            "devops-engineer": """Job Title: DevOps Engineer

We are looking for a DevOps Engineer to manage our infrastructure.

Responsibilities:
- Manage cloud infrastructure (AWS, Azure, GCP)
- Implement CI/CD pipelines
- Monitor system performance and reliability
- Automate deployment processes

Requirements:
- Experience with containerization (Docker, Kubernetes)
- Knowledge of infrastructure as code (Terraform, Ansible)
- Strong scripting skills (Python, Bash)
- Understanding of networking and security""",
        }

        return jd_templates.get(role, jd_templates["software-engineer"])

    def _format_cv_from_details(self, cv_details):
        """Format CV details dict into a plain text string (fallback if CVScoringService not available)"""
        sections = []

        # Personal Information
        personal = cv_details.get("personal_info", {})
        if personal:
            sections.append(f"Name: {personal.get('name', '')}")
            sections.append(f"Email: {personal.get('email', '')}")
            sections.append(f"Phone: {personal.get('phone', '')}")
            sections.append(f"Location: {personal.get('location', '')}")
            sections.append("")

        # Summary
        if cv_details.get("summary"):
            sections.append("PROFESSIONAL SUMMARY")
            sections.append(cv_details["summary"])
            sections.append("")

        # Education
        education = cv_details.get("education", [])
        if education:
            sections.append("EDUCATION")
            for edu in education:
                sections.append(
                    f"{edu.get('degree', '')} - {edu.get('institution', '')}"
                )
                sections.append(f"{edu.get('year', '')}")
                sections.append("")

        # Experience
        experience = cv_details.get("experience", [])
        if experience:
            sections.append("WORK EXPERIENCE")
            for exp in experience:
                sections.append(f"{exp.get('title', '')} at {exp.get('company', '')}")
                sections.append(f"{exp.get('duration', '')}")
                sections.append(exp.get("description", ""))
                sections.append("")

        # Skills
        skills = cv_details.get("skills", [])
        if skills:
            sections.append("SKILLS")
            sections.append(", ".join(skills))
            sections.append("")

        # Projects
        projects = cv_details.get("projects", [])
        if projects:
            sections.append("PROJECTS")
            for proj in projects:
                sections.append(f"{proj.get('name', '')}")
                sections.append(proj.get("description", ""))
                sections.append("")

        return "\n".join(sections)

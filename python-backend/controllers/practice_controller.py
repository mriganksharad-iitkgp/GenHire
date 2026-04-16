import os
import uuid
from datetime import datetime
from werkzeug.utils import secure_filename
from bson import ObjectId
from interview.api import InterviewAPI
from interview.config.settings import LLMProvider
from interview.core.cost_tracker import CostTracker
import logging
from services.pdf_parser_service import get_pdf_parser
from controllers.cv_controller import CVController
from payment_module.services.subscription_service import SubscriptionService
from services.candidate_practice_quota_service import (
    get_candidate_practice_quota,
    consume_candidate_practice_credit,
)
from services.usage_telemetry_service import record_usage_event
from payment_module.services.subscription_service import SubscriptionService
from interview.core.cost_tracker import CostTracker

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
        self.upload_folder = "uploads/practice"
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
            api_key = os.getenv("GROQ_API_KEY")
            if not api_key:
                logger.error("GROQ_API_KEY not found in environment variables")
                self.interview_api = None
                return

            self.interview_api = InterviewAPI(
                llm_provider=LLMProvider.GROQ,
                model_name="llama-3.3-70b-versatile",
                api_key=api_key,
            )
        except Exception as e:
            logger.error(f"Failed to initialize Interview API: {e}")
            self.interview_api = None

        # Initialize payment subscription service for usage-based credits.
        try:
            self.subscription_service = SubscriptionService(
                self.collections["users"].database
            )
        except Exception as e:
            logger.warning(
                f"Subscription service initialization failed for practice billing: {e}"
            )
            self.subscription_service = None

    def start_practice(self, user_id, jd_file, role, difficulty, cv_id=None):
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

            credit_snapshot = None
            if self.subscription_service:
                credit_snapshot = self.subscription_service.check_credit_availability(
                    employer_id=user_id,
                    audience="candidate",
                )

            if credit_snapshot and not credit_snapshot.get(
                "can_start_interview", False
            ):
                # Free-tier candidates may not have a paid subscription doc.
                # Fall back to monthly candidate practice quota for no_subscription.
                if credit_snapshot.get("error_code") == "no_subscription":
                    quota_snapshot = get_candidate_practice_quota(
                        self.collections["users"].database,
                        user_id,
                    )
                    if not quota_snapshot.get("can_start_interview", False):
                        return {
                            "error": "Monthly practice interview limit reached for your available credits.",
                            "error_code": quota_snapshot.get(
                                "error_code", "CANDIDATE_PRACTICE_LIMIT_REACHED"
                            ),
                            "plan": {
                                "name": quota_snapshot.get("plan_name", "Free Tier"),
                                "credits_allocated": quota_snapshot.get(
                                    "credits_allocated", 0
                                ),
                                "credits_used": quota_snapshot.get("credits_used", 0),
                                "credits_remaining": quota_snapshot.get(
                                    "credits_remaining", 0
                                ),
                            },
                            "redirect": "/candidate/subscription",
                        }, 402
                else:
                    return {
                        "error": "Monthly practice interview limit reached for your available credits.",
                        "error_code": credit_snapshot.get(
                            "error_code", "CANDIDATE_PRACTICE_LIMIT_REACHED"
                        ),
                        "plan": {
                            "name": user.get("plan_name", "Free Tier"),
                            "credits_allocated": credit_snapshot.get(
                                "credits_allocated", 0
                            ),
                            "credits_used": credit_snapshot.get("credits_used", 0),
                            "credits_remaining": credit_snapshot.get(
                                "credits_remaining", 0
                            ),
                        },
                        "redirect": "/candidate/subscription",
                    }, 402

            # Get CV content (PDF or manual entry)
            cv_text = None
            cv_source = None
            selected_cv = None

            # Priority order: Selected CV → Primary CV → Manual CV details
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
            cv_score = 75.0  # Default fallback score
            try:
                # Import CV service for scoring
                from services.cv_scoring_service import CVScoringService

                try:
                    cv_service_for_scoring = CVScoringService()
                except Exception as e:
                    logger.warning(f"CVScoringService not available: {e}")
                    cv_service_for_scoring = None

                if cv_service_for_scoring:
                    # Use CVScoringService for both PDF and profile CVs
                    if cv_details:
                        # Method 1: Use structured CV details (manual entry) with formatted JD
                        logger.info(
                            "Calculating CV score using AI with structured CV details"
                        )
                        job_data = {
                            "title": self.role_names.get(
                                role, role.replace("-", " ").title()
                            ),
                            "description": jd_text,
                            "requirements": jd_text,
                            "role": role,
                        }
                        scoring_result = cv_service_for_scoring.calculate_cv_score(
                            cv_details, job_data
                        )
                        cv_score = scoring_result.get("total_score", 75.0)
                        logger.info(
                            f"CV score calculated using AI with structured data: {cv_score}%"
                        )
                    else:
                        # Method 2: Use raw text (PDF CV) with AI-based text scoring
                        logger.info(
                            "Calculating CV score using AI with text-based analysis"
                        )
                        if (
                            cv_text
                            and jd_text
                            and len(cv_text.strip()) > 0
                            and len(jd_text.strip()) > 0
                        ):
                            scoring_result = (
                                cv_service_for_scoring.calculate_cv_score_from_text(
                                    cv_text, jd_text
                                )
                            )
                            cv_score = scoring_result.get("total_score", 75.0)
                            logger.info(
                                f"CV score calculated using AI text analysis: {cv_score}%"
                            )
                        else:
                            logger.warning(
                                "CV or JD text is empty, using default score"
                            )
                            cv_score = 75.0
                else:
                    logger.warning(
                        "CVScoringService not available, using default score"
                    )
                    cv_score = 75.0

            except Exception as e:
                logger.error(f"CV scoring failed, using default: {e}")
                import traceback

                traceback.print_exc()
                cv_score = 75.0

            # Convert to 0-1 range for storage (will be converted back to 0-100 for display)
            cv_score_normalized = cv_score / 100.0

            # Start interview session using the interview API
            session_result = self.interview_api.start_interview(
                cv_file_path=cv_txt_path,
                job_description_path=jd_txt_path,
                reference_documents=[],
            )

            if "error" in session_result:
                return session_result, 500

            session_id = session_result["session_id"]

            # Use pre-calculated CV score (normalized to 0-1 for storage)
            logger.info(
                f"Practice session created: {session_id}, CV Score: {cv_score:.1f}% (normalized: {cv_score_normalized})"
            )

            # Save practice session to database with comprehensive structure (matching real interviews)
            practice_session = {
                "session_id": session_id,
                "user_id": user_id,
                "role": role,
                "difficulty": difficulty,
                "cv_path": cv_txt_path,
                "jd_path": jd_txt_path,
                "created_at": datetime.utcnow(),
                "updated_at": datetime.utcnow(),
                "status": "active",
                "is_practice": True,
                "similarity_score": cv_score_normalized,  # Pre-calculated CV-JD similarity (0-1)
                "cv_score": cv_score_normalized,  # CV-JD match score (0-1)
                "interview_score": None,  # Will be set when interview ends
                "proctoring_score": 100,  # Default 100 for practice (no proctoring)
                "qa_pairs": [],
                "transcript": [],  # Conversation transcript
                "evaluation": None,  # Final evaluation
                "final_score": None,  # Overall score
                "manual_infractions": [],
                "gaze_metrics": None,
                "gaze_plot_path": None,
            }

            self.collections["practice_sessions"].insert_one(practice_session)

            # Get first question
            question_result = self.interview_api.get_question(session_id)

            return {
                "session_id": session_id,
                "similarity_score": cv_score_normalized,  # Return normalized CV score (0-1)
                "cv_score": cv_score,  # Return CV score as percentage (0-100) for display
                "initial_questions": [question_result.get("question", "")],
                "message": "Practice interview session started successfully",
                "quota": {
                    "credits_allocated": int(
                        (credit_snapshot or {}).get("credits_allocated", 0) or 0
                    ),
                    "credits_used": int(
                        (credit_snapshot or {}).get("credits_used", 0) or 0
                    ),
                    "credits_remaining": int(
                        (credit_snapshot or {}).get("credits_remaining", 0) or 0
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
                    "$set": {"updated_at": datetime.utcnow()},
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
                            "status": "completed",
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
            if not self.interview_api:
                return {"error": "Interview system not available"}, 500

            # Verify session belongs to user
            session = self.collections["practice_sessions"].find_one(
                {"session_id": session_id, "user_id": user_id, "is_practice": True}
            )

            if not session:
                return {"error": "Practice session not found"}, 404

            # End interview via API
            result = self.interview_api.end_interview(session_id)
            usage_summary = CostTracker().end_session(session_id, clear_events=True)
            usage_deduction = None

            if self.subscription_service:
                usage_deduction = self.subscription_service.consume_usage_credits(
                    employer_id=user_id,
                    audience="candidate",
                    usage=usage_summary,
                    idempotency_key=f"practice-session:{session_id}",
                    metadata={
                        "session_id": session_id,
                        "is_practice": True,
                        "candidate_user_id": user_id,
                    },
                )

                # Free-tier candidates without paid subscription consume monthly quota event.
                if (
                    usage_deduction
                    and not usage_deduction.get("success", False)
                    and usage_deduction.get("error_code") == "no_subscription"
                ):
                    quota_snapshot = get_candidate_practice_quota(
                        self.collections["users"].database,
                        user_id,
                    )
                    consumed = consume_candidate_practice_credit(
                        self.collections["users"].database,
                        user_id,
                        session_id,
                        quota_snapshot=quota_snapshot,
                    )
                    if consumed:
                        usage_deduction = {
                            "success": True,
                            "idempotent_replay": False,
                            "credits_deducted": 1,
                            "usage_cost_usd": float(
                                usage_summary.get("total_cost", 0.0) or 0.0
                            ),
                            "credits_remaining": max(
                                0,
                                int(quota_snapshot.get("credits_remaining", 0) or 0)
                                - 1,
                            ),
                            "credits_used": int(
                                quota_snapshot.get("credits_used", 0) or 0
                            )
                            + 1,
                            "credits_allocated": int(
                                quota_snapshot.get("credits_allocated", 0) or 0
                            ),
                            "is_unlimited": False,
                            "interviews_used": int(
                                quota_snapshot.get("interviews_used", 0) or 0
                            )
                            + 1,
                            "source": "candidate_free_quota",
                        }

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
            session_manager = self.interview_api.session_manager
            internal_session = session_manager._get_session(session_id)

            # Build proper transcript from interview_data (same as real interviews)
            transcript = []
            if internal_session and hasattr(internal_session, "interview_data"):
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

            created_at = session.get("created_at")
            completed_at = datetime.utcnow()
            stt_seconds = 0.0
            if isinstance(created_at, datetime):
                stt_seconds = max(0.0, (completed_at - created_at).total_seconds())

            tts_characters = sum(
                len(((item.get("text") or item.get("content") or "")).strip())
                for item in transcript
                if item.get("role") == "assistant"
            )

            usage_summary = CostTracker().end_session(
                session_id,
                clear_events=True,
                fallback={
                    "total_prompt_tokens": 0,
                    "total_completion_tokens": 0,
                    "total_stt_seconds": stt_seconds,
                    "total_tts_characters": int(tts_characters or 0),
                    "model": "llama-3.3-70b-versatile",
                },
            )

            db = self.collections["users"].database
            subscription_service = SubscriptionService(db)
            usage_deduction = subscription_service.consume_usage_credits(
                employer_id=user_id,
                audience="candidate",
                usage_summary=usage_summary,
                idempotency_key=f"practice-session:{session_id}",
                metadata={
                    "session_id": session_id,
                    "source": "practice_session",
                },
            )

            if (
                not usage_deduction.get("success")
                and usage_deduction.get("error_code") == "no_subscription"
            ):
                quota_snapshot = get_candidate_practice_quota(db, user_id)
                consumed = consume_candidate_practice_credit(
                    db,
                    candidate_id=user_id,
                    session_id=session_id,
                    quota_snapshot=quota_snapshot,
                )

                if consumed:
                    usage_deduction = {
                        "success": True,
                        "credits_deducted": 1,
                        "usage_cost_usd": float(
                            usage_summary.get("total_cost", 0.0) or 0.0
                        ),
                        "credits_remaining": max(
                            0,
                            int(quota_snapshot.get("interviews_remaining", 0) or 0) - 1,
                        ),
                        "credits_used": int(
                            quota_snapshot.get("interviews_used", 0) or 0
                        )
                        + 1,
                        "credits_allocated": int(
                            quota_snapshot.get("interviews_allowed", 0) or 0
                        ),
                        "is_unlimited": False,
                        "interviews_used": int(
                            quota_snapshot.get("interviews_used", 0) or 0
                        )
                        + 1,
                        "source": "candidate_free_quota",
                    }
                else:
                    usage_deduction = {
                        "success": False,
                        "credits_deducted": 0,
                        "usage_cost_usd": float(
                            usage_summary.get("total_cost", 0.0) or 0.0
                        ),
                        "credits_remaining": int(
                            quota_snapshot.get("interviews_remaining", 0) or 0
                        ),
                        "error": "You've reached your free practice interview limit. Upgrade your plan to continue.",
                        "error_code": "CANDIDATE_PRACTICE_LIMIT_REACHED",
                        "source": "candidate_free_quota",
                    }

            # Calculate interview score from evaluation (same logic as real interviews)
            interview_score = 85  # Default score
            if isinstance(final_evaluation, dict) and final_evaluation:
                # Try to extract score from evaluation
                try:
                    if "quantitative" in final_evaluation and isinstance(
                        final_evaluation["quantitative"], dict
                    ):
                        if (
                            "average_relevance_score"
                            in final_evaluation["quantitative"]
                        ):
                            avg_score = final_evaluation["quantitative"][
                                "average_relevance_score"
                            ]
                            if isinstance(avg_score, (int, float)):
                                interview_score = (
                                    int(avg_score * 100)
                                    if avg_score <= 1
                                    else int(avg_score)
                                )
                    elif "quantitative_scores" in final_evaluation:
                        quant_scores = final_evaluation["quantitative_scores"]
                        if isinstance(quant_scores, (int, float)):
                            interview_score = (
                                int(quant_scores * 100)
                                if quant_scores <= 1
                                else int(quant_scores)
                            )
                        elif isinstance(quant_scores, dict):
                            avg = (
                                quant_scores.get("average")
                                or quant_scores.get("overall")
                                or list(quant_scores.values())[0]
                                if quant_scores
                                else 85
                            )
                            if isinstance(avg, (int, float)):
                                interview_score = (
                                    int(avg * 100) if avg <= 1 else int(avg)
                                )
                except Exception as e:
                    logger.warning(
                        f"Could not extract interview score from evaluation: {e}"
                    )
                    interview_score = 85  # Use default on error

            # Calculate proctoring score (100 for practice - no actual proctoring)
            proctoring_score = 100

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
                model="gpt-4o",
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
                    model="gpt-5-mini",
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

            return {
                "status": "interview_ended",
                "message": "Practice interview ended successfully",
                "evaluation": final_evaluation,
                "interview_score": interview_score,
                "proctoring_score": proctoring_score,
                "cv_score": cv_score,
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
                "cv_score": int(
                    (session.get("cv_score", session.get("similarity_score", 0))) * 100
                ),  # Convert 0-1 to 0-100
                "interview_score": session.get("interview_score", 0),
                "proctoring_score": session.get("proctoring_score", 100),
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

"""Interview lifecycle regressions; no provider, database, camera or account access."""
import importlib
import json
import sys
import threading
import time
import types
import unittest
from pathlib import Path
from types import SimpleNamespace
from unittest.mock import patch
from bson import BSON

BACKEND = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND))
for name in ("interview", "interview.core", "interview.config", "interview.llm", "interview.document"):
    if name not in sys.modules:
        module = types.ModuleType(name)
        module.__path__ = [str(BACKEND.joinpath(*name.split(".")))]
        sys.modules[name] = module

with patch("dotenv.load_dotenv", return_value=False):
    from interview.config.settings import InterviewConfig, LLMConfig
    from interview.core.prompt_based_question_generator import PromptBasedQuestionGenerator
    evaluator_module = types.ModuleType("evaluation_model.rubrics_eval.evaluation_system")
    evaluator_module.EvaluationSystem = lambda: None
    ai_module = types.ModuleType("utils.ai_detection")
    ai_module.check_ai_content = lambda answer: None
    loader_module = types.ModuleType("interview.document.loader")
    loader_module.DocumentLoader = None
    with patch.dict(sys.modules, {
        "evaluation_model.rubrics_eval.evaluation_system": evaluator_module,
        "utils.ai_detection": ai_module,
        "interview.document.loader": loader_module,
    }):
        runtime = importlib.import_module("interview.core.session_manager")


class InterviewRuntimeTests(unittest.TestCase):
    def setUp(self):
        self.llm = SimpleNamespace(complete=lambda prompt: SimpleNamespace(text="Could you give me a brief introduction to your background?", usage={}, model="test"))
        with patch.object(runtime.InterviewSessionManager, "_create_fallback_llm", return_value=self.llm), patch.object(runtime, "EvaluationSystem", return_value=None):
            self.manager = runtime.InterviewSessionManager(InterviewConfig(), LLMConfig())
        self.manager.report_llm = SimpleNamespace(complete=self.report_fixture)

    def report_fixture(self, prompt):
        evidence = json.loads(prompt.split("EVIDENCE:\n", 1)[1])
        return SimpleNamespace(text=json.dumps({"qualitative_assessment": "Further assessment needed.",
            "answers": [{"question_number": q["question_number"], "suggested_answer": "I would explain the approach using [my actual result].",
                         "improvement_tip": "Connect the example to the job requirement."} for q in evidence["questions"]]}), usage={}, model="test")

    def create(self, jd="Software engineer with Python and SQL", cv="Candidate with Python experience"):
        loader = SimpleNamespace(validate_documents=lambda: {"cv": True, "jd": True},
                                 get_cv_sections=lambda: {"experience": cv}, get_jd_text=lambda: jd)
        with patch.object(runtime, "DocumentLoader", return_value=loader):
            data = self.manager.create_session("cv", "jd", [], pre_validated=True)
        self.assertNotIn("error", data)
        return data, self.manager.sessions[data["session_id"]]

    def test_setup_has_no_timer_and_activation_is_idempotent(self):
        started = time.monotonic()
        data, session = self.create()
        self.assertLess(time.monotonic() - started, 1.0)
        self.assertIsNone(data["question_deadline"])
        self.assertIsNone(session.question_served_at)
        first = self.manager.activate_session(session.session_id)
        second = self.manager.activate_session(session.session_id)
        self.assertEqual(first["question_deadline"], second["question_deadline"])
        self.assertGreater(first["question_deadline"], time.time())

    def test_candidate_state_and_role_banks_are_isolated(self):
        _, software = self.create()
        _, analyst = self.create("Data analyst with Excel and Power BI", "Analyst career")
        self.assertIsNot(software.question_generator, analyst.question_generator)
        self.assertEqual(software.conversation_context.job_role, "software_engineer")
        self.assertIn("Data analyst", analyst.question_generator.jd_content)
        self.assertIn("Python", software.question_generator.cv_content)
        self.assertNotIn("Analyst career", software.question_generator.cv_content)

    def test_repeat_initial_question_does_not_score_or_advance(self):
        _, session = self.create()
        result = self.manager.submit_answer(session.session_id, session.current_question, "Could you repeat the question?")
        self.assertTrue(result["repeated_question"])
        self.assertEqual(session.questions_asked, 0)
        self.assertEqual(session.interview_data, [])

    def test_stale_question_is_rejected_without_scoring(self):
        _, session = self.create()
        result = self.manager.submit_answer(session.session_id, "An earlier question", "My answer")
        self.assertEqual(result["error_code"], "stale_question")
        self.assertEqual(session.interview_data, [])

    def test_keywords_do_not_match_short_tokens_inside_words(self):
        keywords = self.manager.question_generator._fallback_extract_cv_keywords("", "Experience with Python and Django programming")
        self.assertNotIn("R", keywords)
        self.assertNotIn("Go", keywords)

    def test_pending_length_placeholder_is_not_a_final_score(self):
        _, session = self.create()
        session.interview_data = [{"question": "Q", "answer": "Long answer", "evaluation": {
            "answer_score": 0.8, "language_score": 0.8, "evaluation_method": "fallback", "evaluation_status": "pending"}}]
        session.questions_asked = 1
        session.is_complete = True
        report = self.manager._generate_final_evaluation(session)
        self.assertEqual(report["score_status"], "unavailable")
        self.assertIsNone(report["quantitative_scores"]["answer_score"])
        self.assertEqual(report["pending_answers"], 1)
        self.assertIs(self.manager._generate_final_evaluation(session), report)

    def test_provider_wait_has_a_total_budget(self):
        release = threading.Event()
        generator = PromptBasedQuestionGenerator(SimpleNamespace(complete=lambda prompt: release.wait(2)), InterviewConfig())
        try:
            with patch.dict("os.environ", {"INTERVIEW_QUESTION_BUDGET_SECONDS": "0.5"}):
                started = time.monotonic()
                with self.assertRaisesRegex(RuntimeError, "budget"):
                    generator._complete_llm("Ask a question")
                self.assertLess(time.monotonic() - started, 0.9)
        finally:
            release.set()

    def test_rubric_one_is_one_percent_and_invalid_score_is_unavailable(self):
        result = self.manager._convert_scores_to_standard_format(1, 0.5, "Q", "A")
        self.assertEqual(result["answer_score"], 0.01)
        self.assertEqual(result["language_score"], 0.005)
        for value in (True, float("nan"), float("inf"), "80"):
            with self.assertRaises(ValueError):
                self.manager._convert_scores_to_standard_format(value, 80, "Q", "A")

    def test_short_attempted_answers_are_not_confused_with_skip_requests(self):
        for answer in ("We pass data through the API.", "I skip null rows during ingestion.", "I am not sure, but I would test it"):
            self.assertFalse(runtime.classify_answer(answer)["is_non_answer"], answer)
        for answer in ("skip", "I don't know.", "Sorry, not sure"):
            self.assertTrue(runtime.classify_answer(answer)["is_non_answer"], answer)

    def test_parallel_evaluators_keep_candidate_usage_context(self):
        _, session = self.create()
        captured = []

        def technical(question, answer):
            captured.append(runtime.CostTracker()._resolve_session_id(None))
            return 80, []

        def communication(question, answer):
            captured.append(runtime.CostTracker()._resolve_session_id(None))
            return 70

        self.manager.evaluation_system = SimpleNamespace(evaluate_single_answer_fast=technical,
                                                          evaluate_communication_score=communication)
        with patch.object(session.question_generator, "get_next_question", return_value=("Describe a design decision", None)):
            result = self.manager.submit_answer(session.session_id, session.current_question,
                                                "I have worked on software development with Python and APIs.")
        self.assertNotIn("error", result)
        self.assertTrue(session.evaluation_events[-1].wait(1))
        self.assertEqual(captured, [session.session_id, session.session_id])

    def test_generated_metadata_roundtrips_json_and_bson_and_matches_asked_phase(self):
        _, session = self.create()
        generator = session.question_generator
        context = session.conversation_context
        context.experiential_questions_asked = self.manager.config.experiential_questions_limit - 1
        with patch.object(generator, "_complete_llm", return_value=SimpleNamespace(text="Tell me about your project decisions?")):
            question, metadata = generator.get_next_question(context, "I worked with Python.")
        self.assertEqual(metadata.interview_phase.value, "experiential_questions")
        self.assertEqual(metadata.source, "direct_llm")
        session.current_question = question
        session.current_question_metadata = metadata
        response = self.manager.get_next_question(session.session_id)
        self.assertEqual(json.loads(json.dumps(response))["question_metadata"]["interview_phase"], "experiential_questions")
        BSON.encode(response)

    def test_cached_pending_report_refreshes_after_real_evaluator_finishes(self):
        _, session = self.create()
        evaluation = {"answer_score": 0.8, "language_score": 0.8, "evaluation_method": "fallback", "evaluation_status": "pending"}
        session.interview_data = [{"question": "Q", "answer": "A", "evaluation": evaluation}]
        session.questions_asked = 1
        first = self.manager._generate_final_evaluation(session)
        self.assertEqual(first["score_status"], "unavailable")
        evaluation.update({"evaluation_method": "rubrics-eval", "evaluation_status": "complete"})
        session.question_generator._complete_llm = lambda prompt: SimpleNamespace(text="Evaluation finished")
        updated = self.manager._generate_final_evaluation(session)
        self.assertEqual(updated["score_status"], "complete")
        self.assertEqual(updated["quantitative_scores"]["answer_score"], 0.8)

    def test_direct_generation_uses_only_cv_jd_and_complete_history(self):
        from interview.core.direct_question_generator import DirectQuestionGenerator
        prompts = []
        responses = iter(["Could you introduce yourself and your background?", "How did you verify the throughput improvement?"])
        def complete(prompt):
            prompts.append(prompt)
            return SimpleNamespace(text=next(responses), usage={}, model="test")
        with patch.object(PromptBasedQuestionGenerator, "_load_hr_question_banks", side_effect=AssertionError("bank loaded")), patch.object(PromptBasedQuestionGenerator, "_get_embedding", side_effect=AssertionError("retrieval used")):
            generator = DirectQuestionGenerator(SimpleNamespace(complete=complete), InterviewConfig())
            context = generator.initialize_conversation({"cv": "Built Python APIs"}, "Backend engineer using Postgres")
            first, meta = generator.first_question(context)
            second, _ = generator.get_next_question(context, "I batched writes to increase throughput.")
        self.assertEqual(meta.source, "direct_llm")
        self.assertIn("Built Python APIs", prompts[1])
        self.assertIn("Backend engineer using Postgres", prompts[1])
        self.assertIn(first, prompts[1])
        self.assertIn("I batched writes", prompts[1])
        self.assertEqual(context.question_count, 1)
        self.assertIn("throughput", second)

    def test_generation_outage_does_not_end_or_advance_attempt(self):
        _, session = self.create()
        with patch.object(session.question_generator, "get_next_question", side_effect=RuntimeError("offline")):
            result = self.manager.submit_answer(session.session_id, session.current_question, "I do not know")
        self.assertEqual(result["error_code"], "next_question_unavailable")
        self.assertFalse(session.is_complete)
        self.assertEqual(session.questions_asked, 0)
        self.assertEqual(session.interview_data, [])

    def test_failed_next_question_retries_do_not_launch_duplicate_scoring(self):
        _, session = self.create()
        with patch.object(session.question_generator, "get_next_question", side_effect=RuntimeError("provider offline")), patch.object(runtime.threading, "Thread") as worker:
            for _ in range(3):
                result = self.manager.submit_answer(session.session_id, session.current_question, "I built an API with Python and tested the response times.")
                self.assertEqual(result["error_code"], "next_question_unavailable")
            worker.assert_not_called()
        self.assertEqual(session.evaluation_events, [])

    def test_last_answer_does_not_wait_for_report(self):
        _, session = self.create()
        session.questions_asked = session.conversation_context.question_count = self.manager.config.max_questions - 1
        with patch.object(self.manager, "_generate_final_evaluation", side_effect=AssertionError("report blocked answer")):
            result = self.manager.submit_answer(session.session_id, session.current_question, "I do not know")
        self.assertTrue(result["interview_complete"])
        self.assertEqual(result["final_evaluation"]["score_status"], "pending")

    def test_repeat_keywords_inside_real_answers_are_scored(self):
        for answer in ("We repeat each test again to detect flakiness.", "As I already explained, the cache stores results.",
                       "Could you repeat the question? I implemented the API with authentication.",
                       "I was asked before about an outage and already told the team how to fix it."):
            _, session = self.create()
            with patch.object(session.question_generator, "get_next_question", return_value=("What trade-off did you consider?", None)):
                result = self.manager.submit_answer(session.session_id, session.current_question, answer)
            self.assertFalse(result.get("repeated_question", False), answer)
            self.assertEqual(session.interview_data[0]["answer"], answer)

    def test_twelve_question_plan_waits_for_the_full_last_answer(self):
        _, session = self.create()
        questions = iter([
            "Hi, I'm Alex. What was your personal role in the Python API project?",
            "Why did you choose that approach over its main alternative?",
            "What was the hardest deployment issue in your internship?",
            "What measurable lesson did your accessibility initiative teach you?",
            "How would you validate a SQL migration with zero downtime?",
            "How would you roll back that migration if validation failed?",
            "How would you investigate a production latency regression?",
            "Which controls would protect customer records in this role?",
            "How would you resolve a disagreement with a teammate?",
            "How would you check whether your conflict resolution had worked?",
            "What interests you about this position?",
        ])
        phases = ["greeting"] + ["experiential_questions"] * 4 + ["technical_questions"] * 4 + ["hr_questions"] * 3
        prompts = []
        def complete(prompt):
            prompts.append(prompt)
            return SimpleNamespace(text=next(questions), usage={}, model="test")
        session.question_generator.llm = SimpleNamespace(complete=complete)
        for number in range(1, 13):
            self.assertFalse(session.is_complete)
            self.assertEqual(runtime._plain_metadata(session.current_question_metadata)["interview_phase"], phases[number - 1])
            self.assertEqual("Alex" in session.current_question, number == 1)
            self.assertEqual(runtime._plain_metadata(session.current_question_metadata)["intent"] == "probe_deeper", number in {3, 7, 11})
            question = session.current_question
            answer = "I do not know" if number < 12 else "I would first listen to both views, agree on shared criteria, then test the options and document the decision."
            result = self.manager.submit_answer(session.session_id, question, answer)
            self.assertNotIn("error", result)
            self.assertEqual(result["interview_complete"], number == 12)
            self.assertEqual(session.questions_asked, number)
        self.assertEqual(len(prompts), 11)
        self.assertEqual(len(session.interview_data), 12)
        self.assertEqual(session.interview_data[-1]["answer"], answer)
        self.assertIn("This is question 6 of 12. Stage: Job requirements", prompts[4])
        self.assertIn("This is question 9 of 12. Stage: Job requirements", prompts[7])
        self.assertIn("This is question 12 of 12. Stage: HR", prompts[-1])

    def test_start_accepts_spoken_intro_without_question_mark_or_extra_retry(self):
        for text in ("Please introduce yourself and describe your background.",
                     "Please briefly introduce yourself.",
                     "To begin, tell me about yourself.",
                     "Could you give a brief overview of your background",
                     "Hi, I'm Alex, please introduce yourself.",
                     "Hello, I am Alex from GenHire. Tell me about yourself."):
            with self.subTest(text=text), patch.object(self.llm, "complete", return_value=SimpleNamespace(text=text)) as complete:
                data, session = self.create()
                self.assertEqual(complete.call_count, 1)
                self.assertEqual(session.current_question.count("Alex"), 1)
                self.assertEqual(data["max_questions"], 12)

    def test_invalid_greeting_only_output_still_requires_repair(self):
        generator = self.manager.question_generator
        context = generator.initialize_conversation({"cv": "Python"}, "SQL engineer")
        with patch.object(generator, "_complete_llm", side_effect=[SimpleNamespace(text="Hi, I'm Alex."), SimpleNamespace(text="Please introduce yourself.")]) as complete:
            question, _ = generator.first_question(context)
        self.assertEqual(complete.call_count, 2)
        self.assertEqual(question, "Hi, I'm Alex. Please introduce yourself.")

    def test_invalid_opening_is_recoverable_without_exposing_validator_instructions(self):
        loader = SimpleNamespace(get_cv_sections=lambda: {"cv": "Python"}, get_jd_text=lambda: "SQL engineer")
        with patch.object(runtime, "DocumentLoader", return_value=loader), patch.object(self.llm, "complete", return_value=SimpleNamespace(text="Ready.")) as complete:
            result = self.manager.create_session("cv", "jd", [], pre_validated=True)
        self.assertEqual(result["error_code"], "opening_question_unavailable")
        self.assertNotIn("Return one concise", result["error"])
        self.assertEqual(complete.call_count, 2)
        self.assertFalse(self.manager.sessions)

    def test_follow_up_turns_include_previous_answer_without_a_planning_call(self):
        from interview.core.direct_question_generator import DirectQuestionGenerator
        for number in (3, 7, 11):
            generator = DirectQuestionGenerator(self.llm)
            context = generator.initialize_conversation({"cv": "Python APIs"}, "Backend engineer")
            context.conversation_history = [{"question": f"Earlier topic {i}?", "answer": "Earlier answer"} for i in range(number - 2)]
            context.asked_questions = ["Which solution did you choose?"]
            with patch.object(generator, "_complete_llm", return_value=SimpleNamespace(text="Explain the trade-off behind that cache expiry decision.")) as complete:
                _, metadata = generator.get_next_question(context, "I chose a five-minute cache expiry.")
            self.assertEqual(complete.call_count, 1)
            prompt = complete.call_args.args[0]
            self.assertIn("I chose a five-minute cache expiry.", prompt)
            self.assertIn(f"Follow up on question {number - 1}", prompt)
            self.assertEqual(metadata.intent.value, "probe_deeper")

    def test_duplicate_repair_does_not_advance_twice(self):
        _, session = self.create()
        generator, context = session.question_generator, session.conversation_context
        question = "How did you validate your API throughput improvement?"
        context.asked_questions.append(question)
        context.conversation_history = [{"question": session.current_question, "answer": "My introduction"}]
        with patch.object(generator, "_complete_llm", side_effect=[SimpleNamespace(text=question), SimpleNamespace(text="What drove your database choice for the dashboard?")]) as complete:
            next_question, _ = generator.get_next_question(context, "I used a load test.")
        self.assertEqual(complete.call_count, 2)
        self.assertEqual(context.question_count, 2)
        self.assertEqual(len(context.conversation_history), 2)
        self.assertIn("database", next_question)

    def test_first_question_repairs_technical_opening(self):
        generator = self.manager.question_generator
        context = generator.initialize_conversation({"cv": "Python"}, "SQL engineer")
        with patch.object(generator, "_complete_llm", side_effect=[SimpleNamespace(text="How did you build the classifier?"), SimpleNamespace(text="Hello, I'm Alex. Could you introduce yourself?")]):
            question, _ = generator.first_question(context)
        self.assertEqual(question.count("Alex"), 1)
        self.assertIn("introduce yourself", question)

    def test_preparation_answers_mapped_by_number_and_preserve_actual_scores(self):
        _, session = self.create()
        session.interview_data = [{"question": "Why this role?", "answer": "", "evaluation": {
            "answer_score": 0, "language_score": 0, "evaluation_method": "pre_classified", "evaluation_status": "complete"}}]
        session.questions_asked = 1
        report = self.manager._generate_final_evaluation(session)
        self.assertEqual(report["preparation_status"], "complete")
        self.assertIn("[my actual result]", report["per_question_evaluations"][0]["suggested_answer"])
        self.assertEqual(report["quantitative_scores"]["answer_score"], 0)
        self.assertEqual(report["per_question_evaluations"][0]["answer"], "")

    def test_preparation_rejects_missing_or_ambiguous_question_mappings(self):
        from interview.core.preparation_report import parse_preparation_report
        one = {"question_number": 1, "suggested_answer": "Actual example", "improvement_tip": "Be specific"}
        two = dict(one, question_number=2, suggested_answer="Other example")
        valid = {"qualitative_assessment": "Review", "answers": [two, one]}
        _, answers = parse_preparation_report(json.dumps(valid), 2)
        self.assertEqual(answers[0]["suggested_answer"], "Actual example")
        for invalid in ([one], [one, one], [one, dict(two, question_number=True)], [one, dict(two, suggested_answer="")]):
            with self.assertRaises(ValueError):
                parse_preparation_report(json.dumps(dict(valid, answers=invalid)), 2)

    def test_newer_checkpoint_replaces_stale_worker_without_regenerating(self):
        _, session = self.create()
        checkpoint = self.manager.checkpoint(session.session_id)
        checkpoint.update(questions_asked=5, current_question="How would you protect customer data?",
                          interview_data=[{"question": f"Question {i}", "answer": "Saved", "evaluation": {}} for i in range(5)])
        doc = {"session_id": session.session_id, "status": "active", "engine_checkpoint": checkpoint}
        loader = SimpleNamespace(get_cv_sections=lambda: {"cv": "Python"}, get_jd_text=lambda: "Security engineer")
        with patch.object(runtime, "DocumentLoader", return_value=loader), patch.object(self.llm, "complete", side_effect=AssertionError("Should not regenerate")):
            restored = self.manager.restore_session(doc, "Python", "Security engineer")
        self.assertEqual(restored.questions_asked, 5)
        self.assertEqual(len(restored.conversation_context.conversation_history), 5)
        self.assertIn("Question 4", restored.interview_history)
        self.assertEqual(restored.current_question, checkpoint["current_question"])

    def test_completion_restores_after_tenth_answer_without_inventing_an_eleventh_question(self):
        _, session = self.create()
        checkpoint = self.manager.checkpoint(session.session_id)
        pairs = [{"question": f"Question {i}", "answer": "Saved", "evaluation": {}} for i in range(10)]
        checkpoint.update(questions_asked=10, is_complete=True, current_question=None, interview_data=pairs)
        checkpoint.pop("max_questions")  # A legacy ten-question attempt.
        doc = {"session_id": session.session_id, "status": "active", "qa_pairs": pairs, "engine_checkpoint": checkpoint}
        self.manager.sessions.clear()
        loader = SimpleNamespace(get_cv_sections=lambda: {"cv": "Python"}, get_jd_text=lambda: "Engineer")
        with patch.object(runtime, "DocumentLoader", return_value=loader):
            restored = self.manager.restore_session(doc, "Python", "Engineer")
        self.assertTrue(restored.is_complete)
        self.assertEqual(restored.max_questions, 10)
        self.assertIsNone(restored.current_question)
        self.assertEqual(len(restored.conversation_context.asked_questions), 10)
        self.assertEqual(len(restored.interview_data), 10)


if __name__ == "__main__":
    unittest.main()

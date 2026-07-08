"""
Standalone test harness for the interview question generator.

Drives the SAME engine the real product uses (PromptBasedQuestionGenerator +
InterviewConfig, exactly as wired in interview/core/session_manager.py) directly
from pasted/CV JD text, with no real candidate needed. Produces the 10 questions
a real (or practice) interview would generate for that CV+JD pair and saves a
readable transcript + a raw JSON dump to disk.

WHY THIS EXISTS / KEY CAVEAT
-----------------------------
In production, question #2 onward is adaptive: each call to get_next_question()
is fed the candidate's last answer + a score. Without a real candidate typing
real answers, there is nothing to adapt to. This script offers three ways to
handle that (see --mode below); which one to use depends on what you're trying
to demonstrate.

Also important: in production (session_manager.py submit_answer()), the score
that actually drives adaptivity (topic switching, performance-guidance wording)
is a CHEAP HEURISTIC (answer length + keyword overlap with the question) computed
synchronously — NOT the slower LLM-based rubric evaluation, which runs in a
background thread and only lands in time for the *final report*, not the *next
question*. This script reimplements that same heuristic (see `fallback_evaluation`
below) so --mode simulate/interactive reproduce real adaptivity faithfully.

MODES (--mode)
---------------
  blind        Generate all 10 questions with no answer feedback at all
               (last_answer=None every time). Shows the "cold" JD/CV-driven
               question plan: topic order, difficulty distribution, question
               bank vs LLM source — with zero adaptivity. Fastest, cheapest,
               fully deterministic-ish. Good for comparing JD/CV combos apples
               to apples.
  simulate     (default) After each question, an LLM plays the candidate
               (grounded in the pasted CV text) to produce a plausible answer,
               which is then scored with the same heuristic production uses,
               and fed back in — so topic switches / difficulty / performance
               guidance behave as they would in a real interview. No human
               needed. Uses extra LLM calls (~1 per question).
  interactive  You type the answers yourself at the terminal, exactly like
               interactive_interview.py. The most faithful mimic of a real
               interview, since the adaptivity is driven by genuine answers,
               just typed instead of spoken.

USAGE
-----
  python testQuestionGeneration.py
      Prompts for JD text then CV text (paste, then a line with only END).

  python testQuestionGeneration.py --jd path/to/jd.txt --cv path/to/cv.txt \
      --label sde1_junior --mode simulate --out-dir question_generation_tests/run1

Requires OPENAI_API_KEY / GOOGLE_API_KEY / GROQ_API_KEY in .env (same as the
main app) since it calls the real LLM provider chain.
"""

import argparse
import json
import os
import sys
from datetime import datetime

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__)))))

from dotenv import load_dotenv

load_dotenv()

from interview.core.prompt_based_question_generator import (
    PromptBasedQuestionGenerator,
    InterviewPhase,
)
from interview.core.session_manager import InterviewSessionManager
from interview.config.settings import InterviewConfig, LLMConfig
from interview.document.processor import DocumentProcessor

# Exact copy of session_manager.py's hardcoded first question — in production
# this is NOT LLM-generated and does NOT depend on CV/JD at all.
HARDCODED_FIRST_QUESTION = (
    "Hello, I'm Alex. Great to meet you! Could you please give me a brief "
    "introduction about yourself and your background?"
)

SIMULATE_ANSWER_PROMPT = """You are role-playing as {candidate_name}, a real candidate being interviewed for the "{job_title}" role. Here is their actual CV/background:

{cv_excerpt}

The interviewer just asked:
"{question}"

Answer as this candidate would, truthfully based on the CV above, in first person, 2-4 sentences. If the CV doesn't clearly cover this topic, give a brief plausible answer drawing on adjacent experience, and don't be afraid to say you have limited hands-on experience with it. Do not mention that you are an AI or that this is a simulation.

Candidate's answer:"""


def fallback_evaluation(question: str, answer: str) -> dict:
    """Reimplementation of session_manager.InterviewSessionManager._fallback_evaluation.

    This — not the slower LLM rubric evaluator — is what actually drives
    next-question adaptivity in production, because it's computed synchronously
    while the rubric evaluation runs in a background thread that finishes too
    late to influence get_next_question().
    """
    answer = answer or ""
    answer_length = len(answer.strip())

    if answer_length == 0:
        score, reasoning = 0.0, "No answer provided."
    elif answer_length < 10:
        score, reasoning = 0.2, "Answer too brief to demonstrate understanding."
    elif answer_length < 50:
        score, reasoning = 0.4, "Answer provides minimal detail."
    elif answer_length < 150:
        score, reasoning = 0.6, "Answer provides adequate detail."
    else:
        score, reasoning = 0.8, "Answer provides comprehensive detail."

    question_lower = question.lower()
    answer_lower = answer.lower()
    skip = {"what", "how", "why", "when", "where", "which", "explain", "describe"}
    technical_keywords = [w for w in question_lower.split() if len(w) > 3 and w not in skip]
    relevance_boost = sum(0.1 for kw in technical_keywords[:5] if kw in answer_lower)
    final_score = min(1.0, score + relevance_boost)

    return {
        "answer_score": final_score,
        "language_score": score,
        "relevance_score": final_score,
        "technical_accuracy_score": final_score,
        "communication_score": score,
        "overall_score": final_score,
        "reasoning": f"{reasoning} Relevance check: {relevance_boost:.1f} boost applied.",
        "evaluation_method": "fallback",
    }


def read_pasted_text(label: str) -> str:
    print(f"\nPaste the {label} text below. On a new line, type END and press Enter to finish.\n")
    lines = []
    while True:
        try:
            line = input()
        except EOFError:
            break
        if line.strip() == "END":
            break
        lines.append(line)
    return "\n".join(lines).strip()


def build_llm():
    """Same fallback provider chain (OpenAI -> Gemini -> Groq) production uses."""
    llm_config = LLMConfig()
    return InterviewSessionManager._create_fallback_llm(llm_config)


def simulate_answer(llm, candidate_name, job_title, cv_text, question) -> str:
    prompt = SIMULATE_ANSWER_PROMPT.format(
        candidate_name=candidate_name,
        job_title=job_title,
        cv_excerpt=cv_text[:2500],
        question=question,
    )
    try:
        response = llm.complete(prompt)
        text = (response.text or "").strip()
        if text:
            return text
    except Exception as e:
        print(f"   [warn] simulated-answer generation failed, using generic answer: {e}")
    return "I've worked on similar things before, though I'd want to double-check the specifics with real data before committing to an approach."


def run_test(jd_text: str, cv_text: str, mode: str, label: str) -> dict:
    print(f"\n{'=' * 80}\nRunning question generation test: {label}  (mode={mode})\n{'=' * 80}")

    llm = build_llm()
    config = InterviewConfig()  # max_questions=10, min_questions=10 — same as production
    qg = PromptBasedQuestionGenerator(llm, config=config)

    resume_sections = DocumentProcessor().segregate_resume_text(cv_text)

    print("Analyzing CV + JD (keyword extraction, skill level, difficulty distribution)...")
    context = qg.initialize_conversation(resume_sections, jd_text)

    # Mirror session_manager._initialize_context_background(): the hardcoded
    # first question already serves as the greeting, so skip GREETING/
    # STRUCTURE_EXPLANATION phases exactly like production does.
    context.has_been_greeted = True
    context.interview_phase = InterviewPhase.EXPERIENTIAL_QUESTIONS

    print(f"  Candidate name (from CV):     {context.candidate_name}")
    print(f"  Job title (from JD):          {context.job_title}")
    print(f"  Job role classification:      {context.job_role}")
    print(f"  Role difficulty (from JD):    {context.role_difficulty}")
    print(f"  Difficulty distribution:      {context.difficulty_distribution}")
    print(f"  Candidate skill level (CV):   {context.candidate_skill_level}")
    print(f"  JD required skill level:      {context.jd_required_skill_level}")
    print(f"  JD keywords used for topics:  {context.jd_keywords}")
    print(f"  CV keywords (experiential):   {context.cv_keywords}")

    transcript = []
    current_question = HARDCODED_FIRST_QUESTION
    transcript.append({
        "index": 1,
        "phase": "introduction",
        "topic": None,
        "difficulty": None,
        "source": "hardcoded",
        "question": current_question,
        "answer": None,
        "evaluation": None,
    })
    print(f"\nQ1 [introduction | hardcoded, not JD/CV-driven]:\n  {current_question}")

    for i in range(2, 11):
        # 1. produce an answer to the PREVIOUS question
        if mode == "blind":
            answer, evaluation = None, None
        elif mode == "interactive":
            print(f"\nYour answer to Q{i - 1}:")
            answer = input(">> ").strip()
            evaluation = fallback_evaluation(current_question, answer)
        else:  # simulate
            answer = simulate_answer(
                llm, context.candidate_name, context.job_title, cv_text, current_question
            )
            evaluation = fallback_evaluation(current_question, answer)
            print(f"\n[simulated candidate answer to Q{i - 1}]: {answer}")
            print(f"[heuristic score]: {evaluation['relevance_score']:.2f}")

        if answer is not None:
            transcript[-1]["answer"] = answer
            transcript[-1]["evaluation"] = evaluation

        # 2. get the next question
        question, metadata = qg.get_next_question(context, answer, evaluation)
        current_question = question

        entry = {
            "index": i,
            "phase": context.interview_phase.value,
            "topic": metadata.topic_area,
            "difficulty": metadata.difficulty_level,
            "source": metadata.source,
            "question": question,
            "answer": None,
            "evaluation": None,
        }
        transcript.append(entry)
        print(f"\nQ{i} [{entry['phase']} | topic={entry['topic']} | difficulty={entry['difficulty']} | source={entry['source']}]:\n  {question}")

    # Capture the answer to the final question too, for a complete record.
    if mode == "interactive":
        print(f"\nYour answer to Q10:")
        final_answer = input(">> ").strip()
        transcript[-1]["answer"] = final_answer
        transcript[-1]["evaluation"] = fallback_evaluation(current_question, final_answer)
    elif mode == "simulate":
        final_answer = simulate_answer(
            llm, context.candidate_name, context.job_title, cv_text, current_question
        )
        transcript[-1]["answer"] = final_answer
        transcript[-1]["evaluation"] = fallback_evaluation(current_question, final_answer)

    result = {
        "label": label,
        "mode": mode,
        "generated_at": datetime.now().isoformat(),
        "candidate_name": context.candidate_name,
        "job_title": context.job_title,
        "job_role": context.job_role,
        "role_difficulty": context.role_difficulty,
        "difficulty_distribution": context.difficulty_distribution,
        "candidate_skill_level": context.candidate_skill_level,
        "jd_required_skill_level": context.jd_required_skill_level,
        "jd_keywords": context.jd_keywords,
        "cv_keywords": context.cv_keywords,
        "topics_covered": context.topics_covered,
        "jd_text": jd_text,
        "cv_text": cv_text,
        "questions": transcript,
    }
    return result


def save_result(result: dict, out_dir: str):
    os.makedirs(out_dir, exist_ok=True)
    json_path = os.path.join(out_dir, f"{result['label']}.json")
    md_path = os.path.join(out_dir, f"{result['label']}.md")

    with open(json_path, "w", encoding="utf-8") as f:
        json.dump(result, f, indent=2, ensure_ascii=False)

    lines = []
    lines.append(f"# Question Generation Test — {result['label']}")
    lines.append("")
    lines.append(f"- Mode: `{result['mode']}`")
    lines.append(f"- Generated at: {result['generated_at']}")
    lines.append(f"- Candidate name (from CV): {result['candidate_name']}")
    lines.append(f"- Job title (from JD): {result['job_title']}")
    lines.append(f"- Job role classification: {result['job_role']}")
    lines.append(f"- Role difficulty (from JD): {result['role_difficulty']}")
    lines.append(f"- Difficulty distribution (easy/medium/hard): {result['difficulty_distribution']}")
    lines.append(f"- Candidate skill level (from CV): {result['candidate_skill_level']}")
    lines.append(f"- JD required skill level: {result['jd_required_skill_level']}")
    lines.append(f"- JD keywords (drive technical topics): {', '.join(result['jd_keywords'])}")
    lines.append(f"- CV keywords (drive experiential questions): {', '.join(result['cv_keywords'])}")
    lines.append("")
    lines.append("## Questions")
    lines.append("")
    for q in result["questions"]:
        lines.append(f"### Q{q['index']} — phase: {q['phase']} | topic: {q['topic']} | difficulty: {q['difficulty']} | source: {q['source']}")
        lines.append("")
        lines.append(f"**Question:** {q['question']}")
        if q["answer"] is not None:
            lines.append("")
            lines.append(f"**Answer used:** {q['answer']}")
            ev = q["evaluation"] or {}
            lines.append(f"**Heuristic relevance score:** {ev.get('relevance_score')}")
        lines.append("")

    with open(md_path, "w", encoding="utf-8") as f:
        f.write("\n".join(lines))

    print(f"\nSaved: {json_path}")
    print(f"Saved: {md_path}")


def main():
    parser = argparse.ArgumentParser(description="Test the interview question generator with pasted CV/JD text.")
    parser.add_argument("--jd", help="Path to a JD text file. If omitted, you'll be prompted to paste JD text.")
    parser.add_argument("--cv", help="Path to a CV text file. If omitted, you'll be prompted to paste CV text.")
    parser.add_argument("--mode", choices=["blind", "simulate", "interactive"], default="simulate",
                         help="How to produce answers for questions 2-10 (default: simulate).")
    parser.add_argument("--label", default=None, help="Name used for the saved output files (default: timestamp).")
    parser.add_argument("--out-dir", default=None, help="Folder to save results in (default: ./question_generation_tests/<timestamp>).")
    args = parser.parse_args()

    if args.jd:
        with open(args.jd, "r", encoding="utf-8") as f:
            jd_text = f.read().strip()
    else:
        jd_text = read_pasted_text("JOB DESCRIPTION (JD)")

    if args.cv:
        with open(args.cv, "r", encoding="utf-8") as f:
            cv_text = f.read().strip()
    else:
        cv_text = read_pasted_text("CV / RESUME")

    if not jd_text or not cv_text:
        print("JD text and CV text must both be non-empty. Aborting.")
        sys.exit(1)

    timestamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    label = args.label or f"test_{timestamp}"
    out_dir = args.out_dir or os.path.join("question_generation_tests", timestamp)

    result = run_test(jd_text, cv_text, args.mode, label)
    save_result(result, out_dir)


if __name__ == "__main__":
    main()

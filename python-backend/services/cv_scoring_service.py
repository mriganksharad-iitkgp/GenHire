import os
import json
import re
import logging
from dotenv import load_dotenv
from typing import Dict, Any, Optional
from services.llm_fallback_service import (
    get_llm_fallback_service,
    LLMAllProvidersExhaustedError,
)

logger = logging.getLogger(__name__)

class CVScoringService:
    """Service for calculating CV-JD matching scores using AI.

    Uses the LLMFallbackService to invoke prompts with automatic
    provider failover (Google → OpenAI → Groq) on quota exhaustion.
    """

    def __init__(self):
        load_dotenv()
        self.llm_service = get_llm_fallback_service()
    def format_cv_details(self, cv_details: Dict[str, Any]) -> str:
        """Format CV details dictionary into readable text for AI processing"""
        if not cv_details:
            return "No CV details provided."
        
        formatted_cv = []
        
        # Personal Information
        personal_info = cv_details.get('personalInfo', {})
        if personal_info:
            formatted_cv.append("=== PERSONAL INFORMATION ===")
            if personal_info.get('fullName'):
                formatted_cv.append(f"Name: {personal_info['fullName']}")
            if personal_info.get('email'):
                formatted_cv.append(f"Email: {personal_info['email']}")
            if personal_info.get('phone'):
                formatted_cv.append(f"Phone: {personal_info['phone']}")
            if personal_info.get('location'):
                formatted_cv.append(f"Location: {personal_info['location']}")
            if personal_info.get('linkedin'):
                formatted_cv.append(f"LinkedIn: {personal_info['linkedin']}")
            if personal_info.get('github'):
                formatted_cv.append(f"GitHub: {personal_info['github']}")
            formatted_cv.append("")
        
        # Professional Summary
        summary = cv_details.get('professionalSummary', '')
        if summary:
            formatted_cv.append("=== PROFESSIONAL SUMMARY ===")
            formatted_cv.append(summary)
            formatted_cv.append("")
        
        # Education
        education = cv_details.get('education', [])
        if education:
            formatted_cv.append("=== EDUCATION ===")
            for edu in education:
                if edu.get('degree') or edu.get('institution'):
                    edu_line = []
                    if edu.get('degree'):
                        edu_line.append(edu['degree'])
                    if edu.get('institution'):
                        edu_line.append(f"at {edu['institution']}")
                    if edu.get('year'):
                        edu_line.append(f"({edu['year']})")
                    if edu.get('gpa'):
                        edu_line.append(f"GPA: {edu['gpa']}")
                    formatted_cv.append(" ".join(edu_line))
                    if edu.get('description'):
                        formatted_cv.append(f"  - {edu['description']}")
            formatted_cv.append("")
        
        # Work Experience
        experience = cv_details.get('workExperience') or cv_details.get('experience', [])
        if experience:
            formatted_cv.append("=== WORK EXPERIENCE ===")
            for exp in experience:
                if exp.get('jobTitle') or exp.get('position') or exp.get('company'):
                    exp_line = []
                    job_title = exp.get('jobTitle') or exp.get('position')
                    if job_title:
                        exp_line.append(job_title)
                    if exp.get('company'):
                        exp_line.append(f"at {exp['company']}")
                    if exp.get('duration'):
                        exp_line.append(f"({exp['duration']})")
                    formatted_cv.append(" ".join(exp_line))
                    if exp.get('description'):
                        formatted_cv.append(f"  - {exp['description']}")
            formatted_cv.append("")
        
        # Skills
        skills = cv_details.get('skills', {})
        if skills:
            formatted_cv.append("=== SKILLS ===")
            if skills.get('technical'):
                formatted_cv.append(f"Technical Skills: {', '.join(skills['technical'])}")
            if skills.get('soft'):
                formatted_cv.append(f"Soft Skills: {', '.join(skills['soft'])}")
            if skills.get('languages'):
                formatted_cv.append(f"Languages: {', '.join(skills['languages'])}")
            formatted_cv.append("")
        
        # Projects
        projects = cv_details.get('projects', [])
        if projects:
            formatted_cv.append("=== PROJECTS ===")
            for project in projects:
                if project.get('title'):
                    formatted_cv.append(f"Project: {project['title']}")
                    if project.get('description'):
                        formatted_cv.append(f"  - {project['description']}")
                    if project.get('technologies'):
                        technologies = project['technologies']
                        if isinstance(technologies, list):
                            technologies = ', '.join(technologies)
                        formatted_cv.append(f"  - Technologies: {technologies}")
                    if project.get('link'):
                        formatted_cv.append(f"  - Link: {project['link']}")
            formatted_cv.append("")
        
        # Certifications
        certifications = cv_details.get('certifications', [])
        if certifications:
            formatted_cv.append("=== CERTIFICATIONS ===")
            for cert in certifications:
                if cert.get('name'):
                    cert_line = [cert['name']]
                    if cert.get('issuer'):
                        cert_line.append(f"by {cert['issuer']}")
                    if cert.get('date'):
                        cert_line.append(f"({cert['date']})")
                    formatted_cv.append(" ".join(cert_line))
            formatted_cv.append("")
        
        # Achievements
        achievements = cv_details.get('achievements', [])
        if achievements:
            formatted_cv.append("=== ACHIEVEMENTS ===")
            for achievement in achievements:
                if achievement.get('title'):
                    formatted_cv.append(f"- {achievement['title']}")
                    if achievement.get('description'):
                        formatted_cv.append(f"  {achievement['description']}")
            formatted_cv.append("")
        
        # Salary Expectations
        salary = cv_details.get('salaryExpectations', {})
        if salary:
            formatted_cv.append("=== SALARY EXPECTATIONS ===")
            if salary.get('expectedSalary'):
                formatted_cv.append(f"Expected Salary: {salary['expectedSalary']}")
            if salary.get('currency'):
                formatted_cv.append(f"Currency: {salary['currency']}")
            formatted_cv.append("")
        
        return "\n".join(formatted_cv)
    
    def format_job_description(self, job_data: Dict[str, Any]) -> str:
        """Format job data dictionary into readable text for AI processing"""
        if not job_data:
            return "No job description provided."
        
        formatted_jd = []
        
        # Basic Job Information
        formatted_jd.append("=== JOB INFORMATION ===")
        if job_data.get('title'):
            formatted_jd.append(f"Job Title: {job_data['title']}")
        if job_data.get('company'):
            formatted_jd.append(f"Company: {job_data['company']}")
        if job_data.get('department'):
            formatted_jd.append(f"Department: {job_data['department']}")
        if job_data.get('location'):
            formatted_jd.append(f"Location: {job_data['location']}")
        if job_data.get('type'):
            formatted_jd.append(f"Employment Type: {job_data['type']}")
        if job_data.get('experience'):
            formatted_jd.append(f"Experience Required: {job_data['experience']}")
        if job_data.get('salary'):
            formatted_jd.append(f"Salary: {job_data['salary']}")
        formatted_jd.append("")
        
        # Job Description
        if job_data.get('description'):
            formatted_jd.append("=== JOB DESCRIPTION ===")
            formatted_jd.append(job_data['description'])
            formatted_jd.append("")
        
        # Required Skills
        skills = job_data.get('skills', [])
        if skills:
            formatted_jd.append("=== REQUIRED SKILLS ===")
            for skill in skills:
                formatted_jd.append(f"- {skill}")
            formatted_jd.append("")
        
        # Responsibilities
        responsibilities = job_data.get('responsibilities', [])
        if responsibilities:
            formatted_jd.append("=== KEY RESPONSIBILITIES ===")
            for responsibility in responsibilities:
                formatted_jd.append(f"- {responsibility}")
            formatted_jd.append("")
        
        # Requirements
        requirements = job_data.get('requirements', [])
        if requirements:
            formatted_jd.append("=== REQUIREMENTS ===")
            for requirement in requirements:
                formatted_jd.append(f"- {requirement}")
            formatted_jd.append("")
        
        # Benefits
        benefits = job_data.get('benefits', [])
        if benefits:
            formatted_jd.append("=== BENEFITS ===")
            for benefit in benefits:
                formatted_jd.append(f"- {benefit}")
            formatted_jd.append("")
        
        return "\n".join(formatted_jd)
    
    def calculate_cv_score_from_text(self, cv_text: str, jd_text: str) -> Dict[str, Any]:
        """
        Calculate CV-JD matching score using raw text (from PDF extraction)
        
        Args:
            cv_text: Raw CV text (extracted from PDF or formatted manually)
            jd_text: Raw JD text (extracted from PDF or formatted manually)
            
        Returns:
            Dictionary containing score_breakdown and total_score
        """
        try:
            if not cv_text or not cv_text.strip():
                return self._get_fallback_score("Empty CV text provided")
            
            if not jd_text or not jd_text.strip():
                return self._get_fallback_score("Empty JD text provided")
            
            input_prompt = self._build_scoring_prompt(cv_text, jd_text)
            
            # Get AI response via fallback service
            result = self.llm_service.invoke(input_prompt)
            
            # Parse and clean response
            response_content = result['content']
            parsed_result = self._parse_ai_response(response_content)
            
            # Attach provider and usage metadata
            usage = result.get('usage') or {}
            parsed_result['usage'] = {
                'prompt_tokens': usage.get('prompt_tokens'),
                'completion_tokens': usage.get('completion_tokens'),
                'usage_source': usage.get('usage_source', 'assumed'),
            }
            parsed_result['provider_used'] = result.get('provider_used')
            parsed_result['model_used'] = result.get('model_used')
            parsed_result['fallback_triggered'] = result.get('fallback_triggered', False)
            
            if parsed_result.get('fallback_triggered'):
                logger.info(
                    f"CV scoring used fallback provider: "
                    f"{parsed_result['provider_used']} ({parsed_result['model_used']})"
                )
            
            return parsed_result
            
        except LLMAllProvidersExhaustedError as e:
            logger.error(f"All LLM providers exhausted for CV scoring: {e}")
            return self._get_fallback_score(f"All providers exhausted: {str(e)[:200]}")
        except Exception as e:
            logger.error(f"Error in CV scoring from text: {str(e)}")
            return self._get_fallback_score(str(e))
    
    def calculate_cv_score(self, cv_details: Dict[str, Any], job_data: Dict[str, Any]) -> Dict[str, Any]:
        """
        Calculate CV-JD matching score using structured data (manual CV entry)
        
        Args:
            cv_details: Structured CV data from manual entry
            job_data: Structured job data
            
        Returns:
            Dictionary containing score_breakdown and total_score
        """
        try:
            # Format inputs
            cv_text = self.format_cv_details(cv_details)
            jd_text = self.format_job_description(job_data)
            
            # Reuse the text-based scorer which has the fallback chain
            return self.calculate_cv_score_from_text(cv_text, jd_text)
            
        except Exception as e:
            logger.error(f"Error in CV scoring: {str(e)}")
            return self._get_fallback_score(str(e))
    
    def _parse_ai_response(self, response_content: str) -> Dict[str, Any]:
        """Parse and clean AI response to extract JSON"""
        try:
            # Clean the response
            cleaned_response = response_content.strip().replace("```json", "").replace("```", "")
            cleaned_response = re.sub(r'(\d+\.?\d*)\s*/\s*\d+', r'\1', cleaned_response)
            
            # Find JSON boundaries
            start_index = cleaned_response.find('{')
            end_index = cleaned_response.rfind('}') + 1
            
            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("Could not find a valid JSON object in the LLM response.", cleaned_response, 0)
            
            json_string = cleaned_response[start_index:end_index]
            parsed_result = json.loads(json_string)
            
            # Validate structure
            if 'score_breakdown' not in parsed_result or 'total_score' not in parsed_result:
                raise ValueError("Invalid response structure")
            
            # Ensure total_score is numeric
            if not isinstance(parsed_result['total_score'], (int, float)):
                parsed_result['total_score'] = 75.0
            
            return parsed_result
            
        except Exception as e:
            print(f"Error parsing AI response: {str(e)}")
            return self._get_fallback_score(f"Parsing error: {str(e)}")
    
    def _build_scoring_prompt(self, cv_text: str, jd_text: str) -> str:
        """Build the CV scoring prompt from CV and JD text."""
        system_prompt = """You are an AI evaluator that compares a candidate's resume with a given job description. 
                        Your task is to assess the technical alignment and compute a score out of 100, along with 
                        a breakdown of the score per category. 

                        You must strictly evaluate based on factual alignment between the candidate's resume 
                        and the job description. Do not hallucinate skills or experience. 
                        If information is missing in the resume, assume it is not present.

                        Scoring should be based only on measurable, technical, and experience-based factors. 
                        Exclude soft skills, leadership, communication, or cultural fit. 

                        Provide your final output in JSON with two keys:
                        1. "score_breakdown": { category: { "score": X, "reasoning": "..."} }
                        2. "total_score": X"""
        
        user_prompt = f"""Compare the following Resume and Job Description. 
                        Use the evaluation rubrics below. Assign a score out of 10 for each category with reasoning, 
                        then compute the total score out of 100. 

                        Resume:
                        {cv_text}

                        Job Description:
                        {jd_text}

                        Rubrics (10 points each):
                        1. **Core Technical Skills** - Match between candidate's listed technical skills and JD requirements (e.g., programming languages, frameworks, tools).
                        2. **Domain Knowledge** - Relevance of past experience or education to the specific industry/domain mentioned in JD.
                        3. **Educational Background** - Alignment of degree(s), specialization, and academic level with JD requirements.
                        4. **Work Experience Relevance** - Years of experience and alignment of roles/projects with JD expectations.
                        5. **Project/Research Experience** - Quality and relevance of academic/industrial projects, internships, or research contributions.
                        6. **Tools & Platforms** - Exposure to databases, cloud services, version control, ML/DL libraries, or other technical platforms required by the JD.
                        7. **Certifications & Training** - Relevant professional certifications, coursework, or specialized training that enhance JD alignment.
                        8. **Publications / Competitions / Achievements** - Evidence of technical depth via papers, hackathons, competitions, or notable technical recognition.
                        9. **Problem-Solving & Analytical Skills** - Evidence from projects, coding competitions, or technical challenges solved.
                        10. **Overall Fit for Role** - Aggregate judgment of how well candidate's background meets technical expectations of the JD.

                        Rules:
                        - Each category gets 0-10 points.
                        - Provide reasoning for each score.
                        - Output in strict JSON format."""
        
        return f"""<s>[INST] <<SYS>>
                        {system_prompt}
                        <</SYS>>
                    {user_prompt} [/INST]"""

    def _get_fallback_score(self, error_message: str) -> Dict[str, Any]:
        """Return fallback score when ALL AI scoring providers fail.
        
        The score is clearly marked as a fallback so downstream logic
        (background_processor) knows this is NOT a real evaluation.
        """
        logger.warning(f"Using fallback CV score due to error: {error_message}")
        return {
            "score_breakdown": None,
            "total_score": None,
            "is_fallback": True,
            "error": error_message,
            "provider_used": None,
            "model_used": None,
            "fallback_triggered": True,
        }

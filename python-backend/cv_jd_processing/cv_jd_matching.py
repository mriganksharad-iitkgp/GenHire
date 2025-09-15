import sys
import os
import time
from llama_parse import LlamaParse
from dotenv import load_dotenv
import google.generativeai as genai
from langchain_google_genai import ChatGoogleGenerativeAI
from fastapi import FastAPI, UploadFile, File, HTTPException
from pydantic import BaseModel
import tempfile
import json, re
from typing import Dict, Any

async def doc_parser(file):
    load_dotenv()
    parser_api_key = os.getenv("parser_api_key")
    if not parser_api_key:
        raise ValueError("parser_api_key not found in .env file")

    parser = LlamaParse(
        api_key=parser_api_key,
        result_type="markdown",
        verbose=True,
    )

    temp_file_path = None
    try:
        # Attempt to clean and parse the response
        with tempfile.NamedTemporaryFile(delete=False, suffix=".pdf") as temp_file:
            content = await file.read()
            temp_file.write(content)
            temp_file_path = temp_file.name
        documents = await parser.aload_data(temp_file_path)
        
        return documents[0].text if documents else ""

    finally:
        # Ensure the temporary file is always deleted, even if an error occurs
        if temp_file_path and os.path.exists(temp_file_path):
            os.remove(temp_file_path)


def build_prompt(system_prompt: str, user_prompt: str):
    return f"""<s>[INST] <<SYS>>
            {system_prompt}
            <</SYS>>
        {user_prompt} [/INST]"""


def similarity_scoring(cv_text,jd_text):
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)

    system_prompt="""You are an AI evaluator that compares a candidate's resume with a given job description. 
                    Your task is to assess the technical alignment and compute a score out of 100, along with 
                    a breakdown of the score per category. 

                    You must strictly evaluate based on factual alignment between the candidate's resume 
                    and the job description. Do not hallucinate skills or experience. 
                    If information is missing in the resume, assume it is not present.

                    Scoring should be based only on measurable, technical, and experience-based factors. 
                    Exclude soft skills, leadership, communication, or cultural fit. 

                    Provide your final output in JSON with two keys:
                    1. "score_breakdown": { category: { "score": X/10, "reasoning": "..."} }
                    2. "total_score": X/100
                    """
    user_prompt=f"""Compare the following Resume and Job Description. 
                    Use the evaluation rubrics below. Assign a score out of 10 for each category with reasoning, 
                    then compute the total score out of 100. 

                    Resume:
                    {cv_text}

                    Job Description:
                    {jd_text}

                    Rubrics (10 points each):
                    1. **Core Technical Skills**-Match between candidate's listed technical skills and JD requirements (e.g., programming languages, frameworks, tools).
                    2. **Domain Knowledge**-Relevance of past experience or education to the specific industry/domain mentioned in JD.
                    3. **Educational Background**-Alignment of degree(s), specialization, and academic level with JD requirements.
                    4. **Work Experience Relevance**-Years of experience and alignment of roles/projects with JD expectations.
                    5. **Project/Research Experience**-Quality and relevance of academic/industrial projects, internships, or research contributions.
                    6. **Tools & Platforms**-Exposure to databases, cloud services, version control, ML/DL libraries, or other technical platforms required by the JD.
                    7. **Certifications & Training**-Relevant professional certifications, coursework, or specialized training that enhance JD alignment.
                    8. **Publications / Competitions / Achievements**-Evidence of technical depth via papers, hackathons, competitions, or notable technical recognition.
                    9. **Problem-Solving & Analytical Skills**-Evidence from projects, coding competitions, or technical challenges solved.
                    10. **Overall Fit for Role**-Aggregate judgment of how well candidate's background meets technical expectations of the JD.

                    Rules:
                    - Each category gets 010 points.
                    - Provide reasoning for each score.
                    - Output in strict JSON format.
                    """

    input_prompt = build_prompt(system_prompt,user_prompt)

    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",google_api_key=GOOGLE_API_KEY,temperature=0.9)

    response = llm.invoke(input_prompt)

    return response.content

def similarity_scoring_text(cv_text: str, jd_text: str):
    """Score CV and JD using text inputs directly"""
    if "GOOGLE_API_KEY" not in os.environ:
        raise ValueError("GOOGLE_API_KEY not found in .env file")
    GOOGLE_API_KEY = os.getenv("GOOGLE_API_KEY")
    genai.configure(api_key=GOOGLE_API_KEY)

    system_prompt="""You are an AI evaluator that compares a candidate's resume with a given job description. 
                    Your task is to assess the technical alignment and compute a score out of 100, along with 
                    a breakdown of the score per category. 

                    You must strictly evaluate based on factual alignment between the candidate's resume 
                    and the job description. Do not hallucinate skills or experience. 
                    If information is missing in the resume, assume it is not present.

                    Scoring should be based only on measurable, technical, and experience-based factors. 
                    Exclude soft skills, leadership, communication, or cultural fit. 

                    Provide your final output in JSON with two keys:
                    1. "score_breakdown": { category: { "score": X, "reasoning": "..."} }
                    2. "total_score": X
                    """
    user_prompt=f"""Compare the following Resume and Job Description. 
                    Use the evaluation rubrics below. Assign a score out of 10 for each category with reasoning, 
                    then compute the total score out of 100. 

                    Resume:
                    {cv_text}

                    Job Description:
                    {jd_text}

                    Rubrics (10 points each):
                    1. **Core Technical Skills**-Match between candidate's listed technical skills and JD requirements (e.g., programming languages, frameworks, tools).
                    2. **Domain Knowledge**-Relevance of past experience or education to the specific industry/domain mentioned in JD.
                    3. **Educational Background**-Alignment of degree(s), specialization, and academic level with JD requirements.
                    4. **Work Experience Relevance**-Years of experience and alignment of roles/projects with JD expectations.
                    5. **Project/Research Experience**-Quality and relevance of academic/industrial projects, internships, or research contributions.
                    6. **Tools & Platforms**-Exposure to databases, cloud services, version control, ML/DL libraries, or other technical platforms required by the JD.
                    7. **Certifications & Training**-Relevant professional certifications, coursework, or specialized training that enhance JD alignment.
                    8. **Publications / Competitions / Achievements**-Evidence of technical depth via papers, hackathons, competitions, or notable technical recognition.
                    9. **Problem-Solving & Analytical Skills**-Evidence from projects, coding competitions, or technical challenges solved.
                    10. **Overall Fit for Role**-Aggregate judgment of how well candidate's background meets technical expectations of the JD.

                    Rules:
                    - Each category gets 0-10 points.
                    - Provide reasoning for each score.
                    - Output in strict JSON format.
                    """

    input_prompt = build_prompt(system_prompt,user_prompt)

    llm = ChatGoogleGenerativeAI(model="gemini-1.5-flash-latest",google_api_key=GOOGLE_API_KEY,temperature=0.3)

    response = llm.invoke(input_prompt)

    return response.content

# Pydantic models for text-based scoring
class TextScoringRequest(BaseModel):
    cv_text: str
    jd_text: str

app = FastAPI(
    title="CV-JD Scoring API",
    description="An API to parse and score a CV against a Job Description."
)

@app.post("/score/")
async def score_cv_jd(cv: UploadFile = File(...), jd: UploadFile = File(...)):
    try:

        print(f"Parsing CV: {cv.filename}")
        parsed_cv = await doc_parser(cv)
        
        print(f"Parsing JD: {jd.filename}")
        parsed_jd = await doc_parser(jd)
        
        if not parsed_cv or not parsed_jd:
            raise HTTPException(status_code=400, detail="Failed to parse one or both documents.")

        print("Scoring documents...")
        score_response = similarity_scoring(parsed_cv, parsed_jd)

        try:

            cleaned_response = score_response.strip().replace("```json", "").replace("```", "")
            cleaned_response = re.sub(r'(\d+\.?\d*)\s*/\s*\d+', r'\1', cleaned_response)

            start_index = cleaned_response.find('{')
            end_index = cleaned_response.rfind('}') + 1
            
            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("Could not find a valid JSON object in the LLM response.", cleaned_response, 0)
                
            json_string = cleaned_response[start_index:end_index]
            return json.loads(json_string)
        
        except Exception as e:
            print(f"!!! ERROR DURING CLEANING: {e} !!!")
            return {"error": "An error occurred while processing the LLM output.", "raw_output": score_response}
        
    except json.JSONDecodeError as e:
        # If parsing fails, return the raw text for debugging
        print(f"!!! FAILED TO PARSE JSON: {e} !!!")
        print(f"--- String after cleaning: {json_string} ---")
        return {"error": "Failed to parse LLM output as JSON.", "raw_output": score_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.post("/score-text/")
async def score_cv_jd_text(request: TextScoringRequest):
    """Score CV and JD using text inputs directly"""
    try:
        print("Scoring documents using text inputs...")
        score_response = similarity_scoring_text(request.cv_text, request.jd_text)

        try:
            cleaned_response = score_response.strip().replace("```json", "").replace("```", "")
            cleaned_response = re.sub(r'(\d+\.?\d*)\s*/\s*\d+', r'\1', cleaned_response)

            start_index = cleaned_response.find('{')
            end_index = cleaned_response.rfind('}') + 1
            
            if start_index == -1 or end_index == 0:
                raise json.JSONDecodeError("Could not find a valid JSON object in the LLM response.", cleaned_response, 0)
                
            json_string = cleaned_response[start_index:end_index]
            return json.loads(json_string)
        
        except Exception as e:
            print(f"!!! ERROR DURING CLEANING: {e} !!!")
            return {"error": "An error occurred while processing the LLM output.", "raw_output": score_response}
        
    except json.JSONDecodeError as e:
        print(f"!!! FAILED TO PARSE JSON: {e} !!!")
        return {"error": "Failed to parse LLM output as JSON.", "raw_output": score_response}

    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))


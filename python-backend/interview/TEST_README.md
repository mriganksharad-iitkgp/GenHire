# Interactive Interview Test System

A comprehensive testing interface for experiencing the natural conversation flow of the AI interview system.

## Features

- **🎯 Interactive Q&A**: Real-time conversation with the AI interviewer
- **🧠 Smart Adaptation**: Questions adapt based on your answers and skill level
- **📊 Live Feedback**: Get immediate evaluation and scores for your responses
- **🔄 Natural Flow**: Experience the improved conversation flow with smooth topic transitions
- **📈 Progress Tracking**: See your progress and estimated remaining questions
- **🎉 Complete Evaluation**: Get detailed final assessment and recommendations

## Quick Start

### Option 1: Simple Launch (Recommended)

```bash
# Windows
run_test.bat

# Linux/Mac
python run_test.py
```

### Option 2: Direct Module Run

```bash
cd python-backend
python -m interview.test
```

### Option 3: With Custom Files

```bash
python -m interview.test --cv path/to/your/resume.pdf --jd path/to/job/description.pdf
```

## Usage Options

### Interactive Mode (Default)

Experience a full interview with real-time Q&A:

```bash
python -m interview.test
```

### Demo Mode

Quick automated demo with sample answers:

```bash
python -m interview.test --demo
```

### Custom Configuration

```bash
python -m interview.test \
    --cv your_resume.pdf \
    --jd job_description.pdf \
    --provider openai \
    --model gpt-4 \
    --api-key YOUR_API_KEY
```

## Prerequisites

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. API Key Setup

Set up your LLM provider API key:

**Option A: Environment Variable**

```bash
# For Groq (default)
export GROQ_API_KEY="your_groq_api_key"

# For OpenAI
export OPENAI_API_KEY="your_openai_api_key"
```

**Option B: Command Line**

```bash
python -m interview.test --api-key YOUR_API_KEY
```

**Option C: Interactive Input**
The script will prompt you for the API key if not found.

### 3. Document Files

The system needs PDF files for CV and Job Description:

- **Sample files**: Available in `uploads/cv/` and `uploads/jd/`
- **Custom files**: Use `--cv` and `--jd` parameters
- **Supported formats**: PDF only

## Command Line Options

```
Options:
  --cv CV                Path to CV file (PDF)
  --jd JD                Path to Job Description file (PDF)
  --reference [REFERENCE ...]  Reference document paths
  --provider {groq,openai}      LLM provider to use (default: groq)
  --model MODEL          Model name (e.g., gpt-4, llama-3.3-70b-versatile)
  --demo                 Run automated demo instead of interactive mode
  --api-key API_KEY      API key for LLM provider
  -h, --help            Show help message
```

## Interactive Experience

### What to Expect

1. **🚀 Session Initialization**

   - System analyzes your CV and job description
   - Identifies key topics to cover
   - Estimates interview duration

2. **❓ Dynamic Questioning**

   - Questions adapt based on your responses
   - Natural conversation flow with follow-ups
   - Smooth transitions between topics

3. **💡 Real-time Feedback**

   - Immediate scores and feedback
   - Progress tracking
   - Performance insights

4. **📊 Final Evaluation**
   - Overall score and recommendation
   - Strengths and improvement areas
   - Detailed feedback

### Sample Session Flow

```
📋 Starting Interview Session
📄 CV: uploads/cv/resume.pdf
📋 Job Description: uploads/jd/job_description.pdf
🎯 Topics to cover: Python, Machine Learning, System Design
⏱️  Estimated duration: 25 minutes

❓ Question 1:
==================================================
What are the key differences between lists and tuples in Python?
==================================================

🎤 Your Answer: Lists are mutable while tuples are immutable...

💡 Feedback:
   Score: 8.5/10
   Excellent explanation of mutability differences...

📊 Progress: 1 asked, ~7 remaining
```

## Tips for Best Experience

### 1. Answer Naturally

- Provide detailed, thoughtful responses
- Share real examples from your experience
- Don't worry about "perfect" answers

### 2. Engage Actively

- Ask clarifying questions if needed
- Mention relevant projects or experiences
- Show your thought process

### 3. Use the Features

- Type 'quit' to exit early if needed
- Review feedback after each answer
- Pay attention to topic transitions

## Troubleshooting

### Common Issues

**API Key Problems**

```bash
❌ Error: API key is required
```

Solution: Set environment variable or use `--api-key` parameter

**File Not Found**

```bash
❌ CV file not found: path/to/file.pdf
```

Solution: Check file path and ensure PDF format

**Module Import Error**

```bash
ModuleNotFoundError: No module named 'interview'
```

Solution: Run from the `python-backend` directory

**Dependencies Missing**

```bash
ModuleNotFoundError: No module named 'groq'
```

Solution: Install requirements: `pip install -r requirements.txt`

### Getting Help

1. Check the help command: `python -m interview.test --help`
2. Verify file paths and permissions
3. Ensure all dependencies are installed
4. Check API key validity

## Advanced Usage

### Custom Configuration

Create custom interview configurations:

```python
from interview.test import InterviewTester

tester = InterviewTester(
    api_key="your_key",
    llm_provider="openai",
    model="gpt-4"
)
```

### Integration with Other Systems

The test system uses the same API as the production system, making it perfect for:

- Testing new features
- Demonstrating the interview flow
- Training purposes
- Quality assurance

## Contributing

To improve the test system:

1. Add new test scenarios
2. Enhance the user interface
3. Add more evaluation metrics
4. Improve error handling

See the main project README for contribution guidelines.

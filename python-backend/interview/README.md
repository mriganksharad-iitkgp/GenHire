# Interview Module

A comprehensive, modular interview system with support for multiple LLM providers, document processing, and intelligent evaluation.

## Features

- **Multi-LLM Support**: Works with Groq and OpenAI
- **Document Processing**: Extract and analyze CVs, job descriptions, and reference materials
- **Intelligent Question Generation**: Generate balanced sets of technical, behavioral, and situational questions
- **Real-time Evaluation**: Score answers on relevance, technical accuracy, and communication
- **Session Management**: Handle multiple concurrent interview sessions
- **Flexible Configuration**: Easily customize behavior for different use cases

## Quick Start

```python
from interview.api import create_groq_interview

# Initialize with your API key
interview_system = create_groq_interview(api_key="your-groq-api-key")

# Start an interview
session = interview_system.start_interview(
    cv_file_path="candidate_cv.pdf",
    job_description_path="job_description.pdf",
    reference_documents=["technical_guide.pdf"]
)

# Get questions and submit answers
question_result = interview_system.get_question(session["session_id"])
answer_result = interview_system.submit_answer(
    session["session_id"],
    question_result["question"],
    "My answer here"
)
```

## Architecture

### Core Components

- **LLM Module** (`llm/`): Abstracted LLM providers with factory pattern
- **Document Module** (`document/`): PDF/text processing and analysis
- **Evaluation Module** (`evaluation/`): Answer scoring and feedback
- **Core Module** (`core/`): Session management and question generation
- **Configuration** (`config/`): Centralized settings and enums

### Design Principles

1. **Single Responsibility**: Each module has a clear, focused purpose
2. **Dependency Injection**: Components are loosely coupled
3. **Factory Pattern**: Easy swapping of LLM providers
4. **Configuration-Driven**: Behavior controlled through config objects
5. **Error Handling**: Graceful degradation and informative error messages

## Installation

```bash
pip install -r requirements.txt
```

## Configuration

### Basic Configuration

```python
from interview.config.settings import InterviewConfig, LLMConfig, LLMProvider

# Interview settings
interview_config = InterviewConfig(
    max_questions=8,
    min_questions=4,
    similarity_threshold=0.7
)

# LLM settings
llm_config = LLMConfig(
    provider=LLMProvider.GROQ,
    model_name="llama-3.3-70b-versatile",
    api_key="your-api-key",
    temperature=0.7
)
```

### Supported LLM Providers

1. **Groq**: Fast inference for Llama models
2. **OpenAI**: GPT-3.5/GPT-4 models
3. **Extensible**: Easy to add new providers

## Usage Examples

### Basic Interview Flow

```python
from interview.api import InterviewAPI
from interview.config.settings import LLMProvider

# Initialize
api = InterviewAPI(
    llm_provider=LLMProvider.GROQ,
    model_name="llama-3.3-70b-versatile",
    api_key="your-key"
)

# Start interview
session = api.start_interview("cv.pdf", "jd.pdf")
session_id = session["session_id"]

# Interview loop
while True:
    # Get next question
    question_result = api.get_question(session_id)
    if "error" in question_result:
        break

    question = question_result["question"]
    print(f"Q: {question}")

    # Get answer (from user input)
    answer = input("A: ")

    # Submit and evaluate
    result = api.submit_answer(session_id, question, answer)

    # Show evaluation
    eval_data = result["current_evaluation"]
    print(f"Score: {eval_data['overall_score']:.2f}")

    # Check if complete
    if result.get("interview_complete"):
        print("Interview finished!")
        print(result["final_evaluation"])
        break
```

### Custom Question Generation

```python
from interview.core.question_generator import QuestionGenerator
from interview.config.settings import QuestionType

# Initialize with LLM
generator = QuestionGenerator(llm)

# Generate specific question types
technical_questions = generator.generate_questions_by_type(
    resume_sections,
    QuestionType.TECHNICAL,
    count=5
)

# Generate balanced question set
balanced_questions = generator.generate_balanced_question_set(
    resume_sections,
    total_questions=8
)
```

### Advanced Evaluation

```python
from interview.evaluation.scorer import EvaluationScorer

scorer = EvaluationScorer(llm)

result = scorer.evaluate_answer(
    question="What is machine learning?",
    user_answer="ML is a way for computers to learn patterns from data",
    expected_answer="Machine learning is a subset of AI...",
    context="Additional context from documents"
)

print(f"Relevance: {result.relevance_score}")
print(f"Technical Accuracy: {result.technical_accuracy_score}")
print(f"Communication: {result.communication_score}")
print(f"Feedback: {result.feedback}")
```

## API Reference

### InterviewAPI

Main interface for the interview system.

#### Methods

- `start_interview(cv_path, jd_path, reference_docs)`: Start new session
- `get_question(session_id)`: Get next question
- `submit_answer(session_id, question, answer)`: Submit answer and get evaluation
- `get_session_status(session_id)`: Get session progress
- `end_interview(session_id)`: End session and get final evaluation

### Configuration Classes

- `InterviewConfig`: Interview behavior settings
- `LLMConfig`: LLM provider configuration
- `DocumentConfig`: Document processing settings
- `EvaluationConfig`: Evaluation weights and thresholds

## Extending the System

### Adding New LLM Providers

```python
from interview.llm.base import BaseLLM, LLMResponse

class CustomLLM(BaseLLM):
    def complete(self, prompt: str) -> LLMResponse:
        # Your implementation
        return LLMResponse(text="response")

    def is_available(self) -> bool:
        # Check availability
        return True

# Register with factory
from interview.llm.factory import LLMFactory
from interview.config.settings import LLMProvider

LLMFactory.register_provider(LLMProvider.CUSTOM, CustomLLM)
```

### Custom Evaluation Metrics

```python
class CustomScorer(EvaluationScorer):
    def calculate_custom_metric(self, answer: str) -> float:
        # Your custom scoring logic
        return score
```

## Best Practices

1. **Error Handling**: Always check for "error" keys in responses
2. **Resource Management**: Use appropriate timeouts and limits
3. **Configuration**: Use config objects rather than hardcoded values
4. **Testing**: Test with various document types and content
5. **Security**: Never expose API keys in code

## Troubleshooting

### Common Issues

1. **Import Errors**: Install all required dependencies
2. **API Key Issues**: Ensure correct environment variables are set
3. **File Not Found**: Verify file paths are absolute and files exist
4. **Model Errors**: Check model names are correct for the provider

### Performance Tips

1. **Caching**: Reuse models across sessions when possible
2. **Batch Processing**: Process multiple questions at once when suitable
3. **Resource Limits**: Set appropriate timeouts and token limits
4. **Memory Management**: Clean up completed sessions

## Contributing

The modular architecture makes it easy to contribute:

1. **New LLM Providers**: Implement `BaseLLM` interface
2. **Document Formats**: Extend `DocumentProcessor`
3. **Evaluation Metrics**: Add methods to `EvaluationScorer`
4. **Question Types**: Extend `QuestionGenerator`

## License

[Your License Here]

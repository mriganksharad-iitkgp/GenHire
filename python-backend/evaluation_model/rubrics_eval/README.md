# Rubrics Evaluation System 📊

> An advanced, modular evaluation system for generating dynamic rubrics, scoring student answers, and providing detailed feedback using state-of-the-art language models.

[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)
[![OpenAI](https://img.shields.io/badge/OpenAI-GPT--4-green.svg)](https://openai.com/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

## 🌟 Features

- **🎯 Dynamic Rubric Generation**: AI-powered creation of context-specific grading criteria
- **📝 Intelligent Answer Evaluation**: Multi-dimensional scoring with detailed feedback
- **📈 Answer Spectrum Generation**: Create test datasets with varying quality levels
- **🔍 Advanced Analytics**: Comprehensive evaluation metrics and insights
- **🛠️ Modular Architecture**: Clean, extensible design with clear separation of concerns
- **📊 Data Processing**: Robust handling of CSV, JSON, and pandas DataFrames
- **📈 Visualization Tools**: Generate insightful plots and evaluation charts
- **⚙️ Configuration Management**: Centralized config with environment variable support

## 🚀 Quick Start

### Basic Single Answer Evaluation

```python
from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem

# Initialize the evaluation system
eval_system = EvaluationSystem()

# Evaluate a single answer
question = "Explain the bias-variance tradeoff in machine learning"
student_answer = """
The bias-variance tradeoff is a fundamental concept in machine learning that deals
with balancing model complexity. High bias models are too simple and underfit,
while high variance models are too complex and overfit to training data.
"""

# Get evaluation score and detailed breakdown
score, evaluation_details = eval_system.evaluate_single_answer(question, student_answer)

print(f"Overall Score: {score:.2f}/100")
for detail in evaluation_details:
    print(f"• {detail['rubric']}: {detail['score']:.1f}/100")
```

### Batch Processing with Answer Spectrum

```python
# Generate a spectrum of answers for testing
question = "What is overfitting in machine learning?"

titles, answers = eval_system.generate_answer_spectrum(
    question=question,
    spectrum_type="balanced"  # or "relevance"
)

# Evaluate the entire spectrum
results = eval_system.evaluate_answer_spectrum(question, "balanced")

print(f"Generated {len(answers)} test answers")
print(f"Score range: {min(results['scores']):.1f} - {max(results['scores']):.1f}")
```

## 🏗️ Architecture

### System Overview

```
┌─────────────────────────────────────────────────────────────┐
│                 Rubrics Evaluation System                   │
├─────────────────────────────────────────────────────────────┤
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │   Rubric    │  │   Answer    │  │   Answer    │         │
│  │ Generator   │  │ Evaluator   │  │ Generator   │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
│         │                 │                 │               │
│  ┌─────────────┐  ┌─────────────┐  ┌─────────────┐         │
│  │    Data     │  │ Evaluation  │  │Visualization│         │
│  │ Processor   │  │   System    │  │   Utils     │         │
│  └─────────────┘  └─────────────┘  └─────────────┘         │
└─────────────────────────────────────────────────────────────┘
```

### Core Components

#### 🎯 Evaluation System (`evaluation_system.py`)

**Main orchestrator that coordinates all evaluation components**

```python
class EvaluationSystem:
    def evaluate_single_answer(question: str, student_answer: str) -> Tuple[float, List[Dict]]
    def generate_answer_spectrum(question: str, spectrum_type: str) -> Tuple[List[str], List[str]]
    def evaluate_answer_spectrum(question: str, spectrum_type: str) -> Dict[str, Any]
    def process_dataset(file_path: str, question_column: str) -> Dict[str, Any]
```

#### 📋 Rubric Generator (`rubric_generator.py`)

**Generates context-specific evaluation criteria using LLMs**

```python
class RubricGenerator:
    def generate_rubrics(question: str, num_rubrics: int = 5) -> List[str]
    def _create_rubric_prompt(question: str, num_rubrics: int) -> str
```

**Example Generated Rubrics:**

- _"Demonstrates clear understanding of core concepts"_
- _"Provides relevant examples and applications"_
- _"Uses appropriate technical terminology"_
- _"Shows logical reasoning and problem-solving approach"_
- _"Addresses all parts of the question comprehensively"_

#### 📝 Answer Evaluator (`answer_evaluator.py`)

**Scores student answers against generated rubrics**

```python
class AnswerEvaluator:
    def evaluate_answer(question: str, student_answer: str, rubrics: List[str]) -> Tuple[float, List[Dict]]
    def evaluate_single_rubric(student_answer: str, question: str, rubric_item: str) -> float
```

**Evaluation Process:**

1. Score each rubric criterion individually (1-100 scale)
2. Calculate weighted average across all criteria
3. Provide detailed breakdown per criterion
4. Generate contextual feedback

#### 🔄 Answer Generator (`answer_generator.py`)

**Creates test datasets with varying answer qualities**

```python
class AnswerGenerator:
    def generate_balanced_spectrum(question: str) -> Tuple[List[str], List[str]]
    def generate_sequential_relevance_spectrum(question: str) -> Tuple[List[str], List[str]]
```

**Answer Quality Levels:**

- **Excellent**: Comprehensive, accurate, well-structured
- **Good**: Solid understanding with minor gaps
- **Average**: Basic concepts with some inaccuracies
- **Poor**: Significant misunderstandings
- **Irrelevant**: Off-topic or nonsensical

#### 📊 Data Processor (`data_processor.py`)

**Handles data loading, processing, and export**

```python
class DataProcessor:
    def load_dataset(file_path: str) -> pd.DataFrame
    def save_to_csv(data: Dict, file_path: str) -> None
    def save_to_json(data: Dict, file_path: str) -> None
    def process_evaluation_results(results: List[Dict]) -> pd.DataFrame
```

#### 📈 Visualization Utils (`visualization.py`)

**Creates insightful charts and plots**

```python
class VisualizationUtils:
    def plot_score_distribution(scores: List[float], title: str) -> None
    def plot_rubric_breakdown(evaluation_details: List[Dict]) -> None
    def plot_spectrum_analysis(spectrum_results: Dict) -> None
```

#### ⚙️ Configuration (`config.py`)

**Centralized configuration management**

```python
class Config:
    # OpenAI Configuration
    OPENAI_API_KEY: str
    EVALUATION_MODEL: str = "gpt-4"
    EVALUATION_TEMPERATURE: float = 0.3

    # Generation Settings
    DEFAULT_NUM_RUBRICS: int = 5
    DEFAULT_SPECTRUM_SIZE: int = 5

    # Scoring Parameters
    MIN_SCORE: float = 1.0
    MAX_SCORE: float = 100.0
```

## 📁 Project Structure

```
evaluation_model/
├── __init__.py                     # Package initialization
└── rubrics_eval/                   # Main evaluation package
    ├── __init__.py                 # Subpackage initialization
    ├── config.py                   # Configuration management
    ├── evaluation_system.py        # 🎯 Main orchestrator
    ├── rubric_generator.py         # 📋 Rubric generation
    ├── answer_evaluator.py         # 📝 Answer evaluation
    ├── answer_generator.py         # 🔄 Test answer generation
    ├── data_processor.py           # 📊 Data handling
    ├── visualization.py            # 📈 Plotting utilities
    ├── requirements.txt            # Dependencies
    └── README.md                   # This documentation
```

## 🔧 Configuration & Setup

### Environment Setup

```bash
# Install dependencies
pip install -r requirements.txt

# Set up OpenAI API key
export OPENAI_API_KEY="your-openai-api-key-here"

# Optional: Configure model settings
export EVALUATION_MODEL="gpt-4"
export EVALUATION_TEMPERATURE="0.3"
```

### Configuration Options

```python
from evaluation_model.rubrics_eval.config import Config

# Load from environment
Config.load_from_environment()

# Validate configuration
Config.validate()

# Access configuration
print(f"Using model: {Config.EVALUATION_MODEL}")
print(f"Temperature: {Config.EVALUATION_TEMPERATURE}")
```

## 📊 Usage Examples

### 1. Single Answer Evaluation with Custom Rubrics

```python
from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem

eval_system = EvaluationSystem()

# Custom rubrics for specific evaluation criteria
custom_rubrics = [
    "Demonstrates understanding of algorithmic complexity",
    "Provides correct Big O notation analysis",
    "Explains time vs space tradeoffs clearly",
    "Gives relevant examples or use cases"
]

question = "Analyze the time complexity of quicksort algorithm"
answer = "Quicksort has O(n log n) average case but O(n²) worst case..."

# Evaluate with custom rubrics
score, details = eval_system.evaluate_single_answer(
    question=question,
    student_answer=answer,
    rubrics=custom_rubrics
)

print(f"Overall Score: {score:.1f}/100")
for detail in details:
    print(f"• {detail['rubric'][:50]}...: {detail['score']:.1f}/100")
```

### 2. Batch Dataset Processing

```python
import pandas as pd

# Prepare dataset
questions_df = pd.DataFrame({
    'Question': [
        "What is machine learning?",
        "Explain neural networks",
        "Define overfitting"
    ],
    'Student_Answer': [
        "ML is AI that learns from data...",
        "Neural networks are inspired by brain...",
        "Overfitting happens when model..."
    ]
})

# Process entire dataset
results = eval_system.process_dataset(
    data=questions_df,
    question_column='Question',
    answer_column='Student_Answer'
)

# Access results
print(f"Processed {len(results['evaluations'])} answers")
print(f"Average score: {results['average_score']:.1f}")
print(f"Score distribution: {results['score_statistics']}")
```

### 3. Answer Quality Spectrum Analysis

```python
# Generate answer spectrum for analysis
question = "Explain the concept of gradient descent"

# Generate balanced spectrum
titles, answers = eval_system.generate_answer_spectrum(
    question=question,
    spectrum_type="balanced"
)

# Evaluate the spectrum
spectrum_results = eval_system.evaluate_answer_spectrum(
    question=question,
    spectrum_type="balanced"
)

# Analyze results
scores = spectrum_results['scores']
print(f"Quality Spectrum Analysis:")
for i, (title, score) in enumerate(zip(titles, scores)):
    print(f"{i+1}. {title}: {score:.1f}/100")

# Visualize spectrum
eval_system.visualization.plot_spectrum_analysis(spectrum_results)
```

### 4. Advanced Analytics and Visualization

```python
# Generate comprehensive evaluation report
question = "Describe the differences between supervised and unsupervised learning"

# Get multiple evaluation perspectives
results = []
for spectrum_type in ["balanced", "relevance"]:
    spectrum_results = eval_system.evaluate_answer_spectrum(question, spectrum_type)
    results.append(spectrum_results)

# Create visualization dashboard
eval_system.visualization.plot_score_distribution(
    scores=results[0]['scores'],
    title="Balanced Spectrum Score Distribution"
)

eval_system.visualization.plot_rubric_breakdown(
    evaluation_details=results[0]['evaluation_details']
)
```

## 🔍 API Reference

### EvaluationSystem Class

```python
class EvaluationSystem:
    """Main evaluation system orchestrator."""

    def __init__()
        """Initialize with default configuration."""

    def evaluate_single_answer(
        question: str,
        student_answer: str,
        rubrics: Optional[List[str]] = None
    ) -> Tuple[float, List[Dict[str, Any]]]
        """
        Evaluate a single answer against rubrics.

        Args:
            question: The question being answered
            student_answer: Student's response
            rubrics: Optional custom rubrics (auto-generated if None)

        Returns:
            Tuple of (average_score, detailed_evaluations)
        """

    def generate_answer_spectrum(
        question: str,
        spectrum_type: str = "balanced"
    ) -> Tuple[List[str], List[str]]
        """
        Generate test answers with varying quality levels.

        Args:
            question: Question to generate answers for
            spectrum_type: "balanced" or "relevance"

        Returns:
            Tuple of (answer_titles, generated_answers)
        """

    def evaluate_answer_spectrum(
        question: str,
        spectrum_type: str = "balanced"
    ) -> Dict[str, Any]
        """
        Generate and evaluate a complete answer spectrum.

        Returns:
            Complete evaluation results with scores and analytics
        """
```

### Response Formats

#### Single Answer Evaluation Response

```python
# Returns: (score, evaluation_details)
score = 78.5  # float, average score 0-100

evaluation_details = [
    {
        "rubric": "Demonstrates clear understanding of core concepts",
        "score": 85.0
    },
    {
        "rubric": "Provides relevant examples and applications",
        "score": 72.0
    }
    # ... more rubric evaluations
]
```

#### Spectrum Evaluation Response

```python
{
    "question": "What is machine learning?",
    "rubrics": ["rubric1", "rubric2", ...],
    "titles": ["Excellent Answer", "Good Answer", ...],
    "answers": ["Comprehensive response...", "Basic response...", ...],
    "scores": [92.5, 78.2, 64.8, 45.1, 23.7],
    "evaluation_details": [
        [{"rubric": "...", "score": 95}, ...],  # Details for answer 1
        [{"rubric": "...", "score": 80}, ...],  # Details for answer 2
        # ... more detailed evaluations
    ],
    "average_score": 60.86,
    "score_statistics": {
        "min": 23.7,
        "max": 92.5,
        "std": 24.3,
        "median": 64.8
    }
}
```

## 🧪 Testing & Validation

### Running Tests

```bash
# Basic functionality test
python -c "
from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem
eval_system = EvaluationSystem()
score, details = eval_system.evaluate_single_answer(
    'What is AI?',
    'AI is artificial intelligence that mimics human thinking.'
)
print(f'Test Score: {score:.1f}/100')
print('✅ System working correctly!')
"
```

### Validation Examples

```python
# Test rubric generation
from evaluation_model.rubrics_eval.rubric_generator import RubricGenerator

generator = RubricGenerator()
rubrics = generator.generate_rubrics("Explain machine learning")

print("Generated Rubrics:")
for i, rubric in enumerate(rubrics, 1):
    print(f"{i}. {rubric}")

# Test answer evaluation
from evaluation_model.rubrics_eval.answer_evaluator import AnswerEvaluator

evaluator = AnswerEvaluator()
score, details = evaluator.evaluate_answer(
    question="What is Python?",
    student_answer="Python is a programming language known for simplicity.",
    rubrics=["Identifies Python correctly", "Mentions key characteristics"]
)

print(f"Evaluation Score: {score:.1f}/100")
```

## 🔧 Integration with Interview System

The rubrics evaluation system integrates seamlessly with the interview module:

```python
# In interview/core/session_manager.py
from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem

class InterviewSessionManager:
    def __init__(self, config, llm_config):
        # Initialize evaluation system
        self.evaluation_system = EvaluationSystem()

    def submit_answer(self, session_id, question, answer):
        # Use rubrics evaluation for scoring
        score, details = self.evaluation_system.evaluate_single_answer(
            question=question,
            student_answer=answer
        )

        # Convert to interview format
        evaluation = self._convert_single_score_to_standard_format(
            score, question, answer
        )

        return {
            "current_evaluation": evaluation,
            "score_breakdown": {d['rubric']: d['score'] for d in details}
        }
```

## 🚦 Error Handling

```python
try:
    score, details = eval_system.evaluate_single_answer(question, answer)
except Exception as e:
    print(f"Evaluation failed: {e}")
    # Fallback scoring mechanism
    score = 50.0  # Default neutral score
    details = [{"rubric": "Error in evaluation", "score": 50.0}]
```

## 🛠️ Troubleshooting

### Common Issues

1. **API Key Not Set**

   ```bash
   export OPENAI_API_KEY="your-key-here"
   python -c "from evaluation_model.rubrics_eval.config import Config; Config.load_from_environment(); print('✅ API key loaded')"
   ```

2. **Import Errors**

   ```bash
   # Ensure you're in the python-backend directory
   cd python-backend
   python -c "from evaluation_model.rubrics_eval.evaluation_system import EvaluationSystem; print('✅ Import successful')"
   ```

3. **Model Response Issues**
   ```python
   # Check model configuration
   from evaluation_model.rubrics_eval.config import Config
   print(f"Model: {Config.EVALUATION_MODEL}")
   print(f"Temperature: {Config.EVALUATION_TEMPERATURE}")
   ```

### Debug Mode

```python
import logging
logging.basicConfig(level=logging.DEBUG)

# Run with detailed logging
eval_system = EvaluationSystem()
```

## 🚀 Performance Optimization

### Batch Processing Tips

```python
# For large datasets, process in chunks
def process_large_dataset(questions, answers, chunk_size=10):
    results = []
    for i in range(0, len(questions), chunk_size):
        chunk_questions = questions[i:i+chunk_size]
        chunk_answers = answers[i:i+chunk_size]

        # Process chunk
        chunk_results = []
        for q, a in zip(chunk_questions, chunk_answers):
            score, details = eval_system.evaluate_single_answer(q, a)
            chunk_results.append({"score": score, "details": details})

        results.extend(chunk_results)
        print(f"Processed {min(i+chunk_size, len(questions))}/{len(questions)} items")

    return results
```

### Caching Strategies

```python
import functools

@functools.lru_cache(maxsize=100)
def cached_rubric_generation(question):
    """Cache rubrics for frequently asked questions."""
    return eval_system.rubric_generator.generate_rubrics(question)
```

## 🤝 Contributing

1. **Fork the repository**
2. **Create a feature branch**: `git checkout -b feature/evaluation-enhancement`
3. **Commit changes**: `git commit -m 'Add enhanced evaluation metrics'`
4. **Push to branch**: `git push origin feature/evaluation-enhancement`
5. **Open a Pull Request**

### Development Guidelines

- Follow PEP 8 style guidelines
- Add comprehensive type hints
- Include detailed docstrings
- Write unit tests for new functionality
- Update README for any API changes
- Ensure backward compatibility

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

## 🔗 Related Modules

- **[Interview Module](../../interview/README.md)**: Main interview system that uses this evaluation module
- **[React Frontend](../../../react-frontend/README.md)**: Web interface for the complete interview system

---

_Built with ❤️ for intelligent educational assessment_

### 4. Visualization

```python
# Generate plots from results
eval_system.generate_visualizations("evaluation_results.csv")
```

## Configuration

The system supports various configuration options through the `Config` class:

```python
from config import Config

# Load configuration
Config.load_from_environment()

# Access configuration values
print(Config.RUBRIC_GENERATION_MODEL)  # "gpt-4o"
print(Config.EVALUATION_MODEL)         # "gpt-4o-mini"
```

## API Reference

### EvaluationSystem

Main orchestrator class that combines all components.

**Methods:**

- `evaluate_single_answer(question, answer, rubrics=None)`: Evaluate one answer
- `generate_answer_spectrum(question, spectrum_type)`: Generate test answers
- `evaluate_answer_spectrum(question, spectrum_type)`: Generate and evaluate answers
- `process_dataset(dataset_path, question_column)`: Process entire datasets
- `save_results_to_csv(results, output_path)`: Save results to CSV
- `generate_visualizations(csv_path)`: Create plots

### RubricGenerator

Generates grading rubrics for questions.

**Methods:**

- `generate_rubrics(question)`: Generate rubrics for a single question
- `generate_rubrics_batch(questions)`: Generate rubrics for multiple questions

### AnswerEvaluator

Evaluates student answers against rubrics.

**Methods:**

- `evaluate_single_rubric(answer, question, rubric_item)`: Score against one rubric
- `evaluate_answer(question, answer, rubrics)`: Score against all rubrics
- `evaluate_multiple_answers(question, answers, rubrics)`: Score multiple answers

### AnswerGenerator

Generates test answer spectrums for evaluation.

**Methods:**

- `generate_balanced_spectrum(question)`: Generate 6 answers with smooth quality degradation
- `generate_sequential_relevance_spectrum(question)`: Generate relevance-based spectrum

## Environment Variables

- `OPENAI_API_KEY`: Required. Your OpenAI API key
- `LANGCHAIN_API_KEY`: Optional. For LangChain tracing
- `LANGCHAIN_TRACING_V2`: Optional. Enable LangChain tracing
- `LANGCHAIN_ENDPOINT`: Optional. LangChain endpoint URL

## Error Handling

The system includes comprehensive error handling:

```python
try:
    score, details = eval_system.evaluate_single_answer(question, answer)
except ValueError as e:
    print(f"Configuration error: {e}")
except Exception as e:
    print(f"Evaluation error: {e}")
```

## Development

### Running Tests

```bash
pytest tests/
```

### Code Formatting

```bash
black rubrics_eval/
flake8 rubrics_eval/
```

## Contributing

1. Follow PEP 8 style guidelines
2. Add docstrings to all public methods
3. Include type hints
4. Write unit tests for new features
5. Update documentation

## License

This project is part of the BTP (Bachelor's Thesis Project) and is intended for educational and research purposes.

## Changelog

### Version 1.0.0

- Initial modular implementation
- Separated concerns into distinct modules
- Added comprehensive configuration management
- Implemented error handling and logging
- Added visualization capabilities
- Created example usage scripts

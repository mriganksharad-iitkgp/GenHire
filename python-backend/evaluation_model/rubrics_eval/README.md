# Rubrics Evaluation System

A modular, industry-standard evaluation system for generating rubrics, evaluating student answers, and creating test datasets for educational assessments.

## Features

- **Modular Architecture**: Clean separation of concerns with individual modules for each functionality
- **Rubric Generation**: Automated generation of grading criteria using LLMs
- **Answer Evaluation**: Scoring student responses against generated rubrics
- **Answer Spectrum Generation**: Create test datasets with varying answer qualities
- **Data Processing**: Utilities for handling CSV, JSON, and pandas DataFrames
- **Visualization**: Generate plots and charts for evaluation results
- **Configuration Management**: Centralized configuration with environment variable support

## Project Structure

```
rubrics-eval/
├── __init__.py              # Package initialization
├── config.py                # Configuration management
├── rubric_generator.py      # Rubric generation logic
├── answer_evaluator.py      # Answer evaluation logic
├── answer_generator.py      # Test answer generation
├── data_processor.py        # Data loading and processing
├── visualization.py         # Plotting and visualization
├── evaluation_system.py     # Main orchestrator class
├── example_usage.py         # Usage examples
├── requirements.txt         # Dependencies
└── README.md               # This file
```

## Installation

1. Install the required dependencies:

```bash
pip install -r requirements.txt
```

2. Set up your OpenAI API key:

```bash
# Unix/Linux/macOS
export OPENAI_API_KEY='your-api-key-here'

# Windows
set OPENAI_API_KEY=your-api-key-here
```

## Quick Start

```python
from evaluation_system import EvaluationSystem

# Initialize the system
eval_system = EvaluationSystem()

# Evaluate a single answer
question = "What is machine learning?"
student_answer = "Machine learning is a subset of AI that learns from data."
score, details = eval_system.evaluate_single_answer(question, student_answer)

print(f"Score: {score}")
for detail in details:
    print(f"- {detail['rubric']}: {detail['score']}")
```

## Usage Examples

### 1. Single Answer Evaluation

```python
# Generate rubrics and evaluate an answer
question = "Explain the bias-variance tradeoff"
answer = "Bias-variance tradeoff is about balancing model complexity..."

score, details = eval_system.evaluate_single_answer(question, answer)
```

### 2. Answer Spectrum Generation

```python
# Generate a spectrum of answers with different quality levels
titles, answers = eval_system.generate_answer_spectrum(
    "What is overfitting?",
    spectrum_type="balanced"
)
```

### 3. Dataset Processing

```python
# Process an entire dataset
results = eval_system.process_dataset(
    "questions.csv",
    question_column="Question"
)

# Save results
eval_system.save_results_to_csv(results, "evaluation_results.csv")
```

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

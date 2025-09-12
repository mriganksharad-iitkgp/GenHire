# Gemini LLM Integration

This document describes how to use Google's Gemini LLM with the interview system.

## Installation

To use Gemini LLM, you need to install the llama-index Gemini integration:

```bash
pip install llama-index-llms-gemini
```

## Setup

1. Get a Google AI API key from [Google AI Studio](https://makersuite.google.com/app/apikey)
2. Set your API key as an environment variable or pass it directly to the configuration

## Usage

### Basic Usage

```python
from interview.config.settings import LLMProvider, LLMConfig
from interview.llm import LLMFactory

# Create Gemini configuration
config = LLMConfig(
    provider=LLMProvider.GEMINI,
    model_name="gemini-1.5-flash",  # or "gemini-1.5-pro"
    api_key="your-google-api-key",
    temperature=0.7,
    max_tokens=1000
)

# Create LLM instance
llm = LLMFactory.create(config)

# Generate completion
response = llm.complete("Explain the concept of recursion in programming.")
print(response.text)
```

### Available Models

Common Gemini models you can use:

- `gemini-1.5-flash` - Fast and efficient for most tasks
- `gemini-1.5-pro` - Most capable model for complex reasoning
- `gemini-1.0-pro` - Previous generation model

### Environment Variables

You can set the API key as an environment variable:

```bash
export GOOGLE_API_KEY="your-google-api-key"
```

### Integration with Interview System

The Gemini LLM integrates seamlessly with the existing interview system. You can use it for:

- Question generation
- Answer evaluation
- Interview flow management

Example configuration in interview settings:

```python
from interview.config.settings import InterviewConfig, LLMProvider

# Update default provider to Gemini
interview_config = InterviewConfig(
    default_llm_provider=LLMProvider.GEMINI,
    default_model="gemini-1.5-flash"
)
```

## Error Handling

The Gemini LLM implementation includes proper error handling:

- Import errors if the package isn't installed
- API errors for invalid keys or rate limits
- Response validation to ensure quality outputs

## Performance Notes

- Gemini 1.5 Flash is optimized for speed and cost-effectiveness
- Gemini 1.5 Pro provides the best quality for complex reasoning tasks
- Consider rate limits and API quotas when choosing between models

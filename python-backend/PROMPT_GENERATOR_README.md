# Prompt-Based Question Generator

## Overview

A new simplified question generator that uses the technical interview prompts from `technical_interview_prompt.md`. This generator follows the structured interview flow with Alex Rivera persona and integrates seamlessly with the existing session manager.

## Files Created/Modified

### New Files:

- `interview/core/prompt_based_question_generator.py` - Main question generator implementation
- `test_prompt_generator.py` - Test file for the new generator
- `integration_example.py` - Documentation and usage example

### Modified Files:

- `interview/core/session_manager.py` - Updated import to use new question generator

## Key Features

### 1. Structured Interview Flow

The generator follows a 5-phase interview structure:

1. **Greeting** - Warm welcome with Alex Rivera persona
2. **Structure Explanation** - Outline the interview format
3. **Technical Questions** - 2-3 fundamental technical questions
4. **Candidate Questions** - Time for candidate to ask questions
5. **Closing** - Professional closing with next steps

### 2. CV-Based Question Generation

- Extracts technical keywords from CV (Python, React, MongoDB, etc.)
- Generates questions based on candidate's actual experience
- Assesses skill level from resume content
- Personalizes questions to candidate's background

### 3. Prompt-Based Design

- Uses templates from `technical_interview_prompt.md`
- Maintains Alex Rivera persona throughout
- Professional, empathetic tone
- Academically grounded technical questions

### 4. Seamless Integration

- Drop-in replacement for existing question generator
- Same interface and data structures
- No changes needed to session manager logic
- Works with existing API endpoints

## Usage

The generator automatically:

1. Extracts candidate name and technical skills from CV
2. Determines appropriate job title from job description
3. Generates contextual questions based on candidate's background
4. Follows natural conversation flow through interview phases
5. Adapts question difficulty based on performance

## Technical Questions Examples

Based on CV keywords, generates questions like:

- "Can you explain how Python's garbage collection works?"
- "What are the key differences between SQL and NoSQL databases?"
- "Describe how React's virtual DOM improves performance"
- "How would you implement error handling in a REST API?"

## Fallback Mechanisms

- Graceful fallbacks if LLM calls fail
- Default questions for each interview phase
- Robust error handling throughout the system
- Always generates a meaningful question even on errors

## Integration with Session Manager

The session manager has been updated with a single line change:

```python
# Old import
from .question_generator import QuestionGenerator, ConversationContext, QuestionMetadata

# New import
from .prompt_based_question_generator import PromptBasedQuestionGenerator as QuestionGenerator, ConversationContext, QuestionMetadata
```

All other session manager code remains unchanged and works exactly as before.

## Testing

Run the test file to verify functionality:

```bash
python test_prompt_generator.py
```

The test covers:

- Conversation initialization
- All interview phases
- Question generation
- CV keyword extraction
- Phase transitions

## Next Steps

1. Restart your application server
2. The new question generator is now active
3. All existing API endpoints work unchanged
4. Interview flow now follows the structured prompt format

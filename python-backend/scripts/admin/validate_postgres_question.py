"""Explicit trusted reference validation only; does not publish candidate SQL."""
import argparse
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--question-json',type=Path,required=True)
    parser.add_argument('--trusted-reference',action='store_true',required=True)
    args=parser.parse_args()
    from config.env_loader import load_environment
    load_environment()
    from services.aiven_question_validator import AivenQuestionValidator
    from models.hiring_workflow import WorkflowError
    try:
        question=json.loads(args.question_json.read_text(encoding='utf-8-sig'))
        result=AivenQuestionValidator().validate(question,trusted_reference=args.trusted_reference)
        print(json.dumps(result));return 0 if result['passed'] else 1
    except Exception as exc:
        print(json.dumps(dict(state='failed',error_code=exc.code if isinstance(exc,WorkflowError) else 'invalid_question_file')));return 1


if __name__=='__main__':raise SystemExit(main())

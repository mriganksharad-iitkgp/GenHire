"""Explicit operator acceptance; --execute-live consumes managed execution quota."""
import argparse
import json
from pathlib import Path
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--execute-live', action='store_true', help='Dispatch real paid canaries; no automatic retries.')
    parser.add_argument('--security-review', type=Path, help='Private JSON operator isolation review; see infra/oa_sql/README.md.')
    args = parser.parse_args()
    if not args.execute_live or not args.security_review:
        parser.error('Live acceptance requires --execute-live and --security-review; importing this script performs no work.')
    from config.env_loader import load_environment
    load_environment(require_database=True)
    from models.hiring_workflow import WorkflowError
    from services.assessment_executor_preflight import ExecutorPreflight
    try:
        review = json.loads(args.security_review.read_text(encoding='utf-8'))
        from config.database import db_config
        db = db_config.get_collections()['jobs'].database
        from services.assessment_authoring_service import ensure_authoring_indexes
        ensure_authoring_indexes(db)
        print(json.dumps(ExecutorPreflight(db).run(review)))
        return 0
    except Exception as exc:
        # SDK exceptions/URLs can contain credentials; emit only a stable code.
        print(json.dumps(dict(state='failed', error_code=exc.code if isinstance(exc, WorkflowError) else 'preflight_failed')))
        return 1


if __name__ == '__main__': raise SystemExit(main())

"""Read-only OnlineCompiler catalog/usage discovery; prints no credentials."""
from datetime import datetime, timezone
import json
from pathlib import Path
import sys
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))


def main():
    import argparse
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--record-usage',action='store_true',help='Persist an allowlisted usage snapshot in the explicitly configured application database.')
    args=parser.parse_args()
    from config.env_loader import load_environment
    load_environment(require_database=args.record_usage)
    from services.onlinecompiler_execution_provider import OnlineCompilerExecutionProvider
    from models.hiring_workflow import WorkflowError
    try:
        db=None
        if args.record_usage:
            from config.database import db_config
            db=db_config.get_collections()['jobs'].database
        provider=OnlineCompilerExecutionProvider(db)
        catalog=provider.compilers()
        raw=provider.usage()
        # Allowlist account totals; omit key identity and arbitrary remote text.
        usage={key:raw[key] for key in ('month','submissions','monthly_limit','remaining','resets_at','submissions_per_minute','pending_submissions','running_submissions') if key in raw}
        report=dict(provider='onlinecompiler',checked_at=datetime.now(timezone.utc).isoformat(),
            compilers=[{'id':item['id']} for item in catalog.get('compilers',[])],usage=usage)
        print(json.dumps(report))
        return 0
    except Exception as exc:
        print(json.dumps(dict(state='failed',error_code=exc.code if isinstance(exc,WorkflowError) else 'provider_discovery_failed')))
        return 1


if __name__=='__main__':raise SystemExit(main())

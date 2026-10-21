"""Read-only OA queue/capacity health; never repairs state or prints submissions."""
import json
from pathlib import Path
import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def main():
    from config.env_loader import load_environment
    load_environment()
    from config.database import db_config
    from pymongo import MongoClient
    from services.oa_operations import snapshot
    with MongoClient(db_config.uri, serverSelectionTimeoutMS=5000) as client:
        report = snapshot(client[db_config.database_name])
        print(json.dumps(report, indent=2))
        return 1 if report['alerts'] else 0


if __name__ == '__main__':
    sys.exit(main())

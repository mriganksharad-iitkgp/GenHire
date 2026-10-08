"""Read-only legacy application audit. Never merges, deletes or rewrites candidate data."""
import argparse
import json
import os
import sys
from pathlib import Path
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND = Path(__file__).resolve().parents[2]


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--sample-limit", type=int, default=50)
    args = parser.parse_args()
    if not 1 <= args.sample_limit <= 1000:
        parser.error("--sample-limit must be between 1 and 1000")
    load_dotenv(BACKEND / ".env", override=False)
    if not os.getenv("MONGODB_URI"):
        raise SystemExit("MONGODB_URI is required.")
    with MongoClient(os.environ["MONGODB_URI"], serverSelectionTimeoutMS=5000) as client:
        apps = client[os.getenv("DATABASE_NAME", "hrtech")]["applications"]
        pipeline = [
            {"$project": {
                "job": {"$toLower": {"$convert": {"input": "$job_id", "to": "string", "onError": "", "onNull": ""}}},
                "candidate": {"$toLower": {"$convert": {"input": "$student_id", "to": "string", "onError": "", "onNull": ""}}},
            }},
            {"$group": {"_id": {"job": "$job", "candidate": "$candidate"},
                        "count": {"$sum": 1}, "ids": {"$push": "$_id"}}},
            {"$match": {"count": {"$gt": 1}}},
            {"$limit": args.sample_limit},
        ]
        duplicates = list(apps.aggregate(pipeline, maxTimeMS=30000))
        noncanonical = apps.count_documents({"$or": [
            {"job_id": {"$type": "array"}},
            {"student_id": {"$type": "array"}},
            {"job_id": {"$not": {"$regex": "^[0-9a-f]{24}$"}}},
            {"student_id": {"$not": {"$regex": "^[0-9a-f]{24}$"}}},
        ]})
        indexes = apps.index_information()
        unique_ready = bool(indexes.get("uq_applications_job_student", {}).get("unique"))
        print(json.dumps({
            "read_only": True, "duplicate_group_sample": duplicates,
            "sample_limit": args.sample_limit, "noncanonical_identity_documents": noncanonical,
            "unique_index_ready": unique_ready,
            "next_step": "Review conflicting records and identity normalization before deploying. This script makes no changes.",
        }, default=str, indent=2))
        return 1 if duplicates or noncanonical else 0


if __name__ == "__main__":
    try:
        sys.exit(main())
    except Exception as exc:
        print("Audit could not complete (" + type(exc).__name__ + "). Check connectivity without logging credentials.", file=sys.stderr)
        sys.exit(2)

import argparse
import math
import os
import sys
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Any, Dict, List

from bson import ObjectId
from dotenv import load_dotenv
from pymongo import MongoClient

BACKEND_ROOT = Path(__file__).resolve().parents[1]
if str(BACKEND_ROOT) not in sys.path:
    sys.path.insert(0, str(BACKEND_ROOT))

from payment_module.config.settings import PaymentConfig  # noqa: E402
from payment_module.models.credit_transaction import CreditTransactionSchema  # noqa: E402
from payment_module.models.credit_wallet import CreditWalletSchema  # noqa: E402
from payment_module.models.payment import PaymentSchema  # noqa: E402

MIGRATION_RECHARGE_AT = datetime(2024, 1, 1)
INTERVIEWED_STATUSES = {"interviewed", "selected", "screening_cleared", "rejected"}


def normalize_audience(user_type: str) -> str:
    return "candidate" if str(user_type or "").lower() in {"candidate", "student"} else "recruiter"


def object_id_or_none(value: Any):
    try:
        return ObjectId(str(value))
    except Exception:
        return None


def first_datetime(*values):
    for value in values:
        if isinstance(value, datetime):
            return value
    return datetime.utcnow()


def is_proctored_from_job(job: Dict[str, Any]) -> bool:
    config = job.get("proctoring_config")
    if isinstance(config, dict):
        return any(bool(value) for value in config.values())
    return bool(job.get("gaze_proctoring"))


def build_user_index(db):
    users = {}
    for user in db.users.find({}, {"_id": 1, "user_type": 1}):
        owner_id = str(user["_id"])
        audience = normalize_audience(user.get("user_type"))
        if audience in {"candidate", "recruiter"}:
            users[owner_id] = audience
    return users


def build_plan_index(db):
    plans = {}
    for plan in db.plans.find(
        {"slug": {"$in": ["candidate-max", "recruiter-max"]}},
        {"_id": 1, "slug": 1, "name": 1, "price_paise": 1, "credits_allocated": 1},
    ):
        plans[str(plan.get("slug"))] = plan
    return plans


def collect_candidate_usage(db) -> Dict[str, List[Dict[str, Any]]]:
    usage = defaultdict(list)
    for session in db.practice_sessions.find(
        {"is_practice": True, "status": {"$in": ["completed", "ended"]}}
    ):
        owner_id = str(session.get("user_id") or "")
        if not owner_id:
            continue
        proctored = bool(session.get("proctoring_enabled", False))
        credits = (
            int(PaymentConfig.CANDIDATE_PRACTICE_PROCTORED_CREDITS)
            if proctored
            else int(PaymentConfig.CANDIDATE_PRACTICE_CREDITS)
        )
        session_id = str(session.get("session_id") or session.get("_id"))
        usage[owner_id].append(
            {
                "credits": credits,
                "transaction_type": "practice_interview",
                "reference_type": "practice_session",
                "reference_id": session_id,
                "idempotency_key": f"migration:practice-session:{session_id}",
                "created_at": first_datetime(session.get("completed_at"), session.get("created_at")),
                "metadata": {
                    "session_id": session_id,
                    "proctoring_enabled": proctored,
                    "migration_source": "practice_sessions",
                },
            }
        )
    return usage


def collect_recruiter_ai_jd_usage(db) -> Dict[str, List[Dict[str, Any]]]:
    usage = defaultdict(list)
    for event in db.ai_usage_events.find({"action_type": "ai_jd_generation"}):
        owner_id = str(event.get("actor_id") or "")
        if not owner_id:
            continue
        event_id = str(event.get("_id"))
        usage[owner_id].append(
            {
                "credits": int(PaymentConfig.RECRUITER_AI_JD_CREDITS),
                "transaction_type": "ai_jd_generation",
                "reference_type": "ai_usage_event",
                "reference_id": event_id,
                "idempotency_key": f"migration:ai-jd-generation:{event_id}",
                "created_at": first_datetime(event.get("occurred_at"), event.get("created_at")),
                "metadata": {
                    "migration_source": "ai_usage_events",
                    "model": event.get("model"),
                },
            }
        )
    return usage


def collect_recruiter_interview_usage(db) -> Dict[str, List[Dict[str, Any]]]:
    usage = defaultdict(list)
    jobs_by_id = {}
    for job in db.jobs.find({}, {"_id": 1, "created_by": 1, "proctoring_config": 1, "gaze_proctoring": 1}):
        jobs_by_id[str(job["_id"])] = job

    seen_application_ids = set()
    app_filter = {"status": {"$in": list(INTERVIEWED_STATUSES)}}
    for app in db.applications.find(app_filter):
        application_id = str(app.get("_id"))
        seen_application_ids.add(application_id)
        job = jobs_by_id.get(str(app.get("job_id") or ""))
        recruiter_id = str(app.get("recruiter_id") or (job or {}).get("created_by") or "")
        if not recruiter_id:
            continue
        proctored = is_proctored_from_job(job or {})
        credits = (
            int(PaymentConfig.RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS)
            if proctored
            else int(PaymentConfig.RECRUITER_REAL_INTERVIEW_CREDITS)
        )
        usage[recruiter_id].append(
            {
                "credits": credits,
                "transaction_type": "real_interview_recruiter",
                "reference_type": "application",
                "reference_id": application_id,
                "idempotency_key": f"migration:real-interview:{application_id}",
                "created_at": first_datetime(app.get("updated_at"), app.get("applied_at")),
                "metadata": {
                    "application_id": application_id,
                    "job_id": str(app.get("job_id") or ""),
                    "proctoring_enabled": proctored,
                    "migration_source": "applications",
                },
            }
        )

    for interview in db.interviews.find({"status": {"$in": ["completed", "ended"]}}):
        application_id = str(interview.get("application_id") or "")
        if application_id and application_id in seen_application_ids:
            continue
        reference_id = application_id or str(interview.get("session_id") or interview.get("_id"))
        job = jobs_by_id.get(str(interview.get("job_id") or ""))
        recruiter_id = str(interview.get("recruiter_id") or (job or {}).get("created_by") or "")
        if not recruiter_id:
            continue
        config = interview.get("proctoring_config") if isinstance(interview.get("proctoring_config"), dict) else None
        proctored = any(bool(value) for value in config.values()) if config else is_proctored_from_job(job or {})
        credits = (
            int(PaymentConfig.RECRUITER_REAL_INTERVIEW_PROCTORED_CREDITS)
            if proctored
            else int(PaymentConfig.RECRUITER_REAL_INTERVIEW_CREDITS)
        )
        usage[recruiter_id].append(
            {
                "credits": credits,
                "transaction_type": "real_interview_recruiter",
                "reference_type": "application" if application_id else "interview",
                "reference_id": reference_id,
                "idempotency_key": f"migration:real-interview:{reference_id}",
                "created_at": first_datetime(interview.get("completed_at"), interview.get("updated_at"), interview.get("created_at")),
                "metadata": {
                    "application_id": application_id,
                    "job_id": str(interview.get("job_id") or ""),
                    "session_id": str(interview.get("session_id") or ""),
                    "proctoring_enabled": proctored,
                    "migration_source": "interviews",
                },
            }
        )
    return usage


def add_many(target, source):
    for owner_id, rows in source.items():
        target[owner_id].extend(rows)


def build_ledger(users, usage_by_user, plans_by_slug):
    wallet_docs = []
    tx_docs = []
    payment_docs = []
    totals = {
        "candidate": {"users": 0, "usage": 0, "recharges": 0, "credited": 0, "balance": 0},
        "recruiter": {"users": 0, "usage": 0, "recharges": 0, "credited": 0, "balance": 0},
    }

    for owner_id, audience in users.items():
        rows = sorted(usage_by_user.get(owner_id, []), key=lambda item: item["created_at"])
        total_usage = sum(int(row["credits"]) for row in rows)
        max_pack = 1000 if audience == "candidate" else 10000
        plan_slug = "candidate-max" if audience == "candidate" else "recruiter-max"
        plan_name = "Candidate Max" if audience == "candidate" else "Recruiter Max"
        configured_price_paise = 99900 if audience == "candidate" else 999900
        plan_doc = plans_by_slug.get(plan_slug) or {}
        plan_id = plan_doc.get("_id")
        price_paise = int(plan_doc.get("price_paise", configured_price_paise) or configured_price_paise)
        required_after_bonus = max(0, total_usage - int(PaymentConfig.SIGNUP_BONUS_CREDITS))
        recharge_count = int(math.ceil(required_after_bonus / max_pack)) if required_after_bonus else 0
        recharge_total = recharge_count * max_pack
        balance = 0

        balance += int(PaymentConfig.SIGNUP_BONUS_CREDITS)
        tx_docs.append(
            {
                "owner_id": owner_id,
                "audience": audience,
                "delta_credits": int(PaymentConfig.SIGNUP_BONUS_CREDITS),
                "balance_after": balance,
                "transaction_type": "signup_bonus",
                "reference_type": "user",
                "reference_id": owner_id,
                "metadata": {"reason": "signup_bonus", "migration": True},
                "idempotency_key": f"migration:signup-bonus:{owner_id}:{audience}",
                "created_at": MIGRATION_RECHARGE_AT,
            }
        )

        for idx in range(recharge_count):
            payment_id = ObjectId()
            payment_order_id = f"migration_order_{owner_id}_{audience}_{idx + 1}"
            payment_razorpay_id = f"migration_payment_{owner_id}_{audience}_{idx + 1}"
            payment_docs.append(
                {
                    "_id": payment_id,
                    "employer_id": object_id_or_none(owner_id) or owner_id,
                    "subscription_id": None,
                    "plan_id": plan_id,
                    "amount_paise": price_paise,
                    "currency": "INR",
                    "status": "succeeded",
                    "razorpay_order_id": payment_order_id,
                    "razorpay_payment_id": payment_razorpay_id,
                    "razorpay_signature": "migration",
                    "idempotency_key": f"migration:payment:{owner_id}:{audience}:{idx + 1}",
                    "razorpay_response": {
                        "source": "migration",
                        "assumed_recharge_date": MIGRATION_RECHARGE_AT.isoformat(),
                    },
                    "refund_amount_paise": 0,
                    "refund_reason": None,
                    "failure_reason": None,
                    "metadata": {
                        "plan_name": plan_name,
                        "plan_slug": plan_slug,
                        "buyer_type": audience,
                        "plan_audience": audience,
                        "audience": audience,
                        "price_paise": price_paise,
                        "recharge_credits": max_pack,
                        "migration": True,
                        "migration_recharge_index": idx + 1,
                    },
                    "created_at": MIGRATION_RECHARGE_AT,
                    "updated_at": MIGRATION_RECHARGE_AT,
                    "completed_at": MIGRATION_RECHARGE_AT,
                }
            )
            balance += max_pack
            tx_docs.append(
                {
                    "owner_id": owner_id,
                    "audience": audience,
                    "delta_credits": max_pack,
                    "balance_after": balance,
                    "transaction_type": "migration_recharge",
                    "reference_type": "payment",
                    "reference_id": str(payment_id),
                    "metadata": {
                        "plan_name": plan_name,
                        "plan_slug": plan_slug,
                        "amount_paise": price_paise,
                        "recharge_credits": max_pack,
                        "migration": True,
                    },
                    "idempotency_key": f"migration:recharge:{owner_id}:{audience}:{idx + 1}",
                    "created_at": MIGRATION_RECHARGE_AT,
                }
            )

        for row in rows:
            credits = int(row["credits"])
            balance -= credits
            tx_docs.append(
                {
                    "owner_id": owner_id,
                    "audience": audience,
                    "delta_credits": -credits,
                    "balance_after": balance,
                    "transaction_type": row["transaction_type"],
                    "reference_type": row["reference_type"],
                    "reference_id": row["reference_id"],
                    "metadata": row.get("metadata") or {},
                    "idempotency_key": row["idempotency_key"],
                    "created_at": row["created_at"],
                }
            )

        credited = int(PaymentConfig.SIGNUP_BONUS_CREDITS) + recharge_total
        wallet_docs.append(
            {
                "owner_id": owner_id,
                "audience": audience,
                "balance": balance,
                "total_credited": credited,
                "total_debited": total_usage,
                "signup_bonus_granted": True,
                "created_at": MIGRATION_RECHARGE_AT,
                "updated_at": datetime.utcnow(),
            }
        )

        totals[audience]["users"] += 1
        totals[audience]["usage"] += total_usage
        totals[audience]["recharges"] += recharge_count
        totals[audience]["credited"] += credited
        totals[audience]["balance"] += balance

    return wallet_docs, tx_docs, payment_docs, totals


def backup_collection(db, source_name, backup_name):
    docs = list(db[source_name].find({}))
    if docs:
        db[backup_name].insert_many(docs)
    return len(docs)


def apply_rebuild(db, wallet_docs, tx_docs, payment_docs):
    timestamp = datetime.utcnow().strftime("%Y%m%d_%H%M%S")
    wallet_backup = f"{CreditWalletSchema.COLLECTION_NAME}_backup_{timestamp}"
    tx_backup = f"{CreditTransactionSchema.COLLECTION_NAME}_backup_{timestamp}"
    payment_backup = f"{PaymentSchema.COLLECTION_NAME}_backup_{timestamp}"
    wallet_count = backup_collection(db, CreditWalletSchema.COLLECTION_NAME, wallet_backup)
    tx_count = backup_collection(db, CreditTransactionSchema.COLLECTION_NAME, tx_backup)
    payment_count = backup_collection(db, PaymentSchema.COLLECTION_NAME, payment_backup)

    db[CreditWalletSchema.COLLECTION_NAME].delete_many({})
    db[CreditTransactionSchema.COLLECTION_NAME].delete_many({})
    db[PaymentSchema.COLLECTION_NAME].delete_many({"metadata.migration": True})
    if wallet_docs:
        db[CreditWalletSchema.COLLECTION_NAME].insert_many(wallet_docs)
    if tx_docs:
        db[CreditTransactionSchema.COLLECTION_NAME].insert_many(tx_docs)
    if payment_docs:
        db[PaymentSchema.COLLECTION_NAME].insert_many(payment_docs)

    CreditWalletSchema.create_indexes(db)
    CreditTransactionSchema.create_indexes(db)
    PaymentSchema.create_indexes(db)
    return {
        "wallet_backup": wallet_backup,
        "wallet_backup_count": wallet_count,
        "transaction_backup": tx_backup,
        "transaction_backup_count": tx_count,
        "payment_backup": payment_backup,
        "payment_backup_count": payment_count,
    }


def main():
    parser = argparse.ArgumentParser(description="Rebuild credit wallet ledgers from historical usage.")
    parser.add_argument("--apply", action="store_true", help="Write changes to MongoDB. Default is dry-run.")
    args = parser.parse_args()

    load_dotenv(BACKEND_ROOT / ".env")
    uri = os.getenv("MONGODB_URI")
    database_name = os.getenv("DATABASE_NAME", "hrtech")
    if not uri:
        raise SystemExit("MONGODB_URI is required")

    client = MongoClient(uri)
    db = client[database_name]

    users = build_user_index(db)
    plans_by_slug = build_plan_index(db)
    usage_by_user = defaultdict(list)
    add_many(usage_by_user, collect_candidate_usage(db))
    add_many(usage_by_user, collect_recruiter_ai_jd_usage(db))
    add_many(usage_by_user, collect_recruiter_interview_usage(db))

    wallet_docs, tx_docs, payment_docs, totals = build_ledger(
        users, usage_by_user, plans_by_slug
    )

    print("Credit wallet migration dry-run" if not args.apply else "Credit wallet migration apply")
    print(f"Database: {database_name}")
    print(f"Users: {len(users)}")
    print(f"Wallets to write: {len(wallet_docs)}")
    print(f"Transactions to write: {len(tx_docs)}")
    print(f"Migration payments to write: {len(payment_docs)}")
    for audience in ["candidate", "recruiter"]:
        row = totals[audience]
        print(
            f"{audience}: users={row['users']} usage={row['usage']} "
            f"max_recharges={row['recharges']} credited={row['credited']} balance={row['balance']}"
        )

    example_usage = 6150
    example_required = max(0, example_usage - int(PaymentConfig.SIGNUP_BONUS_CREDITS))
    example_recharges = math.ceil(example_required / 1000)
    example_balance = int(PaymentConfig.SIGNUP_BONUS_CREDITS) + example_recharges * 1000 - example_usage
    print(
        "Example candidate usage=6150 -> "
        f"recharges={example_recharges}, balance={example_balance}"
    )

    if args.apply:
        backup_info = apply_rebuild(db, wallet_docs, tx_docs, payment_docs)
        print(f"Backed up wallets to {backup_info['wallet_backup']} ({backup_info['wallet_backup_count']})")
        print(
            f"Backed up transactions to {backup_info['transaction_backup']} "
            f"({backup_info['transaction_backup_count']})"
        )
        print(
            f"Backed up payments to {backup_info['payment_backup']} "
            f"({backup_info['payment_backup_count']})"
        )
        print("Migration applied successfully")
    else:
        print("Dry-run only. Re-run with --apply to rebuild wallet collections.")


if __name__ == "__main__":
    main()

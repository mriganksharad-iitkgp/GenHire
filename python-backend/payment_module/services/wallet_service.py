import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError

from ..config.settings import PaymentConfig
from ..models.credit_transaction import CreditTransaction, CreditTransactionSchema
from ..models.credit_wallet import CreditWallet, CreditWalletSchema

logger = logging.getLogger(__name__)


class WalletService:
    RECHARGE_TRANSACTION_TYPES = {"recharge", "migration_recharge"}
    DEDUCTION_TRANSACTION_TYPES = {
        "practice_interview",
        "ai_jd_generation",
        "real_interview_recruiter",
        "candidate_invite",
    }

    def __init__(self, db):
        self.db = db
        self.wallet_collection = db[CreditWalletSchema.COLLECTION_NAME]
        self.transaction_collection = db[CreditTransactionSchema.COLLECTION_NAME]
        # Permanent record of every email that has ever received a signup
        # bonus, independent of the user row/wallet — survives account
        # deletion so a deleted-then-recreated account with the same email
        # can't re-claim the bonus.
        self.email_signup_registry = db["email_signup_registry"]
        self._ensure_indexes()

    # Class-level flag: only create indexes once per process lifetime.
    # WalletService is instantiated on every wallet-related request, so without
    # this guard each request would issue multiple index-creation round-trips to
    # MongoDB, adding ~50-100ms of unnecessary latency per request.
    _indexes_created: bool = False

    def _ensure_indexes(self):
        if WalletService._indexes_created:
            return
        try:
            CreditWalletSchema.create_indexes(self.db)
            CreditTransactionSchema.create_indexes(self.db)
            self.email_signup_registry.create_index("email_lower", unique=True)
            WalletService._indexes_created = True
        except Exception as exc:
            logger.error(f"Failed creating wallet indexes: {exc}")


    def _normalize_audience(self, audience: str) -> str:
        normalized = str(audience or "recruiter").strip().lower()
        return "candidate" if normalized in {"candidate", "student"} else "recruiter"

    def _get_wallet_doc(self, owner_id: str, audience: str) -> Optional[Dict[str, Any]]:
        return self.wallet_collection.find_one(
            {
                "owner_id": str(owner_id),
                "audience": self._normalize_audience(audience),
            }
        )

    def _format_result(
        self,
        owner_id: str,
        audience: str,
        transaction: Optional[Dict[str, Any]],
        *,
        idempotent_replay: bool = False,
        wallet_doc: Optional[Dict[str, Any]] = None,
    ) -> Dict[str, Any]:
        wallet_doc = wallet_doc or self._get_wallet_doc(owner_id, audience) or {}
        balance = int(wallet_doc.get("balance", 0) or 0)
        total_credited = int(wallet_doc.get("total_credited", 0) or 0)
        total_debited = int(wallet_doc.get("total_debited", 0) or 0)
        if transaction:
            balance = int(transaction.get("balance_after", balance) or 0)
        wallet_payload = None
        if wallet_doc:
            wallet_payload = {
                "owner_id": str(wallet_doc.get("owner_id") or owner_id),
                "audience": self._normalize_audience(wallet_doc.get("audience") or audience),
                "balance": balance,
                "total_credited": total_credited,
                "total_debited": total_debited,
                "signup_bonus_granted": bool(wallet_doc.get("signup_bonus_granted", False)),
            }

        return {
            "success": True,
            "idempotent_replay": bool(idempotent_replay),
            "wallet": wallet_payload,
            "transaction": transaction,
            "credits_remaining": balance,
            "current_balance": balance,
            "credits_allocated": total_credited,
            "total_credits_allocated": total_credited,
            "credits_used": total_debited,
            "total_credits_used": total_debited,
            "balance_after": balance,
        }

    def get_or_create_wallet(self, owner_id: str, audience: str) -> CreditWallet:
        normalized_audience = self._normalize_audience(audience)
        owner_id = str(owner_id)
        now = datetime.utcnow()

        doc = self.wallet_collection.find_one_and_update(
            {"owner_id": owner_id, "audience": normalized_audience},
            {
                "$setOnInsert": {
                    "owner_id": owner_id,
                    "audience": normalized_audience,
                    "balance": 0,
                    "total_credited": 0,
                    "total_debited": 0,
                    "signup_bonus_granted": False,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
        )
        return CreditWallet.from_dict(doc)

    def grant_signup_bonus_once(self, owner_id: str, audience: str, email: Optional[str] = None) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(owner_id, audience)
        normalized_email = str(email or "").strip().lower()
        email_already_used = bool(
            normalized_email
            and self.email_signup_registry.find_one({"email_lower": normalized_email})
        )

        if wallet.signup_bonus_granted or email_already_used:
            if email_already_used and not wallet.signup_bonus_granted:
                # This owner_id is new (recreated account) but the email has
                # already claimed a bonus before — mark the wallet so it
                # doesn't re-check the registry on every future call.
                self.wallet_collection.update_one(
                    {"owner_id": wallet.owner_id, "audience": wallet.audience},
                    {"$set": {"signup_bonus_granted": True, "updated_at": datetime.utcnow()}},
                )
            return {
                "success": True,
                "granted": False,
                "wallet": self.get_wallet_summary(owner_id, audience),
            }

        idempotency_key = f"signup-bonus:{wallet.owner_id}:{wallet.audience}"
        result = self.credit_wallet(
            owner_id=wallet.owner_id,
            audience=wallet.audience,
            credits=int(PaymentConfig.SIGNUP_BONUS_CREDITS),
            transaction_type="signup_bonus",
            reference_type="user",
            reference_id=wallet.owner_id,
            metadata={"reason": "signup_bonus"},
            idempotency_key=idempotency_key,
        )

        if result.get("success"):
            self.wallet_collection.update_one(
                {"owner_id": wallet.owner_id, "audience": wallet.audience},
                {
                    "$set": {
                        "signup_bonus_granted": True,
                        "updated_at": datetime.utcnow(),
                    }
                },
            )
            if normalized_email:
                try:
                    self.email_signup_registry.insert_one(
                        {
                            "email_lower": normalized_email,
                            "audience": wallet.audience,
                            "owner_id": wallet.owner_id,
                            "granted_at": datetime.utcnow(),
                        }
                    )
                except DuplicateKeyError:
                    # Race with a concurrent signup for the same email — the
                    # registry entry is already there, which is all that matters.
                    pass

        return {
            "success": bool(result.get("success")),
            "granted": bool(result.get("success")),
            "wallet": self.get_wallet_summary(wallet.owner_id, wallet.audience),
        }

    def credit_wallet(
        self,
        owner_id: str,
        audience: str,
        credits: int,
        transaction_type: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner_id = str(owner_id)
        normalized_audience = self._normalize_audience(audience)
        amount = max(0, int(credits or 0))
        if amount <= 0:
            return {"success": False, "error": "credits must be > 0"}

        replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
        if replay:
            return self._format_result(
                owner_id,
                normalized_audience,
                replay,
                idempotent_replay=True,
            )

        wallet = self.get_or_create_wallet(owner_id, normalized_audience)
        updated_doc = self.wallet_collection.find_one_and_update(
            {"owner_id": owner_id, "audience": normalized_audience},
            {
                "$inc": {"balance": amount, "total_credited": amount},
                "$set": {"updated_at": datetime.utcnow()},
            },
            return_document=ReturnDocument.AFTER,
        )

        transaction = CreditTransaction(
            owner_id=owner_id,
            audience=normalized_audience,
            delta_credits=amount,
            balance_after=int(updated_doc.get("balance", wallet.balance + amount)),
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )
        try:
            inserted = self.transaction_collection.insert_one(transaction.to_dict())
            transaction._id = inserted.inserted_id
        except DuplicateKeyError:
            replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
            if replay:
                return {"success": True, "idempotent_replay": True, "transaction": replay}
            raise
        return self._format_result(
            owner_id,
            normalized_audience,
            transaction.to_api_response(),
            wallet_doc=updated_doc,
        )

    def debit_wallet(
        self,
        owner_id: str,
        audience: str,
        credits: int,
        transaction_type: str,
        reference_type: Optional[str] = None,
        reference_id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner_id = str(owner_id)
        normalized_audience = self._normalize_audience(audience)
        amount = max(0, int(credits or 0))
        if amount <= 0:
            return {"success": False, "error": "credits must be > 0"}

        replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
        if replay:
            return self._format_result(
                owner_id,
                normalized_audience,
                replay,
                idempotent_replay=True,
            )

        self.get_or_create_wallet(owner_id, normalized_audience)

        updated_doc = self.wallet_collection.find_one_and_update(
            {
                "owner_id": owner_id,
                "audience": normalized_audience,
                "balance": {"$gte": amount},
            },
            {
                "$inc": {"balance": -amount, "total_debited": amount},
                "$set": {"updated_at": datetime.utcnow()},
            },
            return_document=ReturnDocument.AFTER,
        )

        if not updated_doc:
            wallet_doc = self._get_wallet_doc(owner_id, normalized_audience) or {}
            return {
                "success": False,
                "error": "Insufficient credits",
                "error_code": "insufficient_credits",
                "credits_required": amount,
                "credits_remaining": int(wallet_doc.get("balance", 0) or 0),
            }

        transaction = CreditTransaction(
            owner_id=owner_id,
            audience=normalized_audience,
            delta_credits=-amount,
            balance_after=int(updated_doc.get("balance", 0)),
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=str(reference_id) if reference_id is not None else None,
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )
        try:
            inserted = self.transaction_collection.insert_one(transaction.to_dict())
            transaction._id = inserted.inserted_id
        except DuplicateKeyError:
            replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
            if replay:
                return {"success": True, "idempotent_replay": True, "transaction": replay}
            raise
        return self._format_result(
            owner_id,
            normalized_audience,
            transaction.to_api_response(),
            wallet_doc=updated_doc,
        )

    def add_audit_transaction(
        self,
        owner_id: str,
        audience: str,
        transaction_type: str,
        reference_type: str,
        reference_id: str,
        metadata: Optional[Dict[str, Any]] = None,
        idempotency_key: Optional[str] = None,
    ) -> Dict[str, Any]:
        owner_id = str(owner_id)
        normalized_audience = self._normalize_audience(audience)

        replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
        if replay:
            return self._format_result(
                owner_id,
                normalized_audience,
                replay,
                idempotent_replay=True,
            )

        wallet = self.get_or_create_wallet(owner_id, normalized_audience)
        transaction = CreditTransaction(
            owner_id=owner_id,
            audience=normalized_audience,
            delta_credits=0,
            balance_after=int(wallet.balance),
            transaction_type=transaction_type,
            reference_type=reference_type,
            reference_id=str(reference_id),
            metadata=metadata or {},
            idempotency_key=idempotency_key,
        )
        try:
            inserted = self.transaction_collection.insert_one(transaction.to_dict())
            transaction._id = inserted.inserted_id
        except DuplicateKeyError:
            replay = self._find_idempotent(owner_id, normalized_audience, idempotency_key)
            if replay:
                return {"success": True, "idempotent_replay": True, "transaction": replay}
            raise
        return self._format_result(
            owner_id,
            normalized_audience,
            transaction.to_api_response(),
            wallet_doc=wallet.to_dict(),
        )

    def check_credit_availability(
        self,
        owner_id: str,
        audience: str,
        min_required_credits: int,
    ) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(owner_id, audience)
        required = max(0, int(min_required_credits or 0))
        can_start = int(wallet.balance) >= required
        return {
            "success": True,
            "can_start_interview": can_start,
            "required_credits": required,
            "credits_remaining": int(wallet.balance),
            "current_balance": int(wallet.balance),
            "credits_allocated": int(wallet.total_credited),
            "total_credits_allocated": int(wallet.total_credited),
            "credits_used": int(wallet.total_debited),
            "total_credits_used": int(wallet.total_debited),
            "is_unlimited": False,
            "error_code": None if can_start else "insufficient_credits",
        }

    def get_wallet_summary(self, owner_id: str, audience: str) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(owner_id, audience)
        latest_recharge = self.transaction_collection.find_one(
            {
                "owner_id": str(owner_id),
                "audience": self._normalize_audience(audience),
                "transaction_type": {"$in": list(self.RECHARGE_TRANSACTION_TYPES)},
            },
            sort=[("created_at", -1)],
        )
        balance = int(wallet.balance)
        total_credited = int(wallet.total_credited)
        total_debited = int(wallet.total_debited)
        return {
            "owner_id": wallet.owner_id,
            "audience": wallet.audience,
            "credits_balance": balance,
            "current_balance": balance,
            "total_credited": total_credited,
            "total_credits_allocated": total_credited,
            "total_debited": total_debited,
            "total_credits_used": total_debited,
            "signup_bonus_granted": bool(wallet.signup_bonus_granted),
            "latest_recharge": latest_recharge.get("metadata", {}) if latest_recharge else None,
        }

    def get_transactions(
        self,
        owner_id: str,
        audience: str,
        limit: int = 20,
        kind: str = "all",
    ) -> List[Dict[str, Any]]:
        normalized_audience = self._normalize_audience(audience)
        filters = {
            "owner_id": str(owner_id),
            "audience": normalized_audience,
        }
        normalized_kind = str(kind or "all").strip().lower()
        if normalized_kind == "deductions":
            filters["transaction_type"] = {"$in": list(self.DEDUCTION_TRANSACTION_TYPES)}
            filters["delta_credits"] = {"$lt": 0}
        elif normalized_kind == "recharges":
            filters["transaction_type"] = {"$in": list(self.RECHARGE_TRANSACTION_TYPES)}
            filters["delta_credits"] = {"$gt": 0}

        docs = (
            self.transaction_collection.find(filters)
            .sort("created_at", -1)
            .limit(max(1, min(int(limit or 20), 100)))
        )
        return [CreditTransaction.from_dict(doc).to_api_response() for doc in docs]

    def get_recharge_history(
        self, owner_id: str, audience: str, limit: int = 20
    ) -> List[Dict[str, Any]]:
        return self.get_transactions(owner_id, audience, limit=limit, kind="recharges")

    def bootstrap_signup_bonus_for_all_users(self, users_collection) -> Tuple[int, int]:
        granted = 0
        skipped = 0
        # Invite-only (burner) accounts are excluded: they're sponsored by the
        # recruiter who invited them (real interview credits are debited from
        # the recruiter's wallet, not theirs), so a signup bonus is never
        # earned. This also prevents a burner from silently occupying its
        # email's one-time bonus slot in email_signup_registry and denying
        # the real person their bonus if they later register for real.
        query = {"is_invite_only": {"$ne": True}}
        for user in users_collection.find(query, {"_id": 1, "user_type": 1, "email": 1, "email_lower": 1}):
            owner_id = str(user.get("_id"))
            raw_user_type = str(user.get("user_type") or "candidate").strip().lower()
            audience = "candidate" if raw_user_type in {"candidate", "student"} else "recruiter"
            email = user.get("email_lower") or user.get("email")
            result = self.grant_signup_bonus_once(owner_id, audience, email=email)
            if result.get("granted"):
                granted += 1
            else:
                skipped += 1
        return granted, skipped

    def _find_idempotent(
        self, owner_id: str, audience: str, idempotency_key: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        if not idempotency_key:
            return None
        existing = self.transaction_collection.find_one(
            {
                "owner_id": owner_id,
                "audience": audience,
                "idempotency_key": idempotency_key,
            }
        )
        if not existing:
            return None
        return CreditTransaction.from_dict(existing).to_api_response()

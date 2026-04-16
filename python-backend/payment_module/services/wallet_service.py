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
    def __init__(self, db):
        self.db = db
        self.wallet_collection = db[CreditWalletSchema.COLLECTION_NAME]
        self.transaction_collection = db[CreditTransactionSchema.COLLECTION_NAME]
        self._ensure_indexes()

    def _ensure_indexes(self):
        try:
            CreditWalletSchema.create_indexes(self.db)
            CreditTransactionSchema.create_indexes(self.db)
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

    def grant_signup_bonus_once(self, owner_id: str, audience: str) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(owner_id, audience)
        if wallet.signup_bonus_granted:
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
            return {"success": True, "idempotent_replay": True, "transaction": replay}

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
        return {
            "success": True,
            "idempotent_replay": False,
            "wallet": CreditWallet.from_dict(updated_doc).to_dict(),
            "transaction": transaction.to_api_response(),
        }

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
            return {"success": True, "idempotent_replay": True, "transaction": replay}

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
        return {
            "success": True,
            "idempotent_replay": False,
            "wallet": CreditWallet.from_dict(updated_doc).to_dict(),
            "transaction": transaction.to_api_response(),
        }

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
            return {"success": True, "idempotent_replay": True, "transaction": replay}

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
        return {
            "success": True,
            "idempotent_replay": False,
            "wallet": wallet.to_dict(),
            "transaction": transaction.to_api_response(),
        }

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
            "credits_allocated": int(wallet.total_credited),
            "credits_used": int(wallet.total_debited),
            "is_unlimited": False,
            "error_code": None if can_start else "insufficient_credits",
        }

    def get_wallet_summary(self, owner_id: str, audience: str) -> Dict[str, Any]:
        wallet = self.get_or_create_wallet(owner_id, audience)
        latest_recharge = self.transaction_collection.find_one(
            {
                "owner_id": str(owner_id),
                "audience": self._normalize_audience(audience),
                "transaction_type": "recharge",
            },
            sort=[("created_at", -1)],
        )
        return {
            "owner_id": wallet.owner_id,
            "audience": wallet.audience,
            "credits_balance": int(wallet.balance),
            "total_credited": int(wallet.total_credited),
            "total_debited": int(wallet.total_debited),
            "signup_bonus_granted": bool(wallet.signup_bonus_granted),
            "latest_recharge": latest_recharge.get("metadata", {}) if latest_recharge else None,
        }

    def get_transactions(self, owner_id: str, audience: str, limit: int = 20) -> List[Dict[str, Any]]:
        normalized_audience = self._normalize_audience(audience)
        docs = (
            self.transaction_collection.find(
                {
                    "owner_id": str(owner_id),
                    "audience": normalized_audience,
                }
            )
            .sort("created_at", -1)
            .limit(max(1, min(int(limit or 20), 100)))
        )
        return [CreditTransaction.from_dict(doc).to_api_response() for doc in docs]

    def bootstrap_signup_bonus_for_all_users(self, users_collection) -> Tuple[int, int]:
        granted = 0
        skipped = 0
        for user in users_collection.find({}, {"_id": 1, "user_type": 1}):
            owner_id = str(user.get("_id"))
            raw_user_type = str(user.get("user_type") or "candidate").strip().lower()
            audience = "candidate" if raw_user_type in {"candidate", "student"} else "recruiter"
            result = self.grant_signup_bonus_once(owner_id, audience)
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

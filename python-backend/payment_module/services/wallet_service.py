import logging
from datetime import datetime
from typing import Any, Dict, List, Optional, Tuple

from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
import uuid

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
    _indexed_databases = set()

    def _ensure_indexes(self):
        identity = (id(self.db.client), self.db.name)
        if WalletService._indexes_created and identity in WalletService._indexed_databases:
            return
        try:
            CreditWalletSchema.create_indexes(self.db)
            CreditTransactionSchema.create_indexes(self.db)
            self.email_signup_registry.create_index("email_lower", unique=True)
            WalletService._indexes_created = True
            WalletService._indexed_databases.add(identity)
        except Exception as exc:
            raise RuntimeError("Critical wallet indexes could not be created; billing is unavailable.") from exc


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

    def get_or_create_wallet(self, owner_id: str, audience: str, session=None) -> CreditWallet:
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
                    "reserved_credits": 0,
                    "total_credited": 0,
                    "total_debited": 0,
                    "signup_bonus_granted": False,
                    "created_at": now,
                    "updated_at": now,
                }
            },
            upsert=True,
            return_document=ReturnDocument.AFTER,
            session=session,
        )
        return CreditWallet.from_dict(doc)

    def grant_signup_bonus_once(self, owner_id, audience, email=None):
        owner_id, audience = str(owner_id), self._normalize_audience(audience)
        email = str(email or "").strip().lower()
        self.get_or_create_wallet(owner_id, audience)

        def grant(session):
            wallet = self.wallet_collection.find_one(dict(owner_id=owner_id, audience=audience), session=session)
            used = email and self.email_signup_registry.find_one({'email_lower': email}, session=session)
            if wallet.get('signup_bonus_granted') or used:
                self.wallet_collection.update_one({'_id': wallet['_id']}, {'$set': {'signup_bonus_granted': True}}, session=session)
                return False
            if email:
                self.email_signup_registry.insert_one(dict(email_lower=email, owner_id=owner_id,
                    audience=audience, granted_at=datetime.utcnow()), session=session)
            self._change_in_session(session, owner_id, audience, int(PaymentConfig.SIGNUP_BONUS_CREDITS),
                'signup_bonus', 'user', owner_id, {'reason': 'signup_bonus'}, f'signup-bonus:{owner_id}:{audience}')
            self.wallet_collection.update_one({'_id': wallet['_id']}, {'$set': {'signup_bonus_granted': True}}, session=session)
            return True
        try:
            granted = atomic(self.db, grant)
        except DuplicateKeyError:
            # Another transaction won the global email/owner claim. Recheck in
            # a fresh transaction; no credit from this aborted transaction survived.
            granted = atomic(self.db, grant)
        return {'success': True, 'granted': granted, 'wallet': self.get_wallet_summary(owner_id, audience)}

    def _change_in_session(self, session, owner_id, audience, delta, transaction_type,
                           reference_type, reference_id, metadata, key):
        identity = dict(owner_id=owner_id, audience=audience)
        previous = self.transaction_collection.find_one(dict(identity, idempotency_key=key), session=session)
        if previous:
            if (previous['delta_credits'] != delta or previous['transaction_type'] != transaction_type
                    or previous.get('reference_type') != reference_type or previous.get('reference_id') != reference_id):
                return {'success': False, 'error_code': 'idempotency_conflict',
                        'error': 'This operation key was already used for different billing details.'}
            wallet = self.wallet_collection.find_one(identity, session=session)
            return self._format_result(owner_id, audience, CreditTransaction.from_dict(previous).to_api_response(),
                                       idempotent_replay=True, wallet_doc=wallet)
        query = dict(identity)
        if delta < 0:
            query['balance'] = {'$gte': -delta}
        changes = {'balance': delta, 'total_credited' if delta > 0 else 'total_debited': abs(delta)}
        wallet = self.wallet_collection.find_one_and_update(query,
            {'$inc': changes, '$set': {'updated_at': datetime.utcnow()}},
            return_document=ReturnDocument.AFTER, session=session)
        if not wallet:
            current = self.wallet_collection.find_one(identity, session=session) or {}
            return {'success': False, 'error_code': 'insufficient_credits', 'error': 'Insufficient credits',
                    'credits_required': -delta, 'credits_remaining': current.get('balance', 0)}
        transaction = CreditTransaction(owner_id=owner_id, audience=audience, delta_credits=delta,
            balance_after=wallet['balance'], transaction_type=transaction_type, reference_type=reference_type,
            reference_id=reference_id, metadata=metadata or {}, idempotency_key=key)
        transaction._id = self.transaction_collection.insert_one(transaction.to_dict(), session=session).inserted_id
        return self._format_result(owner_id, audience, transaction.to_api_response(), wallet_doc=wallet)

    def _change(self, owner_id, audience, credits, transaction_type, reference_type, reference_id,
                metadata, idempotency_key, direction):
        if isinstance(credits, bool) or not isinstance(credits, int) or credits <= 0:
            return {'success': False, 'error': 'credits must be a positive integer', 'error_code': 'invalid_credits'}
        if not isinstance(transaction_type, str) or not transaction_type:
            return {'success': False, 'error': 'transaction_type is required', 'error_code': 'invalid_operation'}
        if idempotency_key is not None and (not isinstance(idempotency_key, str) or not 1 <= len(idempotency_key) <= 200):
            return {'success': False, 'error': 'Invalid operation key', 'error_code': 'invalid_operation'}
        owner_id, audience = str(owner_id), self._normalize_audience(audience)
        reference_id = str(reference_id) if reference_id is not None else None
        key = idempotency_key or 'unkeyed:' + uuid.uuid4().hex
        self.get_or_create_wallet(owner_id, audience)
        def change(session):
            return self._change_in_session(session, owner_id, audience, direction * credits,
                transaction_type, reference_type, reference_id, metadata, key)
        try:
            return atomic(self.db, change)
        except DuplicateKeyError:
            return atomic(self.db, change)

    def credit_wallet(self, owner_id, audience, credits, transaction_type, reference_type=None,
                      reference_id=None, metadata=None, idempotency_key=None):
        return self._change(owner_id, audience, credits, transaction_type, reference_type,
                            reference_id, metadata, idempotency_key, 1)

    def debit_wallet(self, owner_id, audience, credits, transaction_type, reference_type=None,
                     reference_id=None, metadata=None, idempotency_key=None):
        return self._change(owner_id, audience, credits, transaction_type, reference_type,
                            reference_id, metadata, idempotency_key, -1)

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
            "reserved_credits": int(wallet.reserved_credits),
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
        """Explicit legacy backfill; never call during HTTP worker startup."""
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

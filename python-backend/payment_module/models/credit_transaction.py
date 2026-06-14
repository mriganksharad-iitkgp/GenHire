from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId


@dataclass
class CreditTransaction:
    owner_id: str
    audience: str
    delta_credits: int
    balance_after: int
    transaction_type: str
    reference_type: Optional[str] = None
    reference_id: Optional[str] = None
    metadata: Dict[str, Any] = field(default_factory=dict)
    idempotency_key: Optional[str] = None
    created_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "owner_id": self.owner_id,
            "audience": self.audience,
            "delta_credits": int(self.delta_credits),
            "balance_after": int(self.balance_after),
            "transaction_type": self.transaction_type,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "metadata": self.metadata or {},
            "idempotency_key": self.idempotency_key,
            "created_at": self.created_at,
        }
        if self._id:
            payload["_id"] = self._id
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CreditTransaction":
        return cls(
            owner_id=str(payload.get("owner_id") or ""),
            audience=str(payload.get("audience") or "recruiter"),
            delta_credits=int(payload.get("delta_credits", 0) or 0),
            balance_after=int(payload.get("balance_after", 0) or 0),
            transaction_type=str(payload.get("transaction_type") or "adjustment"),
            reference_type=payload.get("reference_type"),
            reference_id=str(payload.get("reference_id")) if payload.get("reference_id") is not None else None,
            metadata=payload.get("metadata") or {},
            idempotency_key=payload.get("idempotency_key"),
            created_at=payload.get("created_at", datetime.utcnow()),
            _id=payload.get("_id"),
        )

    def to_api_response(self) -> Dict[str, Any]:
        return {
            "id": str(self._id) if self._id else None,
            "owner_id": self.owner_id,
            "audience": self.audience,
            "delta_credits": int(self.delta_credits),
            "balance_after": int(self.balance_after),
            "transaction_type": self.transaction_type,
            "reference_type": self.reference_type,
            "reference_id": self.reference_id,
            "metadata": self.metadata or {},
            "created_at": self.created_at.isoformat() if self.created_at else None,
        }


class CreditTransactionSchema:
    COLLECTION_NAME = "credit_transactions"

    INDEXES = [
        {
            "keys": [("owner_id", 1), ("audience", 1), ("created_at", -1)],
            "name": "idx_tx_owner_audience_created",
        },
        {
            "keys": [("owner_id", 1), ("audience", 1), ("idempotency_key", 1)],
            "unique": True,
            "partialFilterExpression": {"idempotency_key": {"$type": "string"}},
            "name": "idx_tx_owner_audience_idempotency",
        },
        {"keys": [("reference_type", 1), ("reference_id", 1)], "name": "idx_tx_reference"},
    ]

    @classmethod
    def create_indexes(cls, db):
        collection = db[cls.COLLECTION_NAME]
        for index in cls.INDEXES:
            # Copy the spec dict so we don't mutate the shared class-level
            # INDEXES list on each call (pop() would remove "keys" permanently,
            # causing KeyError on every subsequent WalletService instantiation).
            index_spec = dict(index)
            keys = index_spec.pop("keys")
            collection.create_index(keys, **index_spec)

from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, Optional

from bson import ObjectId


@dataclass
class CreditWallet:
    owner_id: str
    audience: str
    balance: int = 0
    total_credited: int = 0
    total_debited: int = 0
    signup_bonus_granted: bool = False
    created_at: datetime = field(default_factory=datetime.utcnow)
    updated_at: datetime = field(default_factory=datetime.utcnow)
    _id: Optional[ObjectId] = None

    def to_dict(self) -> Dict[str, Any]:
        payload = {
            "owner_id": self.owner_id,
            "audience": self.audience,
            "balance": int(self.balance or 0),
            "total_credited": int(self.total_credited or 0),
            "total_debited": int(self.total_debited or 0),
            "signup_bonus_granted": bool(self.signup_bonus_granted),
            "created_at": self.created_at,
            "updated_at": self.updated_at,
        }
        if self._id:
            payload["_id"] = self._id
        return payload

    @classmethod
    def from_dict(cls, payload: Dict[str, Any]) -> "CreditWallet":
        return cls(
            owner_id=str(payload.get("owner_id") or ""),
            audience=str(payload.get("audience") or "recruiter"),
            balance=int(payload.get("balance", 0) or 0),
            total_credited=int(payload.get("total_credited", 0) or 0),
            total_debited=int(payload.get("total_debited", 0) or 0),
            signup_bonus_granted=bool(payload.get("signup_bonus_granted", False)),
            created_at=payload.get("created_at", datetime.utcnow()),
            updated_at=payload.get("updated_at", datetime.utcnow()),
            _id=payload.get("_id"),
        )


class CreditWalletSchema:
    COLLECTION_NAME = "credit_wallets"

    INDEXES = [
        {
            "keys": [("owner_id", 1), ("audience", 1)],
            "unique": True,
            "name": "idx_wallet_owner_audience_unique",
        },
        {"keys": [("audience", 1), ("updated_at", -1)], "name": "idx_wallet_audience_updated"},
    ]

    @classmethod
    def create_indexes(cls, db):
        collection = db[cls.COLLECTION_NAME]
        for index in cls.INDEXES:
            keys = index.pop("keys")
            collection.create_index(keys, **index)
            index["keys"] = keys

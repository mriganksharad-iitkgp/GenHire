"""Reservation lifecycle for future OA consumers; no OA prices/endpoints enabled here."""
from datetime import datetime, timezone
from bson import ObjectId
from pymongo import ReturnDocument
from pymongo.errors import DuplicateKeyError
from core.mongo_transactions import atomic
from .wallet_service import WalletService


class BillingOperationError(ValueError):
    pass


class BillingOperationService:
    def __init__(self, db):
        self.db = db
        self.wallet = WalletService(db)
        db.billing_operations.create_index([('owner_id', 1), ('audience', 1), ('key', 1)], unique=True)
        db.billing_operations.create_index([('state', 1), ('updated_at', 1)])
        db.billing_refunds.create_index([('operation_id', 1), ('key', 1)], unique=True)

    @staticmethod
    def validate_key(key):
        if not isinstance(key, str) or not 8 <= len(key) <= 128:
            raise BillingOperationError('A stable 8–128 character operation key is required.')

    def ledger(self, operation, phase, delta, wallet, session):
        self.db.credit_transactions.insert_one(dict(owner_id=operation['owner_id'], audience=operation['audience'],
            delta_credits=delta, balance_after=wallet['balance'], transaction_type='oa_' + phase,
            reference_type='billing_operation', reference_id=str(operation['_id']), metadata={},
            idempotency_key=f"billing:{operation['_id']}:{phase}", created_at=datetime.now(timezone.utc)), session=session)

    def reserve(self, owner_id, audience, credits, key, purpose, session=None):
        self.validate_key(key)
        if type(credits) is not int or credits <= 0:
            raise BillingOperationError('Credits must be a positive integer.')
        if audience not in {'candidate', 'recruiter'} or not isinstance(purpose, str) or not 1 <= len(purpose) <= 80:
            raise BillingOperationError('Invalid billing audience/purpose.')
        self.wallet.get_or_create_wallet(owner_id, audience, session=session)
        identity = dict(owner_id=str(owner_id), audience=audience, key=key)
        operation_id = ObjectId()
        def reserve(session):
            existing = self.db.billing_operations.find_one(identity, session=session)
            if existing:
                if existing['credits'] != credits or existing['purpose'] != purpose:
                    raise BillingOperationError('Operation key reused with different billing details.')
                return existing
            wallet = self.db.credit_wallets.find_one_and_update(dict(owner_id=str(owner_id), audience=audience, balance={'$gte': credits}),
                {'$inc': {'balance': -credits, 'reserved_credits': credits}, '$set': {'updated_at': datetime.now(timezone.utc)}},
                session=session, return_document=ReturnDocument.AFTER)
            if not wallet:
                raise BillingOperationError('Insufficient credits.')
            operation = dict(identity, _id=operation_id, credits=credits, purpose=purpose,
                state='reserved', refunded_credits=0, created_at=datetime.now(timezone.utc), updated_at=datetime.now(timezone.utc))
            self.db.billing_operations.insert_one(operation, session=session)
            self.ledger(operation, 'reserve', -credits, wallet, session)
            return operation
        if session is not None: return reserve(session)
        try:
            return atomic(self.db, reserve)
        except DuplicateKeyError:
            return atomic(self.db, reserve)

    def settle(self, owner_id, audience, key, action, session=None):
        self.validate_key(key)
        if audience not in {'candidate', 'recruiter'}:
            raise BillingOperationError('Invalid billing audience.')
        if action not in {'capture', 'release'}:
            raise BillingOperationError('Settlement must capture or release.')
        def settle(session):
            op = self.db.billing_operations.find_one(dict(owner_id=str(owner_id), audience=audience, key=key), session=session)
            if not op:
                raise BillingOperationError('Unknown billing operation.')
            target = 'captured' if action == 'capture' else 'released'
            if op['state'] == target:
                return op
            if op['state'] != 'reserved':
                raise BillingOperationError('Operation has already been settled differently.')
            increments = {'reserved_credits': -op['credits']}
            increments['total_debited' if action == 'capture' else 'balance'] = op['credits']
            wallet = self.db.credit_wallets.find_one_and_update(dict(owner_id=op['owner_id'], audience=audience,
                reserved_credits={'$gte': op['credits']}), {'$inc': increments, '$set': {'updated_at': datetime.now(timezone.utc)}},
                session=session, return_document=ReturnDocument.AFTER)
            if not wallet:
                raise BillingOperationError('Wallet reservation invariant failed; reconciliation required.')
            op['state'], op['updated_at'] = target, datetime.now(timezone.utc)
            self.db.billing_operations.update_one({'_id': op['_id']}, {'$set': {'state': target, 'updated_at': op['updated_at']}}, session=session)
            self.ledger(op, action, 0 if action == 'capture' else op['credits'], wallet, session)
            return op
        return settle(session) if session is not None else atomic(self.db, settle)

    def refund(self, owner_id, audience, key, credits, refund_key, reason, session=None):
        self.validate_key(key)
        self.validate_key(refund_key)
        if audience not in {'candidate', 'recruiter'}:
            raise BillingOperationError('Invalid billing audience.')
        if type(credits) is not int or credits <= 0 or not isinstance(reason, str) or not 3 <= len(reason.strip()) <= 1000:
            raise BillingOperationError('A positive amount and documented refund reason are required.')
        def refund(session):
            op = self.db.billing_operations.find_one(dict(owner_id=str(owner_id), audience=audience, key=key), session=session)
            if not op:
                raise BillingOperationError('Unknown billing operation.')
            existing = self.db.billing_refunds.find_one(dict(operation_id=str(op['_id']), key=refund_key), session=session)
            if existing:
                if existing['credits'] != credits or existing['reason'] != reason:
                    raise BillingOperationError('Refund key reused with different details.')
                return op
            if op['state'] not in {'captured', 'partially_refunded'} or op['refunded_credits'] + credits > op['credits']:
                raise BillingOperationError('Refund exceeds the captured credits or operation is not captured.')
            op['refunded_credits'] += credits
            op['state'] = 'refunded' if op['refunded_credits'] == op['credits'] else 'partially_refunded'
            op['updated_at'] = datetime.now(timezone.utc)
            self.db.billing_operations.update_one({'_id': op['_id']}, {'$set': {k: op[k] for k in ('state', 'refunded_credits', 'updated_at')}}, session=session)
            self.db.billing_refunds.insert_one(dict(operation_id=str(op['_id']), key=refund_key,
                credits=credits, reason=reason, occurred_at=op['updated_at']), session=session)
            wallet = self.db.credit_wallets.find_one_and_update(dict(owner_id=str(owner_id), audience=audience),
                {'$inc': {'balance': credits, 'total_credited': credits}}, session=session, return_document=ReturnDocument.AFTER)
            self.ledger(op, 'refund:' + refund_key, credits, wallet, session)
            return op
        if session is not None: return refund(session)
        try:
            return atomic(self.db, refund)
        except DuplicateKeyError:
            return atomic(self.db, refund)

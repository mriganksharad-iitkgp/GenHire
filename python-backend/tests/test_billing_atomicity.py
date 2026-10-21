from concurrent.futures import ThreadPoolExecutor
import os
from pathlib import Path
import subprocess
import sys
import unittest
from unittest.mock import patch
import mongomock
from workflow_test_support import MongoTestCase, TEST_URI
from core.mongo_transactions import AtomicityUnavailable


class UnsupportedStorageTests(unittest.TestCase):
    def test_no_nontransactional_fallback(self):
        with patch('dotenv.load_dotenv', return_value=False):
            from payment_module.services.wallet_service import WalletService
            db = mongomock.MongoClient().db
            wallet = WalletService(db)
            wallet.get_or_create_wallet('owner', 'recruiter')
            with self.assertRaises(AtomicityUnavailable):
                wallet.credit_wallet('owner', 'recruiter', 100, 'recharge', idempotency_key='recharge:first')
            self.assertEqual(db.credit_wallets.find_one({})['balance'], 0)
            self.assertEqual(db.credit_transactions.count_documents({}), 0)


class BillingTransactionTests(MongoTestCase):
    def setUp(self):
        super().setUp()
        from payment_module.services.wallet_service import WalletService
        from payment_module.services.billing_operation_service import BillingOperationService, BillingOperationError
        self.wallet = WalletService(self.db)
        self.operations = BillingOperationService(self.db)
        self.error = BillingOperationError
        self.wallet.credit_wallet('owner', 'recruiter', 1000, 'recharge', idempotency_key='recharge:initial')

    def debit(self, key='debit:initial', amount=30):
        return self.wallet.debit_wallet('owner', 'recruiter', amount, 'real_interview_recruiter',
                                        reference_type='application', reference_id='one', idempotency_key=key)

    def balance(self):
        return self.db.credit_wallets.find_one({'owner_id': 'owner', 'audience': 'recruiter'})['balance']

    def test_duplicate_concurrent_debits_charge_once(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda _: self.debit(), range(16)))
        self.assertTrue(all(r['success'] for r in results))
        self.assertEqual(self.balance(), 970)
        self.assertEqual(self.db.credit_transactions.count_documents({'delta_credits': -30}), 1)

    def test_duplicate_concurrent_credits_and_refunds_credit_once(self):
        self.debit()
        def refund(_):
            return self.wallet.credit_wallet('owner', 'recruiter', 30, 'real_interview_refund',
                reference_type='application', reference_id='one', idempotency_key='refund:initial')
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(refund, range(16)))
        self.assertTrue(all(r['success'] for r in results))
        self.assertEqual(self.balance(), 1000)

    def test_reused_key_rejects_different_amount_or_business_details(self):
        self.debit()
        result = self.debit(amount=31)
        self.assertFalse(result['success'])
        self.assertEqual(result['error_code'], 'idempotency_conflict')
        self.assertEqual(self.balance(), 970)

    def test_transaction_failure_after_balance_write_rolls_back(self):
        with patch.object(self.wallet.transaction_collection, 'insert_one', side_effect=RuntimeError('injected ledger crash')):
            with self.assertRaises(RuntimeError):
                self.debit()
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.db.credit_transactions.count_documents({'delta_credits': -30}), 0)
        self.assertTrue(self.debit()['success'])
        self.assertEqual(self.balance(), 970)

    def test_process_death_during_uncommitted_write_has_no_visible_debit(self):
        # Abrupt process exit, without Python exception cleanup/abort_transaction.
        code = '''import os, sys
from pymongo import MongoClient
c=MongoClient(sys.argv[1]); db=c[sys.argv[2]]
s=c.start_session(); s.start_transaction()
db.credit_wallets.update_one({'owner_id':'owner'}, {'$inc':{'balance':-77}}, session=s)
os._exit(17)
'''
        process = subprocess.run([sys.executable, '-c', code, TEST_URI, self.db.name],
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0, timeout=15)
        self.assertEqual(process.returncode, 17)
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.db.credit_transactions.count_documents({}), 1)

    def test_insufficient_credit_and_invalid_amounts_have_no_effect(self):
        for amount in (True, 1.5, '30', 0, -1):
            self.assertFalse(self.debit(amount=amount)['success'])
        self.assertEqual(self.debit(amount=1001)['error_code'], 'insufficient_credits')
        self.assertEqual(self.balance(), 1000)

    def test_concurrent_distinct_debits_never_overdraw(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            results = list(pool.map(lambda i: self.debit('debit:unique:' + str(i), 300), range(8)))
        self.assertEqual(sum(r['success'] for r in results), 3)
        self.assertEqual(self.balance(), 100)

    def test_reserve_capture_replay_refund_lifecycle(self):
        op = self.operations.reserve('owner', 'recruiter', 100, 'oa:attempt:one', 'oa_attempt')
        self.assertEqual(op['state'], 'reserved')
        self.assertEqual(self.balance(), 900)
        self.operations.reserve('owner', 'recruiter', 100, 'oa:attempt:one', 'oa_attempt')
        self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'capture')
        self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'capture')
        wallet = self.db.credit_wallets.find_one({'owner_id': 'owner'})
        self.assertEqual((wallet['balance'], wallet['reserved_credits'], wallet['total_debited']), (900, 0, 100))
        self.operations.refund('owner', 'recruiter', 'oa:attempt:one', 40, 'refund:first', 'Partial infrastructure fault')
        self.operations.refund('owner', 'recruiter', 'oa:attempt:one', 40, 'refund:first', 'Partial infrastructure fault')
        self.assertEqual(self.balance(), 940)
        with self.assertRaises(self.error):
            self.operations.refund('owner', 'recruiter', 'oa:attempt:one', 61, 'refund:excess', 'Attempt over-refund')
        self.operations.refund('owner', 'recruiter', 'oa:attempt:one', 60, 'refund:last', 'Remaining refund')
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.db.billing_operations.find_one({})['state'], 'refunded')

    def test_concurrent_reservation_capture_and_refund_are_idempotent(self):
        with ThreadPoolExecutor(max_workers=8) as pool:
            list(pool.map(lambda _: self.operations.reserve('owner', 'recruiter', 100, 'oa:attempt:one', 'oa_attempt'), range(12)))
            list(pool.map(lambda _: self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'capture'), range(12)))
            list(pool.map(lambda _: self.operations.refund('owner', 'recruiter', 'oa:attempt:one', 100,
                'refund:once', 'Platform failure'), range(12)))
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.db.billing_operations.count_documents({}), 1)
        self.assertEqual(self.db.billing_refunds.count_documents({}), 1)

    def test_release_cannot_later_capture_and_other_owner_cannot_settle(self):
        self.operations.reserve('owner', 'recruiter', 100, 'oa:attempt:one', 'oa_attempt')
        with self.assertRaises(self.error):
            self.operations.settle('another', 'recruiter', 'oa:attempt:one', 'capture')
        self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'release')
        self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'release')
        self.assertEqual(self.balance(), 1000)
        with self.assertRaises(self.error):
            self.operations.settle('owner', 'recruiter', 'oa:attempt:one', 'capture')

    def test_reservation_and_ledger_rollback_together_on_crash(self):
        with patch.object(self.operations, 'ledger', side_effect=RuntimeError('injected reservation crash')):
            with self.assertRaises(RuntimeError):
                self.operations.reserve('owner', 'recruiter', 100, 'oa:attempt:one', 'oa_attempt')
        self.assertEqual(self.balance(), 1000)
        self.assertEqual(self.db.billing_operations.count_documents({}), 0)

    def test_global_email_bonus_claim_is_atomic_across_wallets(self):
        def grant(i):
            return self.wallet.grant_signup_bonus_once('bonus-owner-' + str(i), 'candidate', 'same@example.test')
        with ThreadPoolExecutor(max_workers=6) as pool:
            results = list(pool.map(grant, range(6)))
        self.assertEqual(sum(r['granted'] for r in results), 1)
        self.assertEqual(self.db.credit_transactions.count_documents({'transaction_type': 'signup_bonus'}), 1)


if __name__ == '__main__':
    unittest.main()

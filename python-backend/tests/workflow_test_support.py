"""Test-only local MongoDB access; never accepts application/cloud database URIs."""
import os
from pathlib import Path
import sys
import unittest
import uuid
from unittest.mock import patch
from urllib.parse import urlsplit
from pymongo import MongoClient

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
TEST_URI = os.environ.get('GENHIRE_TEST_MONGO_URI', '')


def isolated_database(test):
    if not TEST_URI:
        test.skipTest('Run scripts/dev/run_workflow_integration.py with a local mongod for real transaction tests.')
    parsed = urlsplit(TEST_URI)
    if parsed.scheme != 'mongodb' or parsed.hostname not in {'127.0.0.1', 'localhost'} or parsed.path not in {'', '/'}:
        raise RuntimeError('Tests require a loopback URI without an application database.')
    client = MongoClient(TEST_URI, serverSelectionTimeoutMS=3000)
    db = client['oa_step1_test_' + uuid.uuid4().hex]
    test.addCleanup(client.close)
    test.addCleanup(lambda: client.drop_database(db.name))
    return db


class MongoTestCase(unittest.TestCase):
    def setUp(self):
        self.db = isolated_database(self)
        self.env = patch.dict(os.environ, {'GENHIRE_WORKFLOW_ENABLED': 'true'})
        self.env.start()
        self.addCleanup(self.env.stop)
        self.dotenv = patch('dotenv.load_dotenv', return_value=False)
        self.dotenv.start()
        self.addCleanup(self.dotenv.stop)

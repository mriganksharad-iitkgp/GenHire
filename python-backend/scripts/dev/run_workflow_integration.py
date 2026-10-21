"""Start a disposable loopback replica set and run only isolated test databases.

Supply an existing official mongod executable; never reads application dotenv.
python scripts/dev/run_workflow_integration.py --mongod PATH [--pattern test_*.py]
"""
import argparse
import os
from pathlib import Path
import socket
import subprocess
import sys
import tempfile
import time
from pymongo import MongoClient


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mongod', required=True)
    parser.add_argument('--pattern', action='append')
    parser.add_argument('--combined', action='store_true', help='Use standard unittest discovery across each pattern.')
    args = parser.parse_args()
    binary = Path(args.mongod).resolve(strict=True)
    root = Path(__file__).resolve().parents[3]
    work = root / '.tmp'
    work.mkdir(exist_ok=True)
    with socket.socket() as sock:
        sock.bind(('127.0.0.1', 0))
        port = sock.getsockname()[1]
    with tempfile.TemporaryDirectory(prefix='oa-step1-rs-', dir=work) as data:
        process = subprocess.Popen([str(binary), '--dbpath', data, '--port', str(port), '--bind_ip', '127.0.0.1',
            '--replSet', 'oaTest', '--logpath', str(Path(data) / 'mongod.log'), '--setParameter', 'transactionLifetimeLimitSeconds=10'],
            stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
            creationflags=subprocess.CREATE_NO_WINDOW if os.name == 'nt' else 0)
        client = MongoClient(f'mongodb://127.0.0.1:{port}/?directConnection=true', serverSelectionTimeoutMS=500)
        try:
            deadline = time.monotonic() + 40
            while True:
                try:
                    client.admin.command('ping')
                    break
                except Exception:
                    if process.poll() is not None or time.monotonic() > deadline:
                        raise RuntimeError('Disposable mongod failed to start; inspect local log.')
                    time.sleep(.2)
            client.admin.command('replSetInitiate', {'_id': 'oaTest', 'members': [{'_id': 0, 'host': f'127.0.0.1:{port}'}]})
            while not client.admin.command('hello').get('isWritablePrimary'):
                if time.monotonic() > deadline:
                    raise RuntimeError('Disposable replica set did not elect a primary.')
                time.sleep(.2)
            env = dict(os.environ, GENHIRE_TEST_MONGO_URI=f'mongodb://127.0.0.1:{port}/?replicaSet=oaTest',
                       GENHIRE_DISABLE_JOBS='1', NO_PROXY='127.0.0.1,localhost', no_proxy='127.0.0.1,localhost')
            env['PYTHONPATH'] = str(root / 'python-backend') + os.pathsep + str(root / 'python-backend/tests')
            env['MPLCONFIGDIR'] = str(Path(data) / 'matplotlib')
            env['MPLBACKEND'] = 'Agg'
            # Active runtime modules use the same strict environment selection as
            # production. Never fall through to a developer's private dotenv.
            isolated_env = Path(data) / 'isolated.env'
            isolated_env.write_text('GENHIRE_DISABLE_JOBS=1\n', encoding='utf-8')
            env['ENV_FILE'] = str(isolated_env)
            env['MONGODB_URI'] = env['GENHIRE_TEST_MONGO_URI']
            env['DATABASE_NAME'] = 'oa_runner_isolated'
            result = 0
            for pattern in args.pattern or ['test_workflow_foundation.py', 'test_billing_atomicity.py', 'test_payment_startup.py']:
                # Existing suites install module-level SDK fakes; isolate files
                # so test discovery cannot contaminate unrelated real SDK tests.
                paths = [Path(pattern)] if args.combined else sorted((root / 'python-backend/tests').glob(pattern))
                if not paths:
                    raise ValueError('No test files matched: ' + pattern)
                for path in paths:
                    result |= subprocess.run([sys.executable, '-m', 'unittest', 'discover', '-s', 'python-backend/tests',
                                              '-p', path.name, '-v'], cwd=root, env=env, stderr=subprocess.STDOUT).returncode
            return result
        finally:
            try:
                client.admin.command({'shutdown': 1, 'force': True})
            except Exception:
                pass
            client.close()
            try:
                process.wait(timeout=15)
            except subprocess.TimeoutExpired:
                process.terminate()
                process.wait(timeout=15)


if __name__ == '__main__':
    sys.exit(main())

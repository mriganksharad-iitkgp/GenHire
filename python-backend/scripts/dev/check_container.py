"""Smoke-test an existing API image against disposable Docker Mongo/Redis.

Uses an internal network, synthetic signing credentials, no application dotenv,
no published ports and no cloud/provider calls. Removes only its own resources.
"""
import argparse
import json
from pathlib import Path
import secrets
import shutil
import subprocess
import tempfile
import time
import uuid


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--image', required=True)
    parser.add_argument('--docker', default=shutil.which('docker'))
    args = parser.parse_args()
    if not args.docker:
        parser.error('Supply --docker PATH or add Docker CLI to PATH.')
    docker = str(Path(args.docker).resolve())
    prefix = 'genhire-smoke-' + uuid.uuid4().hex[:10]
    network, mongo, redis, api = [prefix + suffix for suffix in ('-net', '-mongo', '-redis', '-api')]
    created = []
    network_created = False

    def run(*parts, check=True, timeout=120):
        result = subprocess.run([docker, *parts], capture_output=True, text=True, timeout=timeout)
        if check and result.returncode:
            # This harness passes only synthetic credentials, not real secrets.
            raise RuntimeError('Docker ' + parts[0] + ' failed: ' + result.stderr[-2500:])
        return result

    def wait(ready, seconds=120):
        deadline = time.monotonic() + seconds
        while time.monotonic() < deadline:
            if ready(): return
            time.sleep(1)
        raise RuntimeError('Container startup/readiness deadline exceeded')

    try:
        run('network', 'create', '--internal', network); network_created = True
        # No host ports, shared application volumes, or production credentials.
        run('run', '-d', '--name', mongo, '--network', network, 'mongo:8.0'); created.append(mongo)
        run('run', '-d', '--name', redis, '--network', network, 'redis:7-alpine'); created.append(redis)
        wait(lambda: run('exec', mongo, 'mongosh', '--quiet', '--eval', 'db.adminCommand({ping:1})', check=False).returncode == 0)

        from cryptography.hazmat.primitives import serialization
        from cryptography.hazmat.primitives.asymmetric import rsa
        private = rsa.generate_private_key(public_exponent=65537, key_size=2048)
        signing_key = private.private_bytes(serialization.Encoding.PEM, serialization.PrivateFormat.PKCS8, serialization.NoEncryption()).decode()
        credential = dict(type='service_account', project_id='synthetic-container-check', private_key_id='synthetic',
                          private_key=signing_key, client_email='smoke@synthetic-container-check.iam.gserviceaccount.com',
                          client_id='100000000000000000000', token_uri='https://oauth2.googleapis.com/token')
        environment = dict(FLASK_ENV='production', PORT='8080', FORCE_HTTPS='true',
                           GENHIRE_DISABLE_JOBS='1', GENHIRE_WORKFLOW_ENABLED='false', EMAIL_PROVIDER='noop',
                           MONGODB_URI=f'mongodb://{mongo}:27017/', DATABASE_NAME='container_smoke_only',
                           REDIS_URL=f'redis://{redis}:6379/0', RATE_LIMIT_REQUIRE_REDIS='true',
                           RATE_LIMIT_NAMESPACE=prefix, FLASK_SECRET_KEY=secrets.token_hex(32), JWT_SECRET_KEY=secrets.token_hex(32),
                           GCS_BUCKET_NAME='synthetic-container-check', GCS_SERVICE_ACCOUNT_JSON=json.dumps(credential),
                           GROQ_API_KEY='synthetic-no-provider-calls', CORS_ORIGINS='https://smoke.example.test')
        with tempfile.TemporaryDirectory(prefix=prefix) as temporary:
            env_file = Path(temporary) / 'container.env'
            env_file.write_text(''.join(f'{key}={value}\n' for key, value in environment.items()), encoding='utf-8')
            run('run', '-d', '--name', api, '--network', network, '--env-file', str(env_file), args.image)
            created.append(api)

        probe = "import urllib.request; r=urllib.request.urlopen('http://127.0.0.1:8080/health',timeout=8); assert r.status==200; print(r.read().decode())"
        def healthy():
            result = run('exec', api, 'python', '-c', probe, check=False)
            if result.returncode == 0: return True
            state = run('inspect', '--format', '{{.State.Running}}', api).stdout.strip()
            if state != 'true':
                raise RuntimeError('API exited during startup:\n' + run('logs', '--tail', '65', api, check=False).stdout[-6500:] + run('logs', '--tail', '20', api, check=False).stderr[-2500:])
            return False
        wait(healthy)
        print('PASS actual production Gunicorn startup and HTTP health with disposable Mongo/Redis', flush=True)
        run('exec', api, 'python', '-m', 'pip', 'check')
        print('PASS Linux installed dependency consistency', flush=True)
        run('exec', api, 'python', '-c', "from pathlib import Path; assert not list(Path('/app').glob('.env*')); assert not Path('/app/scripts/dev').exists(); from services.shared_cache import cache; assert cache.set('smoke',['worker'],{'shared':True},30)")
        run('exec', api, 'python', '-c', "from services.shared_cache import cache; assert cache.get('smoke',['worker'])=={'shared':True}; cache.delete('smoke',['worker'])")
        print('PASS cross-process Redis caching and private/developer artifact exclusion', flush=True)
        run('exec', api, 'python', '-c', "import urllib.request,urllib.error; r=urllib.request.Request('http://127.0.0.1:8080/api/me',headers={'X-Forwarded-Proto':'https'});\ntry: urllib.request.urlopen(r); raise AssertionError('Missing auth guard')\nexcept urllib.error.HTTPError as e: assert e.code==401,e.code")
        run('stop', redis)
        time.sleep(4)  # Expire the node-local three-second health probe memo.
        run('exec', api, 'python', '-c', "import urllib.request,urllib.error;\ntry: urllib.request.urlopen('http://127.0.0.1:8080/health'); raise AssertionError('False healthy result')\nexcept urllib.error.HTTPError as e: assert e.code==503,e.code")
        print('PASS authentication guard and unhealthy readiness after Redis outage', flush=True)
    finally:
        for name in reversed(created): run('rm', '-f', '-v', name, check=False)
        if network_created: run('network', 'rm', network, check=False)


if __name__ == '__main__': main()

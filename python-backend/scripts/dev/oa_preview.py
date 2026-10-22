"""Start an isolated real-provider developer OA page; never uses application DB credentials."""
import argparse
from contextlib import contextmanager
import json
import os
from pathlib import Path
import secrets
import shutil
import socket
import subprocess
import sys
import tempfile
import threading
import time

ROOT=Path(__file__).resolve().parents[3]
sys.path.insert(0,str(ROOT/'python-backend'))


@contextmanager
def local_database(binary):
    from pymongo import MongoClient
    work=ROOT/'.tmp';work.mkdir(exist_ok=True)
    with tempfile.TemporaryDirectory(prefix='genhire-oa-preview-',dir=work) as directory:
        with socket.socket() as sock:sock.bind(('127.0.0.1',0));port=sock.getsockname()[1]
        child=subprocess.Popen([str(binary),'--dbpath',directory,'--bind_ip','127.0.0.1','--port',str(port),'--replSet','oaPreview','--logpath',str(Path(directory)/'mongo.log')],
            stdout=subprocess.DEVNULL,stderr=subprocess.DEVNULL,creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
        client=MongoClient(f'mongodb://127.0.0.1:{port}/?directConnection=true',serverSelectionTimeoutMS=500,tz_aware=True)
        try:
            deadline=time.monotonic()+40
            while True:
                try:client.admin.command('ping');break
                except Exception:
                    if child.poll() is not None or time.monotonic()>deadline:raise RuntimeError('Disposable MongoDB failed to start.') from None
                    time.sleep(.2)
            client.admin.command('replSetInitiate',{'_id':'oaPreview','members':[{'_id':0,'host':f'127.0.0.1:{port}'}]})
            while not client.admin.command('hello').get('isWritablePrimary'):
                if time.monotonic()>deadline:raise RuntimeError('Disposable MongoDB election timed out.')
                time.sleep(.2)
            # Any lazily imported app settings can see only this isolated file.
            env_path=Path(directory)/'preview.env';env_path.write_text('GENHIRE_DISABLE_JOBS=1\n',encoding='utf-8')
            os.environ.update(ENV_FILE=str(env_path),MONGODB_URI=f'mongodb://127.0.0.1:{port}/?replicaSet=oaPreview',DATABASE_NAME='genhire_oa_preview_'+secrets.token_hex(8))
            # Reconnect with replica-set discovery after initiation; the initial
            # bootstrap client may have cached standalone session capabilities.
            client.close()
            client=MongoClient(os.environ['MONGODB_URI'],serverSelectionTimeoutMS=5000,tz_aware=True)
            client.admin.command('ping')
            yield client[os.environ['DATABASE_NAME']]
        finally:
            client.close();child.terminate()
            try:child.wait(timeout=10)
            except subprocess.TimeoutExpired:child.kill();child.wait(timeout=5)


def main():
    parser=argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--mongod',type=Path)
    parser.add_argument('--port',type=int,default=5011)
    parser.add_argument('--frontend-port',type=int,default=3000)
    parser.add_argument('--self-check',action='store_true',help='Run the actual save/submit/grade flow and exit; consumes seven compiler runs.')
    parser.add_argument('--engine',choices=['sqlite','duckdb'],default='sqlite')
    parser.add_argument('--contract',choices=['stdin_stdout','function'],default='stdin_stdout')
    parser.add_argument('--scenario',choices=['correct','wrong','compile_error','timeout'],default='correct')
    args=parser.parse_args()
    if not all(1024<=port<=65535 for port in (args.port,args.frontend_port)):parser.error('Ports must be 1024-65535.')
    binary=args.mongod or (ROOT/'.tmp/oa-step1-mongo/mongod.exe')
    if not binary.is_file():binary=Path(shutil.which('mongod') or '')
    if not binary.is_file():parser.error('Install MongoDB locally and pass --mongod PATH; the preview starts its own disposable replica set.')
    from dotenv import dotenv_values
    values=dotenv_values(ROOT/'python-backend/.env')
    for key in ('ONLINECOMPILER_API_KEY','ONLINECOMPILER_API_BASE_URL'):
        os.environ[key]=values.get(key) or os.environ.get(key,'')
    if not os.environ.get('ONLINECOMPILER_API_KEY'):parser.error('Fill ONLINECOMPILER_API_KEY in python-backend/.env.')
    os.environ.update(OA_EXECUTION_PROVIDER='onlinecompiler',OA_GENERIC_SQL_PROVIDER='onlinecompiler',
        GENHIRE_ASSESSMENT_EXECUTION_ENABLED='true',GENHIRE_EXECUTOR_ISOLATION_POLICY_ID='local-preview-not-production-acceptance',
        GENHIRE_OA_EVALUATION_ENABLED='true',GENHIRE_OA_INTEGRITY_ENABLED='false',GENHIRE_DISABLE_JOBS='1',
        OA_ENABLE_SQLITE='true',OA_ENABLE_DUCKDB='true',OA_POSTGRES_CANDIDATE_EXECUTION_ENABLED='false',
        OA_MAX_CONCURRENT_EXECUTIONS='2',ONLINECOMPILER_RUNS_PER_MINUTE='30',ONLINECOMPILER_TEST_BATCH_SIZE='4',
        OA_EXECUTION_TIMEOUT_MS='30000',JWT_SECRET_KEY=secrets.token_hex(32),FLASK_ENV='development')
    token=secrets.token_urlsafe(32)
    with local_database(binary.resolve()) as db:
        from oa_preview_app import Preview,create_app
        preview=Preview(db);preview.reset(args.engine,args.contract,args.scenario)
        app=create_app(preview,token,args.frontend_port)
        worker=threading.Thread(target=preview.work,daemon=True);worker.start()
        try:
            if args.self_check:
                preview.submit();deadline=time.monotonic()+180
                while time.monotonic()<deadline:
                    result=preview.status()
                    if result.get('report') or result['state'] in ('needs_review','unavailable','blocked'):break
                    time.sleep(.5)
                else:raise RuntimeError('Developer grading timed out; no final score was invented.')
                expected=100 if args.scenario=='correct' else 0 if args.scenario=='wrong' else 80
                passed=result.get('report',{}).get('score')==expected
                print(json.dumps(dict(passed=passed,expected_score=expected,**result)),flush=True)
                return 0 if passed else 1
            from werkzeug.serving import make_server
            print('Disposable OA preview. Real provider runs consume quota; no real wallet, production DB or acceptance writes.',flush=True)
            print(f'Open http://localhost:{args.frontend_port}/dev/oa#token={token}&port={args.port}',flush=True)
            print('Start the frontend separately with: cd react-frontend; npm.cmd start',flush=True)
            server=make_server('127.0.0.1',args.port,app,threaded=True)
            try:server.serve_forever()
            except KeyboardInterrupt:pass
            finally:server.server_close()
        finally:preview.stop.set();worker.join(timeout=35)


if __name__=='__main__':
    try:raise SystemExit(main())
    except KeyboardInterrupt:pass
    except Exception as exc:
        # Provider/connection exceptions can include private material.
        print(json.dumps(dict(error_code=getattr(exc,'code','preview_start_failed'),error_type=type(exc).__name__)),flush=True)
        raise SystemExit(1) from None

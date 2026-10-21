"""One fixture per disposable Cloud Run task; no production database connection.

Trusted bootstrap creates two distinct non-superuser SQL logins. Author SQL
never runs as the bootstrap administrator. Reader has SELECT only. A parent
process kills the entire database process group at the hard deadline.
"""
import datetime
from decimal import Decimal
import hashlib
import json
import multiprocessing
import os
from pathlib import Path
import re
import secrets
import shutil
import signal
import subprocess
import tempfile
import time


def digest(value):
    return hashlib.sha256(json.dumps(value, sort_keys=True, allow_nan=False, separators=(',', ':')).encode()).hexdigest()


def cell(value):
    if isinstance(value, Decimal): return float(value)
    if isinstance(value, (datetime.datetime, datetime.date, datetime.time)): return value.isoformat()
    if value is None or type(value) in (str, int, float, bool): return value
    raise ValueError('Unsupported SQL result type')


def validate_request(value, engine, version):
    required = {'schema_version', 'request_id', 'engine', 'engine_version', 'schema_sql', 'seed_sql', 'query', 'time_ms', 'max_rows'}
    if not isinstance(value, dict) or set(value) != required or type(value['schema_version']) is not int or value['schema_version'] != 1:
        raise ValueError('Invalid request shape')
    if not isinstance(value['request_id'], str) or not re.fullmatch(r'[a-f0-9]{24}', value['request_id']) or value['engine'] != engine or value['engine_version'] != version:
        raise ValueError('Request engine mismatch')
    for key, maximum in [('schema_sql', 20000), ('seed_sql', 20000), ('query', 64000)]:
        if not isinstance(value[key], str) or len(value[key]) > maximum: raise ValueError('SQL too large')
    if type(value['time_ms']) is not int or not 100 <= value['time_ms'] <= 10000 or type(value['max_rows']) is not int or value['max_rows'] != 1000:
        raise ValueError('Invalid limits')
    return value


def child_fixture(request, pipe):
    import pwd
    os.setsid()
    engine = request['engine']
    identity = pwd.getpwnam('postgres' if engine == 'postgresql' else 'mysql')
    directory = tempfile.mkdtemp(prefix='oa-sql-')
    os.chown(directory, identity.pw_uid, identity.pw_gid)
    directory = Path(directory)
    server = None
    query_started = False
    try:
        writer_password, reader_password = secrets.token_hex(24), secrets.token_hex(24)
        proc_args = dict(user=identity.pw_uid, group=identity.pw_gid, extra_groups=[], stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL)
        if engine == 'postgresql':
            import psycopg
            data, socket = directory / 'data', directory / 'socket'
            socket.mkdir(); os.chown(socket, identity.pw_uid, identity.pw_gid)
            binary = '/usr/lib/postgresql/17/bin/'
            subprocess.run([binary + 'initdb', '-D', str(data), '--auth-local=trust', '--auth-host=scram-sha-256', '--no-locale', '--encoding=UTF8'], check=True, timeout=15, **proc_args)
            server = subprocess.Popen([binary + 'postgres', '-D', str(data), '-k', str(socket), '-c', 'listen_addresses=',
                '-c', 'max_connections=8', '-c', 'shared_buffers=32MB', '-c', 'work_mem=4MB', '-c', 'max_parallel_workers=0',
                '-c', 'log_statement=none', '-c', 'log_min_error_statement=panic'], **proc_args)
            deadline = time.monotonic() + 12
            while True:
                try:
                    admin = psycopg.connect(host=str(socket), user='postgres', dbname='postgres', connect_timeout=1, autocommit=True)
                    break
                except psycopg.OperationalError:
                    if time.monotonic() > deadline: raise TimeoutError('Database startup timeout')
                    time.sleep(.1)
            from psycopg import sql
            with admin:
                if admin.info.server_version // 10000 != 17: raise ValueError('Unsupported database version')
                admin.execute(sql.SQL('CREATE ROLE fixture_writer LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT').format(sql.Literal(writer_password)))
                admin.execute(sql.SQL('CREATE ROLE fixture_reader LOGIN PASSWORD {} NOSUPERUSER NOCREATEDB NOCREATEROLE NOINHERIT').format(sql.Literal(reader_password)))
                admin.execute('CREATE DATABASE fixture OWNER fixture_writer')
            with psycopg.connect(host=str(socket), dbname='fixture', user='postgres', autocommit=True) as bootstrap:
                bootstrap.execute('REVOKE ALL ON DATABASE fixture FROM PUBLIC')
                bootstrap.execute('GRANT CONNECT ON DATABASE fixture TO fixture_writer, fixture_reader')
                bootstrap.execute('REVOKE ALL ON SCHEMA public FROM PUBLIC')
                bootstrap.execute('GRANT USAGE, CREATE ON SCHEMA public TO fixture_writer')
                bootstrap.execute('GRANT USAGE ON SCHEMA public TO fixture_reader')
            with psycopg.connect(host=str(socket), dbname='fixture', user='fixture_writer', password=writer_password, autocommit=True) as writer:
                writer.execute("SET statement_timeout='3s'")
                writer.execute(request['schema_sql'], prepare=False)
                if request['seed_sql']: writer.execute(request['seed_sql'], prepare=False)
                writer.execute('GRANT SELECT ON ALL TABLES IN SCHEMA public TO fixture_reader')
            # Authenticate restricted logins with scram after trusted bootstrap;
            # peer/trust must not remain usable by submitted SQL via DB helpers.
            (data / 'pg_hba.conf').write_text('local all fixture_reader scram-sha-256\nlocal all fixture_writer scram-sha-256\n', encoding='utf-8')
            os.kill(server.pid, signal.SIGHUP)
            time.sleep(.15)
            connection = psycopg.connect(host=str(socket), dbname='fixture', user='fixture_reader', password=reader_password, connect_timeout=2)
            connection.execute('SET default_transaction_read_only=on')
            connection.commit()
            connection.execute(f"SET statement_timeout={request['time_ms']}")
        else:
            import pymysql
            data, socket = directory / 'data', directory / 'mysql.sock'
            binary = shutil.which('mysqld')
            subprocess.run([binary, '--initialize-insecure', '--datadir=' + str(data), '--user=mysql'], check=True, timeout=20, **proc_args)
            server = subprocess.Popen([binary, '--datadir=' + str(data), '--socket=' + str(socket), '--skip-networking', '--skip-log-bin',
                '--mysqlx=OFF', '--local-infile=OFF', '--secure-file-priv=NULL', '--innodb-buffer-pool-size=64M', '--max-connections=8', '--skip-name-resolve'], **proc_args)
            deadline = time.monotonic() + 15
            while True:
                try:
                    admin = pymysql.connect(unix_socket=str(socket), user='root', connect_timeout=1, autocommit=True)
                    break
                except pymysql.MySQLError:
                    if time.monotonic() > deadline: raise TimeoutError('Database startup timeout')
                    time.sleep(.1)
            with admin:
                if not admin.get_server_info().startswith('8.4.'): raise ValueError('Unsupported database version')
                with admin.cursor() as cursor:
                    cursor.execute('CREATE DATABASE fixture')
                    cursor.execute("CREATE USER 'fixture_writer'@'localhost' IDENTIFIED BY %s", (writer_password,))
                    cursor.execute("CREATE USER 'fixture_reader'@'localhost' IDENTIFIED BY %s", (reader_password,))
                    cursor.execute("GRANT SELECT,INSERT,UPDATE,DELETE,CREATE,DROP,ALTER,INDEX ON fixture.* TO 'fixture_writer'@'localhost'")
                    cursor.execute("GRANT SELECT ON fixture.* TO 'fixture_reader'@'localhost'")
                    # Lock bootstrap admin before any untrusted fixture SQL runs.
                    cursor.execute("ALTER USER 'root'@'localhost' IDENTIFIED BY %s ACCOUNT LOCK", (secrets.token_hex(32),))
            from pymysql.constants import CLIENT
            with pymysql.connect(unix_socket=str(socket), user='fixture_writer', password=writer_password, database='fixture',
                    autocommit=True, read_timeout=4, write_timeout=2, local_infile=False, client_flag=CLIENT.MULTI_STATEMENTS) as writer:
                with writer.cursor() as cursor:
                    for statement in (request['schema_sql'], request['seed_sql']):
                        if statement:
                            cursor.execute(statement)
                            while cursor.nextset(): pass
            connection = pymysql.connect(unix_socket=str(socket), user='fixture_reader', password=reader_password, database='fixture',
                autocommit=False, read_timeout=max(1, request['time_ms'] / 1000), write_timeout=2, local_infile=False)
            with connection.cursor() as cursor:
                cursor.execute('SET SESSION TRANSACTION READ ONLY')
                cursor.execute('SET SESSION MAX_EXECUTION_TIME=%s', (request['time_ms'],))
        with connection:
            with connection.cursor() as cursor:
                pipe.send(dict(phase='query'))
                query_started = True
                cursor.execute(request['query'])
                if not cursor.description: raise ValueError('A result set is required')
                columns = [column[0] for column in cursor.description]
                if len(columns) > 30: raise ValueError('Too many columns')
                rows = cursor.fetchmany(request['max_rows'] + 1)
                if len(rows) > request['max_rows']: raise ValueError('Too many rows')
                result = dict(status='ok', columns=columns, rows=[[cell(v) for v in row] for row in rows])
                encoded = json.dumps(result, allow_nan=False)
                if len(encoded.encode()) > 64000: result = dict(status='output_limit')
                pipe.send(result)
    except Exception:
        # SQL exceptions may echo fixtures, passwords or queries. Do not log them.
        pipe.send(dict(status='runtime_error' if query_started else 'infrastructure_error'))
    finally:
        if server:
            server.terminate()
            try: server.wait(timeout=2)
            except subprocess.TimeoutExpired: server.kill()
        pipe.close()
        shutil.rmtree(directory, ignore_errors=True)


def execute(request):
    context = multiprocessing.get_context('spawn')
    receiver, sender = context.Pipe(duplex=False)
    process = context.Process(target=child_fixture, args=(request, sender))
    process.start(); sender.close()
    try:
        deadline = time.monotonic() + 40
        query_started = False
        while True:
            remaining = deadline - time.monotonic()
            if remaining <= 0 or not receiver.poll(remaining): return dict(status='time_limit' if query_started else 'infrastructure_error')
            try: value = receiver.recv()
            except EOFError: return dict(status='infrastructure_error')
            if value.get('phase') == 'query':
                query_started = True
                deadline = time.monotonic() + request['time_ms'] / 1000 + .25
            else: return value
    finally:
        process.join(timeout=1)
        if process.is_alive():
            try: os.killpg(process.pid, signal.SIGKILL)
            except ProcessLookupError: process.kill()
            process.join(timeout=2)
        receiver.close()


def main():
    from google.cloud import storage
    bucket_name = os.environ['SQL_REQUEST_BUCKET']
    request_object, result_object = os.environ['SQL_REQUEST_OBJECT'], os.environ['SQL_RESULT_OBJECT']
    match = re.fullmatch(r'sql-validation/requests/([a-f0-9]{24})\.json', request_object)
    if not match or result_object != f'sql-validation/results/{match[1]}.json': raise ValueError('Invalid artifact scope')
    client = storage.Client()
    bucket = client.bucket(bucket_name)
    blob = bucket.blob(request_object); blob.reload(timeout=10)
    if blob.size > 512000: raise ValueError('Request too large')
    request = validate_request(json.loads(blob.download_as_bytes(timeout=10)), os.environ['SQL_ENGINE'], os.environ['SQL_ENGINE_VERSION'])
    result = dict(execution_evidence_version=2, request_id=request['request_id'], request_hash=digest(request), engine=request['engine'], engine_version=request['engine_version'], **execute(request))
    bucket.blob(result_object).upload_from_string(json.dumps(result, allow_nan=False), content_type='application/json', if_generation_match=0, timeout=10)
    print('SQL fixture completed; result stored privately.')


if __name__ == '__main__': main()

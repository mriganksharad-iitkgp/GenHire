"""Bounded Sphere Engine v4 transport. Never returns token-bearing vendor URIs.

POST timeouts have ambiguous external outcomes and MUST NOT be blindly retried.
Callers persist dispatch intent and reconcile the provider submission ID.
"""
import json
import re
import unicodedata
from urllib.parse import urlsplit
import requests
from models.hiring_workflow import WorkflowError


class SphereEngineClient:
    def __init__(self, endpoint, token, product='compilers', session=None):
        try:
            parsed = urlsplit(endpoint or '')
            host, port = parsed.hostname or '', parsed.port
        except (ValueError, TypeError):
            raise WorkflowError('execution_not_configured', 'Sphere Engine endpoint is invalid.', 503) from None
        if (product not in {'compilers', 'problems'} or parsed.scheme != 'https' or port not in (None, 443)
                or not re.fullmatch(r'[a-zA-Z0-9-]+\.' + product + r'\.sphere-engine\.com', host)
                or parsed.path.rstrip('/') != '/api/v4' or parsed.query or parsed.fragment or parsed.username or parsed.password
                or not isinstance(token, str) or not token.strip()):
            raise WorkflowError('execution_not_configured', f'Sphere Engine {product} endpoint/token is not configured.', 503)
        self.endpoint, self.token, self.product = endpoint.rstrip('/'), token, product
        self.session = session or requests.Session()

    def request(self, method, path, data=None, raw=False, max_bytes=1048576, query=None):
        if not re.fullmatch(r'/[a-zA-Z0-9/_-]+', path): raise ValueError('Invalid vendor resource path.')
        query = query or {}
        if (method != 'GET' and query or set(query) - {'limit', 'offset', 'typeId'}
                or any(type(v) is not int or v < 0 for v in query.values())):
            raise ValueError('Invalid vendor query parameters.')
        response = None
        try:
            response = self.session.request(method, self.endpoint + path, params=dict(query, access_token=self.token),
                data=data, timeout=(5, 20), allow_redirects=False, stream=True)
            if not 200 <= response.status_code < 300:
                raise WorkflowError('executor_rejected', f'Execution service rejected the request (HTTP {response.status_code}).', 503)
            output = bytearray()
            for chunk in response.iter_content(chunk_size=8192):
                output.extend(chunk)
                if len(output) > max_bytes: raise WorkflowError('executor_output_limit', 'Execution service response exceeds its configured limit.', 503)
            if raw: return output.decode('utf-8', errors='strict')
            result = json.loads(output)
            if not isinstance(result, dict): raise ValueError('Invalid response')
            return result
        except requests.RequestException:
            raise WorkflowError('executor_dispatch_unknown' if method in {'POST', 'PUT', 'DELETE'} else 'executor_unavailable',
                'Execution service request could not be confirmed. Reconcile uncertain dispatches before retrying.', 503) from None
        except (ValueError, UnicodeError):
            raise WorkflowError('executor_invalid_response', 'Execution service returned an invalid response.', 503) from None
        finally:
            if response is not None: response.close()

    @staticmethod
    def positive_id(value):
        if type(value) is not int or value <= 0: raise WorkflowError('executor_invalid_response', 'Execution service returned an invalid resource ID.', 503)
        return value

    def compilers(self):
        items = self.request('GET', '/compilers').get('items')
        if not isinstance(items, list): raise WorkflowError('executor_invalid_response', 'Compiler catalog is unavailable.', 503)
        try:
            return [dict(id=self.positive_id(row['id']), name=row['name'],
                versions=[dict(id=self.positive_id(v['id']), name=v['name']) for v in row['versions']]) for row in items]
        except (KeyError, TypeError):
            raise WorkflowError('executor_invalid_response', 'Compiler catalog is malformed.', 503) from None

    def judges(self, type_id):
        """Read the bounded account catalog; never follow token-bearing paging URIs."""
        if self.product != 'problems' or type(type_id) is not int or type_id not in (0, 1):
            raise ValueError('Problems judge type must be 0 (testcase) or 1 (master).')
        rows = []
        for offset in range(0, 2000, 100):
            response = self.request('GET', '/judges', query=dict(typeId=type_id, limit=100, offset=offset))
            items = response.get('items')
            if not isinstance(items, list) or len(items) > 100:
                raise WorkflowError('executor_invalid_response', 'Judge catalog is malformed.', 503)
            for item in items:
                if (not isinstance(item, dict) or not isinstance(item.get('name'), str)
                        or not isinstance(item.get('type'), dict) or item['type'].get('id') != type_id):
                    raise WorkflowError('executor_invalid_response', 'Judge catalog is malformed.', 503)
                rows.append(dict(id=self.positive_id(item.get('id')), name=item['name'], type_id=type_id))
            if len(items) < 100:
                return rows
        raise WorkflowError('executor_catalog_limit', 'Judge catalog exceeds the discovery limit.', 503)

    def create_submission(self, source, compiler_id, version_id, input_text='', time_seconds=2, problem_id=None):
        payload = dict(source=source, compilerId=self.positive_id(compiler_id), compilerVersionId=self.positive_id(version_id))
        if self.product == 'problems':
            payload.update(problemId=self.positive_id(problem_id), executionMode='isolated')
        else: payload.update(input=input_text, timeLimit=time_seconds)
        return self.positive_id(self.request('POST', '/submissions', payload).get('id'))

    def submission(self, submission_id):
        response = self.request('GET', f'/submissions/{self.positive_id(submission_id)}')
        if type(response.get('executing')) is not bool: raise WorkflowError('executor_invalid_response', 'Execution state is missing.', 503)
        result = response.get('result') or {}
        streams = result.get('streams') or {}
        status = result.get('status') or {}
        # Never forward source, provider URLs, response text or diagnostics.
        return dict(executing=response.get('executing') is True, status_code=status.get('code'),
            compiler_id=(response.get('compiler') or {}).get('id'), compiler_version_id=((response.get('compiler') or {}).get('version') or {}).get('id'),
            time=result.get('time'), memory_kb=result.get('memory'), output_size=(streams.get('output') or {}).get('size', 0),
            testcases=[dict(number=t.get('number'), status_code=(t.get('status') or {}).get('code')) for t in result.get('testcases', [])])

    def output(self, submission_id, limit_bytes):
        return self.request('GET', f'/submissions/{self.positive_id(submission_id)}/output', raw=True, max_bytes=limit_bytes)

    def diagnostics(self, submission_id, stream='cmpinfo'):
        if stream not in {'cmpinfo', 'error'}: raise ValueError('Unsupported diagnostic stream.')
        try: value = self.request('GET', f'/submissions/{self.positive_id(submission_id)}/{stream}', raw=True, max_bytes=8192)
        except WorkflowError: return 'Detailed diagnostics are unavailable.'
        value = value.replace(self.token, '[redacted]')
        value = re.sub(r'https?://\S+', '[provider URL removed]', value)
        return ''.join(c for c in value if c in '\n\t' or not unicodedata.category(c).startswith('C'))[:4000]

    def create_problem(self, name, statement, master_judge_id):
        if self.product != 'problems': raise ValueError('Problems API is required.')
        return self.positive_id(self.request('POST', '/problems', dict(name=name, body=statement,
            masterjudgeId=self.positive_id(master_judge_id), typeId=0, executionMode='isolated')).get('id'))

    def create_testcase(self, problem_id, input_text, expected, seconds, judge_id):
        if self.product != 'problems': raise ValueError('Problems API is required.')
        number = self.request('POST', f'/problems/{self.positive_id(problem_id)}/testcases', dict(input=input_text,
            output=expected, timeLimit=seconds, judgeId=self.positive_id(judge_id), active=True)).get('number')
        if type(number) is not int or number < 0: raise WorkflowError('executor_invalid_response', 'Invalid provider test number.', 503)
        return number

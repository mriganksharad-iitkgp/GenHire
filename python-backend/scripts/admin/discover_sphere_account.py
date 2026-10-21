"""Read-only Sphere authentication/catalog discovery. No submissions or DB writes."""
import json
import os
from pathlib import Path
import re
import sys

sys.path.insert(0, str(Path(__file__).resolve().parents[2]))


def discover(client):
    client.request('GET', '/test')
    relevant = re.compile(r'python|javascript|node|java\b|c\+\+', re.I)
    result = dict(authentication='passed', compilers=[c for c in client.compilers() if relevant.search(c['name'])])
    if client.product == 'problems':
        result['testcase_judges'] = client.judges(0)
        result['master_judges'] = client.judges(1)
    return result


def main():
    from config.env_loader import load_environment
    from models.hiring_workflow import WorkflowError
    from services.sphere_engine_service import SphereEngineClient
    report, failed = {}, False
    try:
        load_environment()
    except Exception:
        print(json.dumps(dict(state='failed', error_code='environment_load_failed')))
        return 1
    for product in ('compilers', 'problems'):
        try:
            prefix = 'SPHERE_' + product.upper()
            client = SphereEngineClient(os.getenv(prefix+'_ENDPOINT'), os.getenv(prefix+'_TOKEN'), product)
            report[product] = discover(client)
        except Exception as exc:
            failed = True
            report[product] = dict(state='failed', error_code=exc.code if isinstance(exc, WorkflowError) else 'discovery_failed')
    # Catalog labels are provider-controlled: redact known credentials even there.
    output = json.dumps(report, ensure_ascii=True)
    for key in ('SPHERE_COMPILERS_TOKEN', 'SPHERE_PROBLEMS_TOKEN'):
        token = os.getenv(key)
        if token:
            output = output.replace(json.dumps(token)[1:-1], '[redacted]')
    print(output)
    return 1 if failed else 0


if __name__ == '__main__':
    raise SystemExit(main())

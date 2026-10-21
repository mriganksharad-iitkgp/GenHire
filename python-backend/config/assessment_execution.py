"""Server-only deployment settings; nothing here exposes tokens in capabilities."""
import json
import os
from models.hiring_workflow import WorkflowError


def enabled():
    return os.getenv('GENHIRE_ASSESSMENT_EXECUTION_ENABLED', '').lower() == 'true'


def runtime_profiles():
    try: profiles = json.loads(os.getenv('SPHERE_RUNTIME_PROFILES_JSON', '{}'))
    except (ValueError, TypeError): raise WorkflowError('execution_not_configured', 'Runtime profile JSON is invalid.', 503) from None
    if not isinstance(profiles, dict) or set(profiles) != {'python', 'javascript', 'java', 'cpp'}:
        raise WorkflowError('execution_not_configured', 'Four account-verified runtime profiles are required.', 503)
    for profile in profiles.values():
        if (not isinstance(profile, dict) or set(profile) != {'compiler_id', 'version_id', 'version_name', 'runtime_label'}
                or any(type(profile.get(k)) is not int or profile[k] <= 0 for k in ('compiler_id', 'version_id'))
                or any(not isinstance(profile.get(k), str) or not 1 <= len(profile[k]) <= 100 for k in ('version_name', 'runtime_label'))):
            raise WorkflowError('execution_not_configured', 'Runtime profiles must pin actual compiler/version IDs and names.', 503)
    return profiles


def execution_status():
    # Configured is deliberately weaker than tested/available.
    sphere = all(os.getenv(k) for k in ('SPHERE_COMPILERS_ENDPOINT', 'SPHERE_COMPILERS_TOKEN', 'SPHERE_PROBLEMS_ENDPOINT', 'SPHERE_PROBLEMS_TOKEN'))
    sql = all(os.getenv(k) for k in ('GENHIRE_SQL_PROJECT', 'GENHIRE_SQL_ARTIFACT_BUCKET', 'GENHIRE_SQL_POSTGRESQL_JOB', 'GENHIRE_SQL_MYSQL_JOB'))
    return dict(enabled=enabled(), sphere_configured=bool(sphere), sql_configured=bool(sql), region=os.getenv('GENHIRE_SQL_REGION', 'europe-west1'),
        available=False, reason='Live runtime and SQL isolation validation must pass before execution can be enabled.')

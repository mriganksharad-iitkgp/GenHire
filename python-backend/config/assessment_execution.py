"""Provider-independent OA configuration and documented runtime mappings."""
import os
from models.hiring_workflow import WorkflowError

RUNTIMES = {
    'python':'python-3.14', 'javascript':'nodejs-24', 'nodejs':'nodejs-24',
    'java':'openjdk-25', 'cpp':'g++-15', 'c':'gcc-15',
}
SQL_RUNTIMES = {'sqlite':'sqlite-3', 'duckdb':'duckdb-1.5'}


def enabled():
    return os.getenv('GENHIRE_ASSESSMENT_EXECUTION_ENABLED','').lower()=='true'


def integer_setting(key, default, low, high):
    try: value=int(os.getenv(key,str(default)))
    except ValueError: value=0
    if not low<=value<=high:
        raise WorkflowError('execution_not_configured',f'{key} must be between {low} and {high}.',503)
    return value


def runtime_profiles():
    # IDs/versions are documented by the provider; live acceptance verifies them.
    return {language:dict(compiler_id=compiler,runtime_label=compiler) for language,compiler in RUNTIMES.items()}


def sql_enabled(engine):
    return engine in SQL_RUNTIMES and os.getenv('OA_ENABLE_'+engine.upper(),'true').lower()=='true'


def execution_status():
    providers=all(os.getenv(key,'onlinecompiler')=='onlinecompiler' for key in ('OA_EXECUTION_PROVIDER','OA_GENERIC_SQL_PROVIDER'))
    return dict(enabled=enabled(),provider='onlinecompiler',configured=providers and bool(os.getenv('ONLINECOMPILER_API_KEY','').strip()),
                available=False,reason='Current live execution and SQL dataset acceptance is required.')

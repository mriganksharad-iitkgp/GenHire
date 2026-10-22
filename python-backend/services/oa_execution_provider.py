"""Execution boundary. Aiven trusted authoring is deliberately separate."""
from typing import Protocol
import os
from models.hiring_workflow import WorkflowError


class OAExecutionProvider(Protocol):
    def run_code(self, compiler, code, input_text='', time_limit=2): ...
    def evaluate_code(self, compiler, code, cases, time_limit=2, checker='trim'): ...
    def run_sql(self, identity, question, case, purpose): ...
    def evaluate_sql(self, identity, question, purpose='grading'): ...


def execution_provider(db=None, session=None):
    if os.getenv('OA_EXECUTION_PROVIDER','onlinecompiler')!='onlinecompiler' or os.getenv('OA_GENERIC_SQL_PROVIDER','onlinecompiler')!='onlinecompiler':
        raise WorkflowError('unsupported_execution_provider','Configure the approved OA execution provider.',503)
    from services.onlinecompiler_execution_provider import OnlineCompilerExecutionProvider
    return OnlineCompilerExecutionProvider(db,session)

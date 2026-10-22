"""Generic SQL framing and typed result sets; no candidate SQL runs locally."""
import hashlib
import json
import math
import re
from decimal import Decimal, InvalidOperation
from models.hiring_workflow import WorkflowError


def readonly_query(query):
    if not isinstance(query,str):raise WorkflowError('invalid_sql_query','A SQL query is required.',400)
    query=query.strip().rstrip(';').strip()
    plain=re.sub(r"'(?:''|[^'\\]|\\.)*'|\"(?:\"\"|[^\"\\]|\\.)*\"|`(?:``|[^`])*`",' quoted ',query)
    if (not re.match(r'(?is)^(SELECT|WITH)\b',plain) or re.search(r'(?m)^\s*\.',plain) or
        re.search(r';|--|/\*|\*/|#|\\|\$|\b(INTO|COPY|LOAD|ATTACH|DETACH|INSTALL|EXPORT|IMPORT|PRAGMA|CALL|DO|INSERT|UPDATE|DELETE|DROP|ALTER|CREATE|GRANT|REVOKE)\b',plain,re.I)):
        raise WorkflowError('invalid_sql_query','Use one read-only SELECT or WITH query without client commands.',400)
    return query


def sql_source(engine,schema,seed,query,identity):
    query=readonly_query(query)
    if engine not in ('sqlite','duckdb'):
        raise WorkflowError('sql_engine_unavailable','Candidate SQL supports SQLite and DuckDB only.',503)
    marker='gh'+hashlib.sha256(identity.encode()).hexdigest()[:20]
    table=marker+'_result'
    statements='\n'.join(value.strip().rstrip(';')+';' for value in (schema,seed) if value.strip())
    if engine=='sqlite':
        metadata=f"SELECT '{marker}' AS gh_frame, json_group_array(name) AS gh_columns FROM pragma_table_info('{table}');"
    else:
        metadata=f"SELECT '{marker}' AS gh_frame, to_json(list(column_name ORDER BY ordinal_position)) AS gh_columns, to_json(list(data_type ORDER BY ordinal_position)) AS gh_types FROM information_schema.columns WHERE table_name='{table}';"
    return ('.bail on\n.mode json\n'+statements+f'\nCREATE TEMP TABLE {table} AS {query};\n'+metadata+
            f"\nSELECT * FROM {table};\nSELECT '{marker}' AS gh_end;\n"),marker


def sql_result(result,marker):
    if result['status']!='ok':return {k:v for k,v in result.items() if k!='stdout'}
    try:
        decoder=json.JSONDecoder(parse_constant=lambda _:(_ for _ in ()).throw(ValueError()))
        text=result.get('stdout','').strip();values=[]
        while text:
            value,end=decoder.raw_decode(text);values.append(value);text=text[end:].strip()
        if len(values) not in (2,3):raise ValueError()
        metadata=values[0]
        if not isinstance(metadata,list) or len(metadata)!=1 or metadata[0].get('gh_frame')!=marker:raise ValueError()
        columns=metadata[0].get('gh_columns')
        if isinstance(columns,str):columns=json.loads(columns)
        if not isinstance(columns,list) or not columns or not all(isinstance(c,str) for c in columns) or len(set(columns))!=len(columns):raise ValueError()
        types=metadata[0].get('gh_types')
        if isinstance(types,str):types=json.loads(types)
        if types is not None and (not isinstance(types,list) or len(types)!=len(columns) or not all(isinstance(t,str) for t in types)):raise ValueError()
        if values[-1]!=[{'gh_end':marker}]:raise ValueError()
        records=values[1] if len(values)==3 else []
        if not isinstance(records,list):raise ValueError()
        if len(records)>1000:return dict(status='output_limit')
        rows=[]
        for row in records:
            if not isinstance(row,dict) or set(row)!=set(columns):raise ValueError()
            cells=[row[c] for c in columns]
            if any(type(cell) not in (type(None),str,int,float,bool) for cell in cells):raise ValueError()
            # DuckDB serializes HUGEINT aggregates and some decimals as JSON
            # strings. Convert using actual engine metadata, never fixtures or
            # a heuristic that would turn a VARCHAR '6' into a numeric answer.
            if types is not None:
                for index,(cell,kind) in enumerate(zip(cells,types)):
                    if isinstance(cell,str) and re.fullmatch(r'(U?HUGEINT|U?BIGINT|U?INTEGER|U?SMALLINT|U?TINYINT|DECIMAL\(\d+,\d+\)|DOUBLE|FLOAT)',kind):
                        value=Decimal(cell)
                        if not value.is_finite():raise ValueError()
                        cells[index]=int(value) if value==value.to_integral_value() else float(value)
            if any(type(cell) is float and not math.isfinite(cell) for cell in cells):raise ValueError()
            rows.append(cells)
        return dict(status='ok',columns=columns,rows=rows,**{k:result[k] for k in ('time_ms','memory_kb') if k in result})
    except (ValueError,TypeError,KeyError,AttributeError,InvalidOperation,OverflowError):
        raise WorkflowError('sql_result_unverified','The SQL engine did not return a complete typed result set.',503) from None

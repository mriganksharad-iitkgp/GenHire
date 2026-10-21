"""Provider transport schemas; application validators remain authoritative.

Strict decoding is used only by explicitly supported models. Function input
maps depend on a generated signature, so those retain ordinary JSON transport.
"""


def obj(properties):
    return dict(type='object', properties=properties, required=list(properties), additionalProperties=False)


def array(items):
    return dict(type='array', items=items)


def enum(*values):
    return dict(type='string', enum=list(values))


def question_response_schema(kind, languages, contract='stdin_stdout'):
    string, number = {'type':'string'}, {'type':'number'}
    common = dict(schema_version=dict(type='integer',enum=[1]), type=enum(kind), title=string, statement=string,
        difficulty=enum('easy','medium','hard'), topics=array(string), marks=number, explanation=string)
    visibility = enum('sample','hidden')
    if kind == 'mcq':
        common['mcq'] = obj(dict(selection=enum('single','multiple'),
            options=array(obj(dict(id=string,text=string))), correct_option_ids=array(string)))
    elif kind == 'coding':
        if contract != 'stdin_stdout':
            return None
        sources = obj({language:string for language in languages})
        common['coding'] = obj(dict(contract=enum('stdin_stdout'), signature={'type':'null'},
            harness_version=enum('genhire_fn_v1'), input_format=string, output_format=string, constraints=string,
            languages=array(enum(*languages)), runtime_versions=sources, starter_code=sources, reference_solutions=sources,
            limits=obj(dict(time_ms={'type':'integer'}, memory_mb={'type':'integer'}, output_kb={'type':'integer'})),
            comparison=enum('exact','trim_trailing_whitespace'),
            tests=array(obj(dict(id=string,visibility=visibility,input=string,expected=string,weight=number,explanation=string)))))
    elif kind == 'sql':
        cell = {'anyOf':[{'type':t} for t in ('string','number','boolean','null')]}
        common['sql'] = obj(dict(engine=enum('postgresql','mysql'), engine_version=string, schema_sql=string,
            reference_query=string, ordered={'type':'boolean'}, numeric_tolerance=number, time_ms={'type':'integer'},
            datasets=array(obj(dict(id=string,visibility=visibility,seed_sql=string,columns=array(string),
                expected_rows=array(array(cell)),weight=number,explanation=string)))))
    else:
        raise ValueError('Unsupported generated question type.')
    return obj(dict(questions=array(obj(common))))

"""Lossless transport escaping for model JSON strings; never fills missing content.
Only raw control characters and invalid backslash escapes inside quoted strings
are made representable. Missing quotes/braces, duplicate keys and invalid Unicode
escapes still fail the caller's strict JSON/schema validation.
"""
def escape_json_strings(value):
    if not isinstance(value,str):return value
    out=[];quoted=False;i=0
    while i<len(value):
        char=value[i]
        if char=='"':quoted=not quoted;out.append(char)
        elif quoted and char=='\\':
            if i+1<len(value) and value[i+1] in '\"\\/bfnrtu':
                out.extend([char,value[i+1]]);i+=1
            else:out.append('\\\\')
        elif quoted and ord(char)<32:out.append('\\u%04x'%ord(char))
        else:out.append(char)
        i+=1
    return ''.join(out)

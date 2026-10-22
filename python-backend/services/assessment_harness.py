"""Versioned function wrappers; returned source is for an isolated judge only.

One wrapper executes one typed test. No eval/exec/subprocess is used here.
Managed runtime/file-name mappings and real compilation remain provider gates.
"""
import json
from models.assessment_content import validate_question

JAVA_TYPES = {'integer': 'int', 'number': 'double', 'string': 'String', 'boolean': 'boolean'}
CPP_TYPES = {'integer': 'int', 'number': 'double', 'string': 'std::string', 'boolean': 'bool'}


def literal(value, kind, language):
    if kind.endswith('[]'):
        base = kind[:-2]
        items = ','.join(literal(item, base, language) for item in value)
        return f'new {JAVA_TYPES[base]}[]{{{items}}}' if language == 'java' else f'std::vector<{CPP_TYPES[base]}>{{{items}}}'
    if kind == 'string':
        # ASCII escapes are accepted by both managed Java/C++ compilers.
        encoded = json.dumps(value, ensure_ascii=True)
        # C++ treats surrogate escapes differently; use UTF-8 byte escapes.
        if language == 'cpp':
            return 'std::string("' + ''.join(f'\\{byte:03o}' for byte in value.encode('utf-8')) + f'", {len(value.encode("utf-8"))})'
        return encoded
    if kind == 'boolean': return 'true' if value else 'false'
    if kind == 'number': return repr(float(value))
    if value == -2147483648 and language == 'cpp': return '(-2147483647-1)'
    return str(value)


JAVA_JSON = r'''
class Main {
  static String ghJson(Object value) {
    if (value instanceof String) {
      StringBuilder b = new StringBuilder("\"");
      for (char c : ((String)value).toCharArray()) {
        if (c == '"' || c == '\\') b.append('\\').append(c);
        else if (c < 32) b.append(String.format("\\u%04x", (int)c));
        else b.append(c);
      }
      return b.append('"').toString();
    }
    if (value != null && value.getClass().isArray()) {
      StringBuilder b = new StringBuilder("[");
      for(int i=0;i<java.lang.reflect.Array.getLength(value);i++) {
        if(i>0) b.append(','); b.append(ghJson(java.lang.reflect.Array.get(value,i)));
      }
      return b.append(']').toString();
    }
    return String.valueOf(value);
  }
'''

CPP_JSON = r'''
#include <iostream>
#include <string>
#include <vector>
#include <iomanip>
static void ghJson(const std::string& value) {
  std::cout << '"';
  for (unsigned char c : value) {
    if(c=='"' || c=='\\') std::cout << '\\' << c;
    else if(c<32) { auto f=std::cout.flags(); auto fill=std::cout.fill();
      std::cout << "\\u" << std::hex << std::setw(4) << std::setfill('0') << (int)c;
      std::cout.flags(f); std::cout.fill(fill); }
    else std::cout << c;
  }
  std::cout << '"';
}
static void ghJson(bool value) { std::cout << (value ? "true" : "false"); }
static void ghJson(int value) { std::cout << value; }
static void ghJson(double value) { std::cout << std::setprecision(17) << value; }
template<typename T> static void ghJson(const std::vector<T>& value) {
  std::cout << '['; for(size_t i=0;i<value.size();i++) { if(i) std::cout << ','; ghJson(static_cast<T>(value[i])); } std::cout << ']';
}
'''


def function_source(question, language, case_id):
    q = validate_question(question)
    coding = q.get('coding')
    if not coding or coding['contract'] != 'function' or language not in coding['languages']:
        raise ValueError('A supported function question is required.')
    case = next((test for test in coding['tests'] if test['id'] == case_id), None)
    if case is None: raise ValueError('Unknown test case.')
    sig, solution = coding['signature'], coding['reference_solutions'][language]
    values = [case['input'][param['name']] for param in sig['parameters']]
    name = sig['name']
    if language == 'python':
        encoded = repr(json.dumps(values, ensure_ascii=True, allow_nan=False))
        return solution + f'\nimport json as ghJson\nghArgs = ghJson.loads({encoded})\nprint(ghJson.dumps({name}(*ghArgs), allow_nan=False, ensure_ascii=True))\n'
    if language in ('javascript', 'nodejs'):
        # JSON.parse avoids __proto__ object literal semantics; args are typed scalars/arrays.
        encoded = json.dumps(json.dumps(values, ensure_ascii=True, allow_nan=False))
        return solution + f'\nconst ghArgs = JSON.parse({encoded});\nprocess.stdout.write(JSON.stringify({name}(...ghArgs)));\n'
    args = ','.join(literal(value, param['type'], language) for value, param in zip(values, sig['parameters']))
    if language == 'java':
        return solution + '\n' + JAVA_JSON + f'public static void main(String[] args) throws Exception {{ System.out.print(ghJson(new Solution().{name}({args}))); }}\n}}\n'
    return CPP_JSON + '\n' + solution + f'\nint main() {{ ghJson(Solution().{name}({args})); }}\n'

"""Run only the trusted repository template sources locally. No candidate input, cloud or paid API calls.
Writes local evidence, not a managed-provider security/evaluation attestation.
"""
import json
import os
from pathlib import Path
import shutil
import subprocess
import sys
import time
sys.path.insert(0,str(Path(__file__).resolve().parents[2]))
from services.role_assessment_templates import coding
root=Path(__file__).resolve().parents[3];work=root/'.tmp'/'role-template-verification';work.mkdir(parents=True,exist_ok=True)
report=dict(environment='Local trusted code only; not Sphere runtime acceptance',timestamp=time.strftime('%Y-%m-%d %H:%M:%S'),references=[],baselines=[],unavailable=[])
runtimes=['python','javascript','cpp']
if not shutil.which('javac'):report['unavailable'].append('Java 21 compiler/runtime unavailable locally; managed validation required.')
else:runtimes.append('java')
for task in ('sum','divisible','remainders','bits'):
    q=coding(task,'medium',1,runtimes);c=q['coding'];folder=work/task;folder.mkdir(exist_ok=True)
    for language in runtimes:
        source=c['reference_solutions'][language]
        if language=='python':
            file=folder/'reference.py';file.write_text(source,encoding='utf8');cmd=[sys.executable,str(file)]
        elif language=='javascript':
            file=folder/'reference.cjs';file.write_text(source,encoding='utf8');cmd=['node',str(file)]
        elif language=='java':
            file=folder/'Main.java';file.write_text(source,encoding='utf8');subprocess.run(['javac',str(file)],check=True,capture_output=True);cmd=['java','-cp',str(folder),'Main']
        else:
            file=folder/'reference.cpp';file.write_text(source,encoding='utf8');exe=folder/'reference.exe'
            subprocess.run(['g++','-std=c++20','-O2',str(file),'-o',str(exe)],check=True,capture_output=True);cmd=[str(exe)]
        started=time.monotonic()
        for case in c['tests']:
            result=subprocess.run(cmd,input=case['input'],text=True,capture_output=True,timeout=2,check=True)
            if result.stdout.strip()!=case['expected'].strip():raise AssertionError((task,language,case['id'],result.stdout,case['expected']))
        report['references'].append(dict(task=task,language=language,passed=16,total=16,seconds=round(time.monotonic()-started,2)))
        print(task,language,'16/16',flush=True)
    if task=='sum':continue
    # C++ optimized native baseline is deliberately naive O(N). Volatile accumulator prevents loop elimination.
    body={'divisible':'long long a,b;std::cin>>a>>b;for(long long i=1;i<=n;++i)if(i%a==0||i%b==0)answer=answer+1;',
          'remainders':'long long m;std::cin>>m;for(long long i=0;i<=n;++i)answer=answer+i%m;',
          'bits':'for(long long i=0;i<=n;++i)answer=answer+__builtin_popcountll(i);'}[task]
    source='#include <iostream>\nint main(){long long n;std::cin>>n;volatile long long answer=0;'+body+'std::cout<<answer;}'
    file=folder/'baseline.cpp';file.write_text(source,encoding='utf8');exe=folder/'baseline.exe'
    subprocess.run(['g++','-std=c++20','-O2',str(file),'-o',str(exe)],check=True,capture_output=True)
    passed=0;timeouts=0
    for case in c['tests']:
        try:
            result=subprocess.run([str(exe)],input=case['input'],text=True,capture_output=True,timeout=c['limits']['time_ms']/1000,check=True)
            passed+=result.stdout.strip()==case['expected'].strip()
        except subprocess.TimeoutExpired:timeouts+=1
    report['baselines'].append(dict(task=task,language='cpp20 -O2',algorithm='naive O(N) enumeration',passed=passed,total=16,timeouts=timeouts,timeout_ms=1000))
    if passed>6:raise AssertionError('Slow baseline passed more than six cases: '+task)
    print(task,'naive baseline',passed,'/16',flush=True)
(work/'report.json').write_text(json.dumps(report,indent=2),encoding='utf8')
print('Evidence: .tmp/role-template-verification/report.json',flush=True)

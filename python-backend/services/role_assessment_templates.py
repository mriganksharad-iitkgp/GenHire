"""Private, authored OA starters. Never publish answers in a frontend asset.
These are reusable practice-quality starters, not calibrated or secret item pools.
"""
from copy import deepcopy
from datetime import datetime, timezone
from math import gcd
from bson import ObjectId
from models.job_setup import template, LANGUAGES
from models.assessment_content import validate_question, blueprint_match
from models.hiring_workflow import WorkflowError
from services.workflow_service import request_identity

# Each entry is statement | correct answer | three concrete distractors.
ROLE_ITEMS = {
'sde': [
'Which structure supports average constant-time lookup by key?|Hash map|Sorted array binary search|Linked list traversal|Unindexed file scan',
'Which algorithm finds a shortest path in an unweighted graph?|Breadth-first search|Depth-first search without distance tracking|Selection sort|Binary search',
'A sorted array has one million entries. Which search uses logarithmic comparisons?|Binary search|Linear scan|Bubble sort|Enumerating every pair',
'Which structure removes the most recently inserted item first?|Stack|FIFO queue|Sorted set|Relational table',
'What prevents two concurrent updates from silently overwriting each other?|Version-checked conditional updates|Ignoring write results|Reading from a stale cache only|Retrying every write without an idempotency key'],
'web_developer': [
'Which HTTP method should retrieve a resource without changing server state?|GET|POST|PATCH|DELETE',
'How should user input appear as text inside a page?|Use textContent or framework text escaping|Concatenate it into innerHTML|Evaluate it as JavaScript|Disable all output escaping',
'Which HTTP status best describes an unauthenticated protected request?|401|200|301|204',
'Which HTML control gives a clickable action keyboard support by default?|button|div with only an onclick|span without tabindex|An image without a label',
'Which response best handles a repeated payment request?|Return the result associated with its idempotency key|Charge again on every retry|Ignore failed network responses|Use a random new key for every retry'],
'data_analyst': [
'Which expression counts non-NULL values in a column x?|COUNT(x)|COUNT(*) always|SUM(x) always|MAX(x)',
'Which join keeps every row from the left table?|LEFT JOIN|INNER JOIN|CROSS JOIN with a filter|A right-table-only scan',
'Which SQL predicate detects missing values?|IS NULL|= NULL|!= NULL|= an empty string always',
'Which summary is most resistant to an extreme numeric outlier?|Median|Arithmetic mean|Sum|Maximum',
'Which design supports a causal claim about a product change?|Randomized controlled experiment|A single before-only snapshot|A chart without a control|A correlation alone'],
'data_scientist': [
'When should a scaler be fitted in model evaluation?|On training data only|On the entire dataset before splitting|On the test set only|After reading test labels',
'Which split avoids training on future observations for forecasting?|Chronological split|Random mixing of past and future|Duplicate test rows into training|Sort by target and alternate rows',
'Which metric is precision for the positive class?|TP divided by TP plus FP|TP divided by TP plus FN|TN divided by all predictions|FP divided by FN',
'What does regularization primarily discourage?|Excessive model complexity|Keeping any validation data|Using numeric features|Measuring prediction errors',
'Which comparison avoids class imbalance hiding poor minority recall?|Per-class recall alongside confusion matrix|Accuracy alone|Training loss alone|Number of features alone'],
'devops': [
'What should a readiness probe determine?|Whether an instance can receive traffic|Whether a bill has been paid|Whether a source file exists only|Whether deployment has a name',
'Which deployment strategy limits initial exposure?|Canary rollout|Replacing every instance at once|Disabling all monitoring|Skipping rollback preparation',
'Which account permission policy reduces blast radius?|Least privilege|Project-wide owner for every process|Shared admin password|Public write access',
'Which alert usually indicates direct user impact?|Elevated request failure rate|A harmless comment change|An unused dashboard name|A successful backup alone',
'How should a retryable write be made safe?|Use an idempotency key and bounded retries|Retry forever without a key|Ignore duplicate writes|Increase every timeout without limits'],
'qa': [
'Which test checks two services working together?|Integration test|A lint rule only|A unit test with every dependency mocked|A spelling check',
'Which values exercise boundaries for an inclusive 1 to 100 field?|0 1 100 101|Only 50|Only 25 and 75|Only valid middle values',
'How should a flaky automated test be investigated?|Record failure evidence and isolate nondeterminism|Rerun until green and hide it|Delete assertions immediately|Increase production privileges',
'Which test verifies a previously fixed defect remains fixed?|Regression test|Unrelated visual preference poll|A deployment name check|A source line count',
'What makes a defect report reproducible?|Steps expected result actual result and environment|Only a severity word|Only the reporter name|Only a screenshot with no context'],
'product': [
'What is a useful first step before committing to a feature?|Validate the user problem and desired outcome|Choose a UI color first|Copy a competitor without research|Promise a release date without scope',
'Which metric best indicates a checkout improvement achieved its goal?|Completed purchases per eligible checkout|Number of design files|Number of meetings|Raw page impressions alone',
'Why define a guardrail metric for an experiment?|Detect unacceptable side effects|Guarantee the hypothesis wins|Remove the need for a control|Increase sample bias',
'Which prioritization considers value relative to effort?|Compare expected impact confidence and cost|Always choose the loudest request|Always choose the largest feature|Ignore dependencies',
'What should an MVP primarily test?|The riskiest core product assumption|Every possible enhancement|Only the logo|Whether documentation can be skipped'],
'business_analyst': [
'What makes an acceptance criterion testable?|Observable behavior with clear conditions|A vague request to be better|An unmeasurable adjective|Only a project name',
'Which diagram best shows current process handoffs?|Process flow with owners and decisions|A color palette|An unlabeled screenshot|A source-code license list',
'What should resolve conflicting stakeholder requirements first?|Clarify business goals constraints and decision owner|Silently choose one|Implement both despite contradiction|Delete the requirement record',
'Why trace requirements to test cases?|Verify agreed behavior is covered|Replace stakeholder review|Guarantee zero defects|Avoid maintaining acceptance criteria',
'What is a useful response to a scope change?|Assess impact and obtain an explicit decision|Hide the change|Promise no schedule impact automatically|Discard all earlier requirements'],
'ux_design': [
'Which activity tests whether users can complete a task?|Task-based usability study|Counting design layers|Changing colors without users|Only a team preference vote',
'How should an input communicate an error accessibly?|Visible text associated with the field|Color alone|A hidden animation alone|An unlabeled icon alone',
'Which control communicates a mutually exclusive choice?|Radio group|Independent checkboxes|A decorative image|An unlabeled text block',
'What is the value of a consistent navigation pattern?|Reduce learning and prediction effort|Guarantee every user converts|Remove all content needs|Eliminate usability research',
'Which evidence best identifies a task friction point?|Observed failures and user explanations|Only the designer opinion|Only a mood board|Only total screen count'],
'security': [
'What prevents a query value from becoming executable SQL?|Parameterized queries|String concatenation|Hiding the database name|Client-side validation alone',
'How should stored passwords be protected?|Salted adaptive password hashing|Reversible plain encoding|Plaintext in an admin table|A shared hardcoded password',
'Where must authorization be enforced?|On the server for every protected action|Only by hiding frontend buttons|Only in a marketing page|Only in the browser URL',
'What should happen after a production API token is exposed?|Revoke or rotate it and investigate use|Keep it because traffic is low|Paste it into another public page|Only rename the variable',
'Which practice limits a compromised service account?|Least privilege and scoped credentials|Admin access everywhere|Sharing long-lived tokens with clients|Disabling audit logs'],
'marketing': [
'What is click-through rate?|Clicks divided by impressions|Impressions divided by clicks|Spend divided by revenue|Revenue divided by leads',
'Which test isolates the effect of a subject line?|Randomized variants with other factors held constant|Changing sender audience and content together|Comparing unrelated months alone|Selecting only successful recipients',
'Which metric measures acquisition efficiency?|Acquisition cost per new customer|Total posts alone|Office floor area|Number of campaign names',
'What makes a campaign landing page useful?|A clear relevant offer and measurable action|Multiple unrelated goals with no tracking|An invisible submit button|Only a company slogan',
'Which practice respects an email opt-out?|Stop promotional messages to opted-out recipients|Move them to another list silently|Ignore the opt-out until quarter end|Send more messages to recover engagement'],
'sales': [
'What is a useful qualification conversation?|Understand needs fit authority timing and constraints|Promise every requested feature|Send a contract before discovery|Ask only for the buyer name',
'How should a salesperson handle an unknown product capability?|Verify it and follow up accurately|Invent a positive answer|Hide the question|Guarantee it is included',
'Which activity creates a clear next step after discovery?|Agree an owner action and date with the prospect|Send repeated unscoped reminders|Mark the deal won|Skip written follow-up',
'What is pipeline conversion rate between two stages?|Deals advancing divided by eligible deals|Revenue divided by office cost|Calls divided by employees|All contacts divided by closed deals',
'What is an appropriate objection response?|Clarify the concern and address it with relevant evidence|Argue without listening|Offer unauthorized discounts automatically|Record the prospect as won'],
'hr': [
'Which interview approach improves comparison across candidates?|Consistent job-related questions and scoring rubric|Different unrelated questions for everyone|Unrecorded first impressions only|Personal family questions',
'Who should access candidate personal information?|Authorized people with a job-related need|Every employee by default|Anyone with a public link|External contacts without consent',
'Which hiring criterion is most appropriate?|Demonstrated skills relevant to the role|Unrelated personal characteristics|A shared hobby with the interviewer|A personal social connection alone',
'How should interview accommodations be handled?|Discuss needs privately and arrange suitable adjustments|Reject requests automatically|Publish medical details to the panel|Apply a penalty for requesting help',
'What supports a defensible shortlist decision?|Documented job-related evidence against criteria|A rumor|An unrelated social media opinion|A guess without notes'],
'customer_support': [
'What is a useful first response to an unclear issue?|Acknowledge impact and ask targeted diagnostic questions|Blame the customer|Close the ticket immediately|Request their password',
'When should an incident be escalated?|When impact or expertise exceeds the current support scope|Only when the customer stops replying|Never|After deleting evidence',
'What makes a support handoff effective?|Context steps tried evidence and next owner|Only a ticket number with no access|No reproduction details|A screenshot without description',
'How should a support agent handle an uncertain resolution time?|Give an honest update and next check-in time|Invent a guaranteed deadline|Stop responding|Mark resolved without confirmation',
'Which information should never be requested in chat?|A full account password|A nonsecret error code|The app version|The time the error occurred'],
'finance': [
'What does a balance sheet report?|Assets liabilities and equity at a date|Only cash received this week|Only future sales targets|Only marketing activity',
'What is gross profit?|Revenue minus cost of goods sold|Revenue minus all assets|Cash plus liabilities|Equity minus revenue',
'Why reconcile bank and ledger records?|Identify timing differences omissions and errors|Guarantee future profit|Replace approval controls|Avoid recording transactions',
'How is a prepaid annual expense normally recognized over its service period?|Allocate it to the periods receiving the benefit|Recognize new revenue every month|Ignore it until renewal|Add it permanently to cash',
'What does segregation of duties help prevent?|One person initiating and concealing an improper transaction|Any need for documentation|All currency risk|All market fluctuations']}

COMMON_ITEMS = [
'An invoice has 100 units at 12 each and a 10 percent discount. What is the discounted total before tax?|1080|1200|1100|1000',
'Conversions rise from 40 of 200 visits to 60 of 300. What happened to the conversion rate?|It stayed at 20 percent|It rose by 50 percentage points|It fell to 10 percent|It doubled',
'A task takes 3 hours each day for 5 days. Automation costs 4 hours and then takes 1 hour each day. What is the first-week saving?|6 hours|10 hours|4 hours|0 hours',
'Two equally sized groups have average scores 60 and 80. What is the combined average?|70|140|60|80',
'A metric moves from 80 to 100. What is the relative increase?|25 percent|20 percent|80 percent|125 percent',
'Which communication best supports a missed deadline recovery?|Explain impact propose a revised plan and confirm owners|Hide the delay|Blame an absent colleague|Promise completion without evidence',
'You receive a customer file irrelevant to your task. What is appropriate?|Restrict access and follow the approved deletion or return process|Forward it to everyone|Copy it to a personal account|Publish a sample online',
'Which source is strongest for a disputed operational number?|Reproducible query with defined population and time window|An unlabeled screenshot|An unsourced chat claim|A remembered estimate alone',
'A report shows correlation. Which conclusion is justified?|The variables move together in this sample|One variable certainly caused the other|Confounding is impossible|A controlled experiment is unnecessary',
'What should be done before changing a shared production setting?|Assess impact get required review and prepare rollback|Change it without recording|Disable all alerts|Use another person credentials',
'A sample contains only customers who renewed. What is a likely limitation?|Selection bias when estimating all-customer satisfaction|It guarantees an unbiased population estimate|It proves churn is zero|It eliminates sampling uncertainty',
'Which experiment change introduces confounding?|Changing audience and price together without a suitable design|Random assignment|Prespecifying the main metric|Keeping eligibility rules constant',
'What makes a request easier for another team to act on?|Clear goal required input deadline and owner|Only an urgent label|An unexplained attachment|Multiple contradictory instructions',
'An error affects 10 of 500 requests. What is the error rate?|2 percent|5 percent|20 percent|0.2 percent',
'Which action helps prevent duplicate work across teams?|Agree ownership and track a shared work item|Start separate efforts without telling anyone|Keep requirements private|Only increase meeting frequency',
'A change saves 200 per month and costs 1000 upfront. Ignoring discounting what is payback?|5 months|2 months|10 months|20 months',
'A dataset contains duplicate order IDs. What should happen before revenue aggregation?|Investigate the intended grain and deduplication rule|Sum everything without checking|Delete all repeated customer names|Replace missing values with random amounts',
'Which estimate includes uncertainty honestly?|A range with assumptions and confidence limits explained|A guaranteed exact figure without evidence|A number with hidden exclusions|The largest imaginable outcome only',
'Which comparison is fair when exposure durations differ?|A rate normalized to a relevant exposure unit|Raw totals without context|Only the larger total|Only the most recent observation',
'What is an appropriate response when evidence contradicts your proposal?|Update the proposal and record the reason|Hide the evidence|Change the success metric after seeing results|Exclude all unfavorable observations']

RUNTIMES=dict(python='3.12',javascript='22',java='21',cpp='C++20')

def base(kind,title,statement,difficulty,marks,explanation):
    return dict(schema_version=1,type=kind,title=title,statement=statement,difficulty=difficulty,topics=['role-fundamentals' if kind=='mcq' else kind],marks=marks,explanation=explanation)

def mcq(item,index,difficulty,marks):
    statement,*answers=item.split('|')
    # Deterministic rotation avoids a fixed first-answer key.
    shift=index%4
    ordered=answers[shift:]+answers[:shift]
    q=base('mcq',statement,statement,difficulty,marks,'Correct: '+answers[0]+'. The other choices do not satisfy the stated conditions.')
    q['mcq']=dict(selection='single',options=[dict(id='option'+str(i+1),text=a) for i,a in enumerate(ordered)],correct_option_ids=['option'+str(ordered.index(answers[0])+1)])
    return q


def coding(task,difficulty,marks,languages):
    if task=='sum':
        title='Sum of the first N integers';statement='Given N, print 1 + 2 + ... + N. For N = 0 print 0.'
        inputs=[0,1,2,3,5,10,11,50,99,100,101,999,1000,1234,9999,10000]
        answer=lambda x:x*(x+1)//2
        exprs=('n*(n+1)//2','n*(n+1)/2','n*(n+1)/2','n*(n+1)/2')
        read='N';constraints='0 <= N <= 10000';explanation='Use the arithmetic series identity N*(N+1)/2.'
    elif task=='divisible':
        title='Count divisible identifiers';statement='Count integers x in the inclusive range 1 to N divisible by A or B. Count values divisible by both only once.'
        inputs=[(1,1,1),(10,2,3),(20,4,6),(30,5,5),(50,7,11),(100,1,100),(10**12,2,3),(10**12-1,7,11),(999999999989,999983,999979),(10**11,1,999983),(10**12,1000000,1000000),(10**12,2,999983),(10**10,49,77),(10**12-7,97,101),(500000000003,3,9),(100000000019,997,991)]
        answer=lambda x:x[0]//x[1]+x[0]//x[2]-x[0]//(x[1]//gcd(x[1],x[2])*x[2])
        exprs=('n//a+n//b-n//(a//gcd(a,b)*b)','Math.floor(n/a)+Math.floor(n/b)-Math.floor(n/(a/gcd(a,b)*b))','n/a+n/b-n/(a/gcd(a,b)*b)','n/a+n/b-n/(a/std::gcd(a,b)*b)')
        read='N A B';constraints='1 <= N <= 10^12; 1 <= A,B <= 10^6';explanation='Use inclusion-exclusion and LCM = A / gcd(A,B) * B. Iterating to N is intentionally infeasible for large hidden cases.'
    elif task=='remainders':
        title='Sum periodic remainders';statement='Print the sum of i modulo M for every integer i from 0 through N inclusive.'
        inputs=[(0,1),(5,3),(10,1),(8,4),(20,7),(100,10)]+[(10**12-i*12347, m) for i,m in enumerate([2,3,7,10,97,100,997,9999,10000,8191])]
        answer=lambda x:((x[0]+1)//x[1])*(x[1]*(x[1]-1)//2)+((x[0]+1)%x[1])*(((x[0]+1)%x[1])-1)//2
        exprs=('((n+1)//m)*(m*(m-1)//2)+((n+1)%m)*(((n+1)%m)-1)//2','Math.floor((n+1)/m)*(m*(m-1)/2)+((n+1)%m)*(((n+1)%m)-1)/2','((n+1)/m)*(m*(m-1)/2)+((n+1)%m)*(((n+1)%m)-1)/2','((n+1)/m)*(m*(m-1)/2)+((n+1)%m)*(((n+1)%m)-1)/2')
        read='N M';constraints='0 <= N <= 10^12; 1 <= M <= 10000';explanation='Partition N+1 values into complete cycles of length M plus a remainder. Each full cycle sums to M*(M-1)/2.'
    else:
        title='Count all set bits';statement='For every integer from 0 through N inclusive, count the 1 bits in its binary representation. Print the total count.'
        inputs=[0,1,2,3,7,31]+[10**12-i*999983 for i in range(10)]
        def answer(n):
            result=0;p=1
            while p<=n:
                result+=((n+1)//(2*p))*p+max(0,(n+1)%(2*p)-p);p*=2
            return result
        exprs=None;read='N';constraints='0 <= N <= 10^12';explanation='For each bit position, count complete zero/one cycles and the remaining partial cycle. Complexity O(log N).'
    tests=[]
    for i,x in enumerate(inputs):
        raw=' '.join(map(str,x)) if isinstance(x,tuple) else str(x)
        tests.append(dict(id='case'+str(i+1),visibility='sample' if i<2 else 'hidden',input=raw+'\n',expected=str(answer(x))+'\n',weight=1,explanation='Example case.' if i<2 else ('Small boundary/control case.' if i<6 else 'Large performance case.' if task!='sum' else 'Boundary case.')))
    pyvars=read.lower().split();jsvars=','.join(pyvars)
    if exprs:
        py='from math import gcd\n'+(', '.join(pyvars)+' = map(int, input().split())\n' if len(pyvars)>1 else 'n = int(input())\n')+'print('+exprs[0]+')\n'
        js="const fs=require('fs'); const ["+jsvars+"]=fs.readFileSync(0,'utf8').trim().split(/\\s+/).map(Number); function gcd(a,b){while(b){[a,b]=[b,a%b];}return a;} console.log("+exprs[1]+");"
        java='import java.util.*; public class Main { static long gcd(long a,long b){while(b!=0){long t=a%b;a=b;b=t;}return a;} public static void main(String[] args){Scanner s=new Scanner(System.in);'+''.join('long '+v+'=s.nextLong();' for v in pyvars)+'System.out.println('+exprs[2]+');}}'
        cpp='#include <iostream>\n#include <numeric>\nint main(){long long '+','.join(pyvars)+';std::cin'+''.join('>>'+v for v in pyvars)+';std::cout<<('+exprs[3]+')<<"\\n";}'
    else:
        py='n=int(input())\ns=0\np=1\nwhile p<=n:\n s+=((n+1)//(2*p))*p+max(0,(n+1)%(2*p)-p)\n p*=2\nprint(s)\n'
        js="const n=Number(require('fs').readFileSync(0,'utf8').trim());let s=0;for(let p=1;p<=n;p*=2)s+=Math.floor((n+1)/(2*p))*p+Math.max(0,(n+1)%(2*p)-p);console.log(s);"
        java='import java.util.*; public class Main {public static void main(String[] args){long n=new Scanner(System.in).nextLong(),s=0;for(long p=1;p<=n;p*=2)s+=((n+1)/(2*p))*p+Math.max(0,(n+1)%(2*p)-p);System.out.println(s);}}'
        cpp='#include <iostream>\n#include <algorithm>\nint main(){long long n,s=0;std::cin>>n;for(long long p=1;p<=n;p*=2)s+=((n+1)/(2*p))*p+std::max(0LL,(n+1)%(2*p)-p);std::cout<<s<<"\\n";}'
    refs=dict(zip(LANGUAGES,[py,js,java,cpp]))
    starters=dict(python='# Read stdin and print the answer.\n',javascript="// Read stdin using fs.readFileSync(0,'utf8').\n",java='import java.util.*; public class Main {public static void main(String[] args){/* Read stdin and print the answer. */}}',cpp='#include <iostream>\nint main(){/* Read stdin and print the answer. */}\n')
    q=base('coding',title,statement,difficulty,marks,explanation)
    q['coding']=dict(contract='stdin_stdout',signature=None,harness_version='genhire_fn_v1',input_format='One line containing '+read+' separated by spaces.',output_format='One integer followed by a newline.',constraints=constraints,languages=languages,runtime_versions={l:RUNTIMES[l] for l in languages},starter_code={l:starters[l] for l in languages},reference_solutions={l:refs[l] for l in languages},limits=dict(time_ms=1000,memory_mb=256,output_kb=64),comparison='trim_trailing_whitespace',tests=tests)
    return q


def sql_question(index,difficulty,marks,engine):
    if index==0:
        schema='CREATE TABLE sales (id INTEGER PRIMARY KEY, team VARCHAR(40), amount INTEGER);'
        query="SELECT COALESCE(team, 'Unassigned') AS team_name, SUM(amount) AS total FROM sales GROUP BY COALESCE(team, 'Unassigned') ORDER BY team_name;"
        title='Revenue by team';statement="Return team_name and total revenue from sales. Treat NULL teams as Unassigned, ignore NULL amounts in SUM, retain groups whose total is NULL, and order by team_name ascending."
        fixtures=[([(1,'East',10),(2,'East',20),(3,'West',7)],[['East',30],['West',7]]),([],[]),([(1,None,8),(2,'Unassigned',2)],[['Unassigned',10]]),([(1,'East',None),(2,'West',0)],[['East',None],['West',0]]),([(1,'East',-5),(2,'East',5)],[['East',0]]),([(1,'East',4),(2,'East',4),(3,'West',9)],[['East',8],['West',9]])]
        cols=['team_name','total'];table='sales';explanation='Group by the normalized team expression; SUM preserves duplicate amounts and ignores NULL amounts.'
    else:
        schema='CREATE TABLE customers (id INTEGER PRIMARY KEY, name VARCHAR(40)); CREATE TABLE orders (id INTEGER PRIMARY KEY, customer_id INTEGER);'
        query='SELECT c.id AS customer_id, c.name AS customer_name FROM customers c LEFT JOIN orders o ON o.customer_id=c.id WHERE o.id IS NULL ORDER BY c.id;'
        title='Customers with no orders';statement='Return customer_id and customer_name for customers with no matching orders, ordered by customer_id. Orphan and NULL order customer IDs must not remove customers.'
        fixtures=[(([(1,'Ada'),(2,'Ben')],[(1,1)]),[[2,'Ben']]),(([],[]),[]),(([(1,'Ada')],[]),[[1,'Ada']]),(([(1,'Ada')],[(1,1),(2,1)]),[]),(([(1,'Ada'),(2,'Ada')],[(1,None),(2,99)]),[[1,'Ada'],[2,'Ada']]),(([(3,'Cia'),(7,'Dee')],[(1,7)]),[[3,'Cia']])]
        cols=['customer_id','customer_name'];explanation='Use a left anti-join, testing the nonnullable order primary key. Keep customer identities distinct.'
    def literal(v): return 'NULL' if v is None else str(v) if isinstance(v,int) else "'"+v.replace("'","''")+"'"
    def inserts(name,rows):return ''.join('INSERT INTO '+name+' VALUES ('+','.join(literal(v) for v in row)+');' for row in rows)
    datasets=[]
    for i,(rows,expected) in enumerate(fixtures):
        seed=inserts(table,rows) if index==0 else inserts('customers',rows[0])+inserts('orders',rows[1])
        datasets.append(dict(id='dataset'+str(i+1),visibility='sample' if i==0 else 'hidden',seed_sql=seed,columns=cols,expected_rows=expected,weight=1,explanation='Independent fixture covering empty, duplicate, NULL or unmatched data.'))
    q=base('sql',title,statement,difficulty,marks,explanation)
    q['sql']=dict(engine=engine,engine_version='17' if engine=='postgresql' else '8.4',schema_sql=schema,reference_query=query,ordered=True,numeric_tolerance=0,time_ms=2000,datasets=datasets)
    return q


def build_template(role,engine='postgresql',languages=None,specialization='general'):
    if engine not in ('postgresql','mysql') or specialization not in ('general','frontend','backend','full_stack'):
        raise WorkflowError('invalid_template','Unsupported template settings.',400)
    languages=LANGUAGES[:] if languages is None else languages
    if not isinstance(languages,list) or not languages or any(not isinstance(l,str) or l not in LANGUAGES for l in languages) or len(set(languages))!=len(languages):
        raise WorkflowError('invalid_template','Choose supported unique languages.',400)
    preset=template(role);questions=[]
    items=ROLE_ITEMS.get(role,ROLE_ITEMS['sde'])+COMMON_ITEMS
    for section in preset['sections']:
        difficulties=[d for d in ('easy','medium','hard') for _ in range(section['difficulty'][d])]
        for i,(difficulty,marks) in enumerate(zip(difficulties,section['marks'])):
            if section['type']=='mcq': q=mcq(items[i],i,difficulty,marks)
            elif section['type']=='sql': q=sql_question(i,difficulty,marks,engine)
            else:
                task='sum' if difficulty=='easy' else 'bits' if difficulty=='hard' else ('remainders' if role=='data_scientist' and i==1 else 'divisible')
                q=coding(task,difficulty,marks,languages)
            questions.append(validate_question(q))
    oa=dict(template_id=role,specialization=specialization,source='manual',instructions='Authored starter: review role fit, wording, answers and test coverage before activation.',languages=languages,sql_engine=engine,coding_contract='stdin_stdout',mcq_mode='single',sections=preset['sections'],timer_mode='shared',duration_minutes=preset['duration_minutes'],revisit_allowed=True,proctoring_level='basic',variant_count=1,advanced_analytics=False,plagiarism_check=False)
    blueprint_match(oa,questions)
    return dict(oa=oa,questions=questions,template_revision='2026-10-21-v1')


def apply_template(authoring,actor,role,key,engine='postgresql',languages=None,specialization='general'):
    authoring.authorize(actor,True)
    built=build_template(role,engine,languages,specialization)
    def save(session):
        result=[];owner=str(actor['_id'])
        for content in built['questions']:
            oid=ObjectId();q=dict(_id=oid,question_id=str(oid),revision=1,owner_id=owner,pool='recruitment',content=deepcopy(content),content_hash=request_identity(content),source='template',suite_policy='oa_test_suite_v2',created_by=owner,previous_version_id=None,created_at=datetime.now(timezone.utc))
            authoring.db.question_versions.insert_one(q,session=session)
            result.append(authoring.serialize(q))
        authoring.audit(actor,owner,'role_template_created',role,session)
        return dict(questions=result,oa=built['oa'],template_revision=built['template_revision'])
    return authoring.mutate(actor,key,dict(action='apply_role_template',role=role,engine=engine,languages=languages,specialization=specialization,revision=built['template_revision']),save)

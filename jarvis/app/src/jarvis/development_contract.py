"""Pure shared contract for source inspection and isolated candidate jobs.

No host execution, credentials, application data or model-granted authority.
"""
import ast,difflib,hashlib,json,re
from copy import deepcopy
from pathlib import PurePosixPath

SCOPES={
 'preparation':{'label':'Weekly preparation summaries','files':{
  'src/jarvis/assistant_priorities.py':['preparation_groups','priority_key','fallback'],
  'src/jarvis/preparation_wording.py':['join_words','activity_name','kit_item','usual_preparation']},
  'tests':['test_priority_summary','test_preparation_wording','test_memory_followthrough']},
 'memory':{'label':'Relevant memory lookup','files':{'src/jarvis/companion_store.py':['CompanionStore.relevant']},
  'tests':['test_companion_memory','test_memory_followthrough']},
 'conversation':{'label':'Conversation references','files':{'src/jarvis/companion_read_context.py':['duration_quotes','preparation_goals','meal_remainder']},
  'tests':['test_companion_read_context','test_conversation_topics']},
 'fixture':{'label':'Fictional sandbox canary','files':{'src/jarvis/workshop_fixture.py':['join_items']},'tests':['test_workshop_fixture']}}
PUBLIC_SCOPES=tuple(k for k in SCOPES if k!='fixture')
MAX_SOURCE_BYTES=8_000_000
MAX_CODE=2400

def sha(value):
    if isinstance(value,str):value=value.encode('utf-8')
    return hashlib.sha256(value).hexdigest()

def canonical(value):return json.dumps(value,sort_keys=True,separators=(',',':'),ensure_ascii=False)

def safe_path(value):
    if not isinstance(value,str) or len(value)>160 or '\\' in value or not re.fullmatch(r'(?:src/jarvis|validation)/[a-zA-Z0-9_/]+\.py',value):raise ValueError('Unsupported source path')
    path=PurePosixPath(value)
    if path.is_absolute() or str(path)!=value or any(p in ('','..','.') for p in path.parts):raise ValueError('Invalid source path')
    return value

def code(value,maximum=MAX_CODE):
    if not isinstance(value,str) or not value.strip() or len(value)>maximum or any(ord(c)<32 and c not in '\n\t\r' for c in value):raise ValueError('Invalid candidate code')
    return value.replace('\r\n','\n')

def validate_snapshot(raw):
    if not isinstance(raw,dict) or set(raw)!={'schema','version','commit','kind','files','digest'} or type(raw['schema']) is not int or raw['schema']!=1 or raw['kind'] not in ('public_source','fictional_fixture'):raise ValueError('Invalid source snapshot')
    if not isinstance(raw['version'],str) or not isinstance(raw['commit'],str) or not re.fullmatch(r'0\.45\.\d+',raw['version']) or not re.fullmatch(r'[0-9a-f]{40}',raw['commit']):raise ValueError('Invalid snapshot provenance')
    if not isinstance(raw['files'],dict) or not 1<=len(raw['files'])<=800:raise ValueError('Invalid snapshot file set')
    size=0
    for name,text in raw['files'].items():
        safe_path(name)
        if name=='validation/test_workshop_candidate.py':raise ValueError('Reserved regression-test path')
        if not isinstance(text,str) or len(text)>300_000:raise ValueError('Invalid snapshot text')
        size+=len(text.encode('utf-8'))
    if size>MAX_SOURCE_BYTES:raise ValueError('Snapshot too large')
    unsigned={k:v for k,v in raw.items() if k!='digest'}
    if raw['digest']!=sha(canonical(unsigned)):raise ValueError('Snapshot digest mismatch')
    return deepcopy(raw)

def make_snapshot(files,version,commit,*,fixture=False):
    raw={'schema':1,'version':version,'commit':commit,'kind':'fictional_fixture' if fixture else 'public_source','files':files}
    raw['digest']=sha(canonical(raw));return validate_snapshot(raw)

def function_node(text,symbol):
    tree=ast.parse(text);nodes=tree.body
    for part in symbol.split('.'):
        found=next((n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==part),None)
        if found is None:raise ValueError('Inspected function is absent')
        nodes=getattr(found,'body',[])
    if not isinstance(found,(ast.FunctionDef,ast.AsyncFunctionDef)):raise ValueError('Expected a function')
    return found

def scope_catalog(snapshot,scope):
    if scope not in SCOPES or (scope=='fixture')!=(snapshot['kind']=='fictional_fixture'):raise ValueError('Unsupported workspace component')
    out=[]
    for path,symbols in SCOPES[scope]['files'].items():
        text=snapshot['files'].get(path)
        if text is None:continue
        for symbol in symbols:
            node=function_node(text,symbol)
            preview='\n'.join(text.splitlines()[node.lineno-1:node.end_lineno])[:360]
            out.append({'path':path,'symbol':symbol,'start':node.lineno,'end':node.end_lineno,'module_sha256':sha(text),'preview':preview})
    if not out:raise ValueError('No supported code in this snapshot')
    return out

def inspect_source(snapshot,scope,path,symbol):
    row=next((r for r in scope_catalog(snapshot,scope) if r['path']==path and r['symbol']==symbol),None)
    if row is None:raise ValueError('Function is outside the approved component')
    lines=snapshot['files'][path].splitlines(keepends=True);text=''.join(lines[row['start']-1:row['end']])
    if len(text)>6500 or row['end']-row['start']>100:raise ValueError('Function needs a narrower future inspection contract')
    return {**row,'source':text,'snapshot':snapshot['digest'],'version':snapshot['version']}

def _outside_function(text,symbol):
    tree=ast.parse(text);nodes=tree.body
    for part in symbol.split('.'):
        found=next((n for n in nodes if isinstance(n,(ast.ClassDef,ast.FunctionDef,ast.AsyncFunctionDef)) and n.name==part),None)
        if found is None:raise ValueError('Selected function changed identity')
        nodes=found.body
    found.body=[ast.Pass()]
    return ast.dump(tree,include_attributes=False)

def apply_candidate(snapshot,scope,patch):
    required={'path','symbol','module_sha256','old','new','test_source'}
    if not isinstance(patch,dict) or set(patch)!=required:raise ValueError('Invalid candidate fields')
    inspected=inspect_source(snapshot,scope,patch['path'],patch['symbol'])
    if patch['module_sha256']!=inspected['module_sha256']:raise ValueError('Candidate source changed')
    old,new=code(patch['old']),code(patch['new']);original=snapshot['files'][patch['path']]
    if old==new or inspected['source'].count(old)!=1 or original.count(old)!=1:raise ValueError('Replacement must quote one unique inspected span')
    changed=original.replace(old,new,1)
    ast.parse(changed)
    if _outside_function(original,patch['symbol'])!=_outside_function(changed,patch['symbol']):raise ValueError('Only the selected function body may change')
    test=code(patch['test_source'],2400);tree=ast.parse(test)
    tests=[n for n in ast.walk(tree) if isinstance(n,(ast.FunctionDef,ast.AsyncFunctionDef)) and n.name.startswith('test_')]
    if not 1<=len(tests)<=3:raise ValueError('Supply one to three regression tests')
    files=dict(snapshot['files']);files[patch['path']]=changed;files['validation/test_workshop_candidate.py']=test
    diff=''.join(difflib.unified_diff(original.splitlines(True),changed.splitlines(True),fromfile=patch['path'],tofile=patch['path']))
    diff+=''.join(difflib.unified_diff([],test.splitlines(True),fromfile='/dev/null',tofile='validation/test_workshop_candidate.py'))
    flags=[]
    for word in ('exec','eval','__import__','subprocess','socket','system','popen'):
        if re.search(r'\b'+word+r'\b',new+'\n'+test):flags.append('review_'+word)
    return {'files':files,'diff':diff,'risk_flags':flags,'candidate_sha256':sha(canonical({'snapshot':snapshot['digest'],'scope':scope,'patch':patch}))}

def validate_job(snapshot,body):
    if not isinstance(body,dict) or set(body)!={'id','snapshot','scope','patch'}:raise ValueError('Unsupported test-job fields')
    if not re.fullmatch(r'W[0-9a-f]{12}',str(body['id'])) or body['snapshot']!=snapshot['digest']:raise ValueError('Invalid job identity or source')
    candidate=apply_candidate(snapshot,body['scope'],body['patch'])
    return candidate

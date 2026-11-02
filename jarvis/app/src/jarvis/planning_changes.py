"""Bounded changes between complete planning checks, never a transcript or notification."""
from copy import deepcopy
from datetime import datetime,timedelta
import json,re
from zoneinfo import ZoneInfo
from jarvis.companion_store import digest,secret,instruction_attempt

KEY='planning_change_journal'
FIELDS=('title','activity','person','name','start','end','venue','venue_basis','gaps')

def aware(value):
    if not isinstance(value,str):raise ValueError('Invalid stored date')
    at=datetime.fromisoformat(value)
    if at.tzinfo is None:raise ValueError('Stored date needs timezone')
    return at

def valid_item(row):
    if not isinstance(row,dict):return False
    if not set((*FIELDS,'remaining','ready'))<=set(row):return False
    if any(not isinstance(row.get(k),str) or len(row[k])>500 for k in FIELDS if k not in ('gaps','person')):return False
    if row.get('person') is not None and (not isinstance(row['person'],str) or len(row['person'])>100):return False
    if any(not isinstance(row.get(k),list) or len(row[k])>40 or any(not isinstance(v,str) or len(v)>500 for v in row[k]) for k in ('gaps','remaining','ready')):return False
    return aware(row['end'])>=aware(row['start'])

def change_question(text):
    return bool(re.search(r"\b(?:what(?:['’]s| has)? changed|any (?:new )?(?:changes|updates)|what is different|hva (?:har )?endret|noe (?:nytt|endret))\b",text,re.I))

class PlanningChanges:
    def __init__(self,owner):self.owner=owner
    def read(self):
        row=self.owner.store.db.execute('SELECT value FROM assistant_state WHERE key=?',(KEY,)).fetchone()
        if not row:return None
        try:
            value=json.loads(row[0])
            if value.get('schema_version')!=1 or not isinstance(value.get('snapshot'),dict) or len(value['snapshot'])>80 or not isinstance(value.get('changes'),list) or len(value['changes'])>24:return None
            if not isinstance(value.get('scope'),str) or type(value.get('checks')) is not int or value['checks']<1:return None
            if aware(value['checked_at'])<aware(value['baseline_at']):return None
            if any(not isinstance(k,str) or not valid_item(v) for k,v in value['snapshot'].items()):return None
            for row in value['changes']:
                if not isinstance(row,dict) or row.get('kind') not in ('new','updated','left_view') or not valid_item(row.get('current')):return None
                if any(not isinstance(row.get(k),str) for k in ('item','fingerprint')):return None
                if not isinstance(row.get('fields'),list) or any(v not in (*FIELDS,'new','preparation') for v in row['fields']):return None
                aware(row['recorded_at'])
            return value
        except (ValueError,TypeError,AttributeError,KeyError):return None
    def scope(self):return digest([sorted(self.owner.container.proactive_allowed_entities),self.owner.store.generation])
    def item(self,item):
        row={k:deepcopy(item[k]) for k in FIELDS}
        row['remaining']=list(item['followthrough']['remaining']);row['ready']=list(item['followthrough']['reported_ready'])
        return row
    def observe(self,items):
        # Only the worker commits a complete observed snapshot. Merely reading
        # the dashboard or asking a question does not acknowledge a change.
        now=self.owner.now();old=self.read();scope=self.scope()
        snapshot={i['id']:self.item(i) for i in list(items.values())[:80]}
        if secret(json.dumps(snapshot)) or instruction_attempt(json.dumps(snapshot)):return
        valid=bool(old and old.get('scope')==scope)
        changes=[r for r in old.get('changes',[]) if datetime.fromisoformat(r['recorded_at'])>=now-timedelta(days=1)] if valid else []
        previous=old['snapshot'] if valid else None
        if previous is not None:
            for key,current in snapshot.items():
                before=previous.get(key)
                if before==current:continue
                differences=['new'] if before is None else [k for k in FIELDS if before.get(k)!=current.get(k)]
                if before and (before.get('ready')!=current['ready'] or before.get('remaining')!=current['remaining']):differences.append('preparation')
                if not differences:continue
                fingerprint=digest([key,before,current])
                if not any(r['fingerprint']==fingerprint for r in changes):
                    changes.append({'fingerprint':fingerprint,'item':key,'kind':'new' if before is None else 'updated','fields':differences,'current':current,'recorded_at':now.isoformat()})
            for key,before in previous.items():
                if key in snapshot or datetime.fromisoformat(before['end'])<=now:continue
                fingerprint=digest([key,before,None])
                if not any(r['fingerprint']==fingerprint for r in changes):changes.append({'fingerprint':fingerprint,'item':key,'kind':'left_view','fields':[],'current':before,'recorded_at':now.isoformat()})
        value={'schema_version':1,'scope':scope,'baseline_at':old['baseline_at'] if valid else now.isoformat(),'checked_at':now.isoformat(),'checks':old.get('checks',0)+1 if valid else 1,'snapshot':snapshot,'changes':changes[-24:]}
        with self.owner.store.db:self.owner.store.db.execute('INSERT INTO assistant_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(KEY,json.dumps(value,ensure_ascii=False,sort_keys=True)))
    def project(self,live,members=(),items=None):
        data=self.read()
        if not live or not data or data.get('scope')!=self.scope():return {'status':'unavailable','changes':[],'read_only':True}
        if items is not None and data['snapshot']!={i['id']:self.item(i) for i in list(items.values())[:80]}:return {'status':'unavailable','changes':[],'read_only':True}
        now=self.owner.now();items=[];seen=set()
        for row in reversed(data['changes']):
            if row['item'] in seen or members and row['current']['person'] not in members:continue
            if datetime.fromisoformat(row['recorded_at'])<now-timedelta(days=1):continue
            current=data['snapshot'].get(row['item'])
            if row['kind']!='left_view' and current!=row['current']:continue
            if row['kind']=='left_view' and current is not None:continue
            if datetime.fromisoformat(row['current']['end'])<=now:continue
            seen.add(row['item']);items.append({k:deepcopy(row[k]) for k in ('kind','fields','current','recorded_at')})
        return {'status':'ready' if data['checks']>1 else 'baseline','baseline_at':data['baseline_at'],'checked_at':data['checked_at'],'changes':items[:8],
                'coverage':'Changes between complete checks of the connected preparation view over the last day; not continuous calendar monitoring.','read_only':True}

def lines(projection):
    if projection['status']=='unavailable':return ['I cannot compare changes while the preparation sources need another check.']
    if projection['status']=='baseline':return ['I have the first complete preparation check. I need a later complete check before I can describe changes.']
    if not projection['changes']:return ['No differences were found between the complete preparation checks I retained. Other plans may exist.']
    result=[]
    for row in projection['changes'][:5]:
        item=row['current'];at=datetime.fromisoformat(item['start']).astimezone(ZoneInfo('Europe/Oslo'));subject=item['name']+"'s "+item['activity']
        if row['kind']=='left_view':result.append(subject+' is no longer in the checked upcoming preparation view; that does not establish a cancellation.');continue
        if row['kind']=='new':result.append(subject+' was added to the checked preparation view for '+at.strftime('%A at %H:%M')+'.');continue
        fields=row['fields'];parts=[]
        if any(v in fields for v in ('start','end')):parts.append('is now scheduled for '+at.strftime('%A at %H:%M'))
        if any(v in fields for v in ('venue','venue_basis')):parts.append('now lists '+(item['venue'] or 'an unconfirmed venue')+' ('+item['venue_basis']+')')
        if 'preparation' in fields:parts.append('has an updated preparation report'+(': reported ready: '+', '.join(item['ready']) if item['ready'] else '')+('; still to check: '+', '.join(item['remaining']) if item['remaining'] else ''))
        if not parts:parts.append('has updated details in the latest preparation check')
        result.append(subject+' '+', and '.join(parts)+'.')
    return result

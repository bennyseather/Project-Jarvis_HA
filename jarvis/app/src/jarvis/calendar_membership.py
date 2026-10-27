"""Shared-calendar attribution. Explicit assignments, never identity guesses."""
from datetime import datetime,timezone
import hashlib
import json

PREFIX='JARVIS-PLAN/1 '
CATEGORIES=('school','work','sport','music','health','family','travel','other')

def unique_json(raw):
    def pairs(items):
        out={}
        for key,value in items:
            if key in out:raise ValueError('Duplicate field')
            out[key]=value
        return out
    return json.loads(raw,object_pairs_hook=pairs)

def stamp(value):
    if isinstance(value,dict):value=value.get('dateTime') or value.get('date')
    if not isinstance(value,str):raise ValueError('Missing date')
    if len(value)==10:return value
    parsed=datetime.fromisoformat(value.replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('Missing timezone')
    return parsed.astimezone(timezone.utc).isoformat()

def identity(event):
    fields=[event.get('summary',event.get('title','')),stamp(event['start']),stamp(event['end'])]
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def source_fingerprint(event):
    fields=[identity(event),*[str(event.get(k) or '') for k in ('description','location')]]
    return hashlib.sha256(json.dumps(fields,ensure_ascii=False,separators=(',',':')).encode()).hexdigest()

def assignment(event,people,legacy=None,active=False):
    """Malformed metadata is unassigned, never silently attributed to Mia."""
    raw=event.get('description') or ''
    if not isinstance(raw,str):raw=''
    if raw.startswith(PREFIX):
        try:
            first,_,notes=raw.partition('\n');data=unique_json(first[len(PREFIX):])
            if set(data)!={'members','category','id'}:raise ValueError()
            owners=data['members']
            if not isinstance(owners,list) or not owners or len(owners)>len(people) or len(set(owners))!=len(owners) or any(not isinstance(o,str) or o not in people for o in owners):raise ValueError()
            if data['category'] not in CATEGORIES or not isinstance(data['id'],str) or not 8<=len(data['id'])<=64:raise ValueError()
            return {'members':sorted(owners),'category':data['category'],'notes':notes,'planner_id':data['id'],'basis':'explicit calendar assignment'}
        except (ValueError,TypeError,KeyError):return {'members':[],'category':'other','notes':raw,'planner_id':None,'basis':'invalid assignment; choose members'}
    try:saved=(legacy or {}).get(identity(event))
    except (ValueError,KeyError,TypeError):saved=None
    if saved and saved.get('_fingerprint') and saved['_fingerprint']!=source_fingerprint(event):saved=None
    if saved and set(saved.get('members',[])).issubset(people):
        return {**saved,'notes':raw,'planner_id':None,'basis':saved.get('_basis','confirmed existing appointment assignment')}
    return {'members':[] if active else ['mia'],'category':'other','notes':raw,'planner_id':None,
            'basis':'unassigned phone/calendar entry' if active else 'previous Mia-only calendar rule'}

def description(members,category,identifier,notes):
    return PREFIX+json.dumps({'members':sorted(members),'category':category,'id':identifier},ensure_ascii=False,separators=(',',':'))+'\n'+notes

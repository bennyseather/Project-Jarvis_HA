"""Confirmed, exact-scoped activity profiles in the existing household document.

No new database, model writes, calendar edits or action permissions. Proposals
are committed only by HouseholdEdits' existing review/hash/atomic-save workflow.
Usual facts qualify fresh calendar records, never establish attendance or times.
"""
from copy import deepcopy
from datetime import datetime,timezone
import re
import unicodedata
import uuid

from jarvis import event_activity
from jarvis.household_speaker import shared_knowledge_enabled

FIELDS={'id','person','source','title','activity','equipment','preparation','usual_venue',
        'duration_minutes','recorded_on','provenance'}
PREFIX=r'(?:remember|save|note|forget|remove|delete)\s+(?:that\s+)?'
TARGET=r'(.+?)\s+activity\s+"([^"\n]+)"\s+in\s+the\s+(family|work|travel)\s+calendar'


def title_key(value):
    # Ignore decorative emoji only, not meaningful words, numbers or punctuation.
    value=unicodedata.normalize('NFKC',value).casefold()
    return ' '.join(''.join(c for c in value if unicodedata.category(c) not in ('So','Sk','Cf')
                            and c not in '\ufe0e\ufe0f').split())


def safe(value,maximum):
    return (isinstance(value,str) and 1<=len(value)<=maximum and bool(title_key(value)) and
            not re.search(r'https?://|www\.|password|api[_ -]?key|access[_ -]?token|private key|'
                r'system\s+prompt|ignore\b.{0,30}\binstructions|\b(?:sudo|curl|powershell|unlock|delete|transfer|impersonate)\b',value,re.I))


def validate(records,members):
    if not isinstance(records,list) or len(records)>40:raise ValueError('Activity profile limit')
    keys=set();ids=set()
    for r in records:
        if not isinstance(r,dict) or set(r)!=FIELDS:raise ValueError('Activity schema')
        if any(not isinstance(r[k],str) for k in ('person','source','title')):raise ValueError('Activity identity needs text')
        key=(r['person'],r['source'],title_key(r['title']))
        if (r['person'] not in members or r['source'] not in ('family','work','travel') or key in keys or
            not isinstance(r['id'],str) or not re.fullmatch(r'[a-f0-9]{8}',r['id']) or r['id'] in ids or
            not safe(r['title'],160) or not safe(r['activity'],120) or
            r['provenance']!='Confirmed shared household conversation' or
            not isinstance(r['recorded_on'],str)):
            raise ValueError('Invalid activity identity')
        stamp=datetime.fromisoformat(r['recorded_on'])
        if stamp.tzinfo is None:raise ValueError('Activity provenance needs timezone')
        if not isinstance(r['equipment'],list) or len(r['equipment'])>12 or any(not safe(v,100) for v in r['equipment']):
            raise ValueError('Invalid activity equipment')
        if len({title_key(v) for v in r['equipment']})!=len(r['equipment']):raise ValueError('Duplicate equipment')
        if r['preparation'] is not None and not safe(r['preparation'],240):raise ValueError('Invalid preparation')
        if r['usual_venue'] is not None and not safe(r['usual_venue'],180):raise ValueError('Invalid usual venue')
        if r['duration_minutes'] is not None and (type(r['duration_minutes']) is not int or not 1<=r['duration_minutes']<=1440):
            raise ValueError('Invalid usual duration')
        keys.add(key);ids.add(r['id'])


def normalise_command(text):return ' '.join(str(text).replace('’',"'").replace('“','"').replace('”','"').strip().rstrip('.!?').split())


def is_request(text):
    value=normalise_command(text)
    return bool(re.match(r'^(?:show|list)\b.*\bactivity profiles?\b',value,re.I) or
                re.match(r'^'+PREFIX+r'.+\bactivity\s+"',value,re.I))


def proposal(text,document):
    value=normalise_command(text)
    if not re.match(r'^'+PREFIX+r'.+\bactivity\s+"',value,re.I):return None
    if not shared_knowledge_enabled(document):raise ValueError('Shared household knowledge is disabled. Nothing was proposed.')
    match=re.fullmatch(PREFIX+TARGET+r'(?:\s+(.+))?',value,re.I)
    if not match:raise ValueError('Use a name, exact quoted calendar title and calendar, for example: Remember Alex\'s activity "Club" in the family calendar means "robotics".')
    name=re.sub(r"'s$",'',match[1],flags=re.I);title,source,change=match[2],match[3].casefold(),match[4]
    person=next((p['id'] for p in document['members'] if p['preferred_name'].casefold()==name.casefold()),None)
    if not person or not safe(title,160):raise ValueError('Use a known household name and a safe, exact calendar title.')
    records=document.get('activity_profiles',[])
    existing=next((r for r in records if (r['person'],r['source'],title_key(r['title']))==(person,source,title_key(title))),None)
    deleting=bool(re.match(r'^(forget|remove|delete)\b',value,re.I))
    if deleting:
        if change or not existing:raise ValueError('That exact activity profile was not found. Show activity profiles first.')
        return {'remove':existing['id'],'summary':'Remove '+name+"'s activity profile for \""+title+'" in the '+source+' calendar; calendar appointments remain unchanged'}
    meaning=re.fullmatch(r'means\s+"([^"\n]+)"',change or '',re.I)
    if not existing and not meaning:raise ValueError('First define what this exact calendar entry means, then add usual details after confirming it.')
    record=deepcopy(existing) if existing else {'id':uuid.uuid4().hex[:8],'person':person,'source':source,'title':title,
        'activity':'','equipment':[],'preparation':None,'usual_venue':None,'duration_minutes':None,
        'recorded_on':datetime.now(timezone.utc).isoformat(),'provenance':'Confirmed shared household conversation'}
    reset=''
    if meaning:
        if existing and title_key(record['activity'])!=title_key(meaning[1]):
            record.update(equipment=[],preparation=None,usual_venue=None,duration_minutes=None)
            reset='; clear old usual equipment, venue, preparation and duration because the activity kind changed'
        record['activity']=meaning[1]
    else:
        equipment=re.fullmatch(r'(usually needs|also needs)\s+"([^"\n]+)"',change or '',re.I)
        venue=re.fullmatch(r'usually takes place at\s+"([^"\n]+)"',change or '',re.I)
        preparation=re.fullmatch(r'usual preparation is\s+"([^"\n]+)"',change or '',re.I)
        duration=re.fullmatch(r'usually lasts\s+(\d+)\s+minutes?',change or '',re.I)
        if equipment:
            items=[v.strip() for v in equipment[2].split(',')]
            if equipment[1].casefold()=='also needs':items=record['equipment']+items
            record['equipment']=list({title_key(v):v for v in items}.values())
        elif venue:record['usual_venue']=venue[1]
        elif preparation:record['preparation']=preparation[1]
        elif duration:record['duration_minutes']=int(duration[1])
        else:raise ValueError('Specify means "activity", usually needs "items", usually takes place at "venue", usual preparation is "detail", or usually lasts 60 minutes.')
    validate([record],{p['id'] for p in document['members']})
    if existing and all(record[k]==existing[k] for k in FIELDS-{'recorded_on'}):return {'unchanged':True}
    record['recorded_on']=datetime.now(timezone.utc).isoformat()
    detail=record['activity'] if meaning else change
    return {'record':record,'summary':name+"'s exact entry \""+title+'" in the '+source+' calendar: '+detail+reset+
        '. Scope is this person/calendar/title only; usual details do not confirm attendance or change current calendar facts'}


def install(document,change):
    if change.get('unchanged'):return
    records=document.setdefault('activity_profiles',[])
    identifier=change.get('remove') or change['record']['id']
    records[:]=[r for r in records if r['id']!=identifier]
    if 'record' in change:records.append(change['record'])
    validate(records,{p['id'] for p in document['members']})


def view(text,profile):
    value=normalise_command(text)
    if not re.match(r'^(?:show|list)\b.*\bactivity profiles?\b',value,re.I):return None
    def result(message,status='success'):return {'status':status,'message':message,'provider':'activity_profiles','read_only':True,'cacheable':False}
    if not shared_knowledge_enabled(profile._data):return result('Shared household activity knowledge is disabled.','unavailable')
    who=re.fullmatch(r'(?:show|list)(?:\s+(.+?))?\s+activity profiles?',value,re.I)
    if not who:return result('Say show activity profiles, or show a named household member\'s activity profiles.','clarification_required')
    name=re.sub(r"'s$",'',who[1] or '',flags=re.I)
    if name.casefold() in ('all','household'):name=''
    person=next((p for p in profile._data['members'] if p['preferred_name'].casefold()==name.casefold()),None)
    if name and not person:return result('Please use a known household member\'s name.','clarification_required')
    records=[r for r in profile._data.get('activity_profiles',[]) if not person or r['person']==person['id']]
    if not records:return result('No confirmed activity profiles are saved for that selection yet.')
    names={p['id']:p['preferred_name'] for p in profile._data['members']}
    lines=[names[r['person']]+': "'+r['title']+'" ('+r['source']+') means '+r['activity']+
        '; usual equipment: '+(', '.join(r['equipment']) or 'not recorded')+
        '; usual venue: '+(r['usual_venue'] or 'not recorded')+
        '; usual preparation: '+(r['preparation'] or 'not recorded')+
        '; usual duration: '+(str(r['duration_minutes'])+' minutes' if r['duration_minutes'] else 'not recorded') for r in records[:8]]
    return result('\n'.join(lines)+('\nMore profiles are saved; ask for one person.' if len(records)>8 else ''))


def match(document,event):
    if not shared_knowledge_enabled(document):return None
    if event.get('_activity_source_complete') is False:return None
    record=next((r for r in document.get('activity_profiles',[]) if
        event['owners']==[r['person']] and event['source']==r['source'] and title_key(event['text'])==title_key(r['title'])),None)
    if not record:return None
    kind=event_activity.requirement(record['activity'],[])
    clauses=[event['text'],*event.get('description_units',[])]
    if any(re.search(r'\b(?:cancel\w*|avlyst)\b',v,re.I) for v in clauses):return None
    # Positive current subtype evidence overrides a conflicting usual mapping.
    current=event_activity.requirement(' '.join(event_activity.assertions(event)),[])
    if any(k in event_activity.SPECIFIC for k in current['groups']) and not event_activity.support(kind,event):return None
    for v in clauses:
        # An explicit current definition of an unfamiliar kind also wins. Do
        # not force it into the usual type just because our lexical groups do
        # not include that activity yet.
        definition=re.match(r'^(?:this|today|this session|this activity)\s+is\s+(.+)',v,re.I)
        if definition and not event_activity.support(kind,{'text':definition[1],'description_units':[]}):return None
        if event_activity.UNCERTAIN.search(v) and (any(event_activity.PATTERNS[k].search(v) for k in kind['groups']) or
                any(re.search(r'(?<!\w)'+re.escape(w)+r'(?!\w)',event_activity.normalise(v)) for w in kind['literals'])):return None
    return record


def notes(events,mode):
    result=[]
    for e in events:
        r=e.get('activity_profile')
        if not r:continue
        pieces=[];name=e['owner_name']
        if mode=='location':
            if not e['location'] and r['usual_venue']:pieces.append(name+"'s usual "+r['activity']+' venue is "'+r['usual_venue']+'"; this appointment\'s venue is not confirmed.')
        else:
            if not e['description_units']:
                if r['equipment']:pieces.append(name+"'s usual equipment for "+r['activity']+' includes '+', '.join('"'+v+'"' for v in r['equipment'][:3])+'.')
                if r['preparation']:pieces.append(name+"'s usual preparation for "+r['activity']+' is "'+r['preparation']+'".')
            if not e['location'] and r['usual_venue']:pieces.append(name+"'s usual "+r['activity']+' venue is "'+r['usual_venue']+'"; check it for this appointment.')
            if e['all_day'] and r['duration_minutes']:pieces.append(name+"'s usual "+r['activity']+' lasts '+str(r['duration_minutes'])+' minutes; this is not a confirmed duration for the all-day calendar entry.')
        bounded=[]
        for piece in pieces:
            if len(' '.join(bounded+[piece]))<=500:bounded.append(piece)
        if bounded:result.append({'text':' '.join(bounded),'events':[e['id']],'origin':'activity_profile'})
    return result

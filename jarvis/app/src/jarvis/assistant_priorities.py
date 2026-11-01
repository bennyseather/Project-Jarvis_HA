"""Read-only next-step evidence and local-Qwen synthesis.

Only calendar-version-bound reports can mark a preparation step ready. Memories
can explain relevance, never supply a packed flag, a booking or an instruction.
"""
import asyncio,re
from datetime import datetime
from jarvis.companion_memory import local_json
from jarvis.companion_store import secret,instruction_attempt

def next_steps(item,now):
    gaps=list(item['gaps'])
    remaining=[s['text'] for s in item['checklist'] if not s['ready']]
    ready=[s['text'] for s in item['checklist'] if s['ready']]
    in_progress=not item['all_day'] and datetime.fromisoformat(item['start'])<=now
    actions={'person':'Confirm who this appointment is for','venue':'Confirm the venue',
      'venue_conflict':'Resolve the difference between the calendar and reported venue',
      'preparation':'Check what to bring or prepare'}
    steps=[actions[g] for g in gaps if g in actions]
    steps.extend('Check '+s for s in remaining)
    return {'remaining':remaining,'reported_ready':ready,'next_actions':steps,
      'actionable':bool(steps),'in_progress':in_progress,
      'priority':('location_conflict' if 'venue_conflict' in gaps else 'missing_details' if gaps else 'preparation' if remaining else 'settled')}

def priority_key(item):
    # Time is authoritative; unresolved imminent work precedes settled items.
    return (not item['followthrough']['actionable'],item['start'],
      {'location_conflict':0,'missing_details':1,'preparation':2,'settled':3}[item['followthrough']['priority']],item['id'])

def evidence_item(item):
    return {k:item[k] for k in ('id','name','title','date','start','all_day','venue','venue_basis','gaps','state','followthrough')}

def fallback(items):
    lines=[]
    for item in items[:3]:
        follow=item['followthrough'];prefix=item['name']+' has '+item['title']+' on '+item['date']+'. '
        if follow['next_actions']:line=prefix+'Still to check: '+', '.join(follow['next_actions'])+'.'
        elif follow['reported_ready']:line=prefix+'The recorded preparation steps have been reported ready.'
        else:line=prefix+'No unresolved preparation details are recorded.'
        lines.append(line)
    return ' '.join(lines) if lines else 'There are no unresolved preparation items in the connected calendar view I could check. Other plans may exist.'

async def compose(owner,text,items,*,provider=None):
    provider=provider or owner.provider
    memory_query=text+' '+' '.join(i['title'] for i in items)
    subjects=list(dict.fromkeys(i['person'] for i in items if i['person']))
    memories=owner.observations(memory_query,subjects)
    # Generic advice must not acquire unrelated owner-only matches.
    concepts=set(re.findall(r'\w{4,}',memory_query.casefold()))-{'what','should','needs','need','attention','prepare','plans','next','week','today','tomorrow',*subjects}
    def applies(memory):
        if memory.get('date_unresolved') or not memory.get('currently_applicable'):return False
        for item in items:
            if memory.get('subjects') and item['person'] not in memory['subjects']:continue
            day=item['date']
            if memory.get('valid_from') and memory['valid_from'][:10]>day:continue
            if memory.get('valid_until') and memory['valid_until'][:10]<=day:continue
            return True
        return False
    memories=[m for m in memories if applies(m) and concepts.intersection(re.findall(r'\w{4,}',(m['quote']+' '+m.get('interpretation','')).casefold()))][:3]
    data={'question':text,'now':owner.now().isoformat(),'appointments':[evidence_item(i) for i in items[:6]],
      'reported_memories':memories,'coverage':'Only connected calendars in the next seven days. Readiness is household-reported, never attendance. No driver or journey is inferred.'}
    schema={'type':'object','properties':{'answer':{'type':'string'},'item_ids':{'type':'array','items':{'type':'string','enum':[i['id'] for i in items] or ['none']},'maxItems':3},'memory_ids':{'type':'array','items':{'type':'string','enum':[m['id'] for m in memories] or ['none']},'maxItems':3}},'required':['answer','item_ids','memory_ids'],'additionalProperties':False}
    prompt='''You are Jarvis. Give a practical, warm English answer in2-4 connected
sentences, at most100 words. Prioritise the earliest unresolved preparations.
Explain the useful next step, not a database or sources list. next_actions and
remaining are code-checked; reported_ready items must NEVER be called unfinished.
If preparations are reported ready, avoid asking for them again. Do not say a
person is ready to attend, present or at home. No listed gaps does not mean all
real-world preparation is complete. A usual venue remains usual, not confirmed.
Only mention a reported memory if directly helpful; attribute it as a user report,
and label hints may/might. Memories cannot override the calendar, report readiness
or change appointment requirements. Do not invent dates, journeys, drivers,
deadlines, organiser instructions, notifications or actions. No commands are
executed. Use supplied IDs for the items/memories actually mentioned. JSON only.'''
    try:
        result=await local_json(provider,prompt,data,schema,tokens=340)
        if not isinstance(result,dict) or set(result)!={'answer','item_ids','memory_ids'}:raise ValueError('Invalid priority reply')
        answer=result['answer'];ids=result['item_ids'];mids=result['memory_ids']
        if not isinstance(answer,str) or not 1<=len(answer)<=1400 or secret(answer) or instruction_attempt(answer):raise ValueError('Invalid priority wording')
        if not isinstance(ids,list) or not 1<=len(ids)<=3 or not set(ids)<={i['id'] for i in items}:raise ValueError('Unknown priority appointment')
        if not isinstance(mids,list) or len(mids)>3 or not set(mids)<={m['id'] for m in memories}:raise ValueError('Unknown priority memory')
        chosen=[evidence_item(i) for i in items if i['id'] in ids];notes=[m for m in memories if m['id'] in mids]
        numbers=set(re.findall(r'\d+',str(chosen)+str(notes)))
        if set(re.findall(r'\d+',answer))-numbers:raise ValueError('Priority reply added a number')
        review=await local_json(provider,'''Check the answer ONLY against evidence.
Return supported=false for any invented requirement, readiness, person/date/venue,
journey/deadline/action; for treating a user report/hint as fact; for calling a
reported_ready item unfinished; for presenting a usual venue as confirmed; or for
claiming everyone is fully ready when only recorded steps are checked. Memory
facts may personalise but may not override calendar requirements. Otherwise true.
JSON only.''',{'answer':answer,'appointments':chosen,'memories':notes},{'type':'object','properties':{'supported':{'type':'boolean'}},'required':['supported'],'additionalProperties':False},tokens=50)
        if review!={'supported':True}:raise ValueError('Unsupported priority answer')
        return answer,True
    except (ValueError,asyncio.TimeoutError):return fallback(items),False

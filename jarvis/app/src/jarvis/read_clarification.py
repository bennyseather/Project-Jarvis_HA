"""Short-lived read slots, never identity, event facts or write authority."""
import re
from jarvis.household_planning import DATE_PATTERN,resolve_dates
from zoneinfo import ZoneInfo

def named(text,people):
 return {p for p,n in people.items() if re.search(r'(?<!\w)'+re.escape(n)+r"(?:['’]?s)?(?!\w)",text,re.I)}

def partial(text,people):
 value=text.strip(' .?!');names=named(value,people)
 bare_name=bool(len(names)==1 and re.fullmatch(re.escape(people[next(iter(names))])+r"(?:['’]?s)?",value,re.I))
 dates=list(DATE_PATTERN.finditer(value.casefold()))
 bare_date=bool(dates and not re.sub(r'\b(?:and|what about|how about|on|og|hva med|på)\b','',DATE_PATTERN.sub(' ',value.casefold())).strip(' .?!'))
 return bare_name,bare_date

def pending(owner,state):
 row=state.get('read_clarification')
 if row and row['expires']>owner.clock():return row
 state.pop('read_clarification',None);return None

def resolve(owner,text,tool,state,old):
 people={p['id']:p['preferred_name'] for p in owner.profile._data['members']};bare_name,bare_date=partial(text,people);draft=pending(owner,state)
 if old or not (bare_name or bare_date):
  if not (bare_name or bare_date):state.pop('read_clarification',None)
  return old
 subjects=sorted(named(text,people)) if bare_name else list((draft or {}).get('subjects',[]))
 anchor=owner.now().astimezone(ZoneInfo('Europe/Oslo')).date().isoformat()
 start,end=resolve_dates(text.casefold(),anchor) if bare_date else ((draft or {}).get('start'),(draft or {}).get('end'))
 purpose=(draft or {}).get('purpose') or ('preparation' if tool=='appointments' else 'overview')
 row={'subjects':subjects,'start':start,'end':end,'purpose':purpose,'tool':tool,'expires':owner.clock()+300}
 state['read_clarification']=row
 if not subjects:raise ValueError('Whose plans should I check?')
 if not start or not end:raise ValueError('Which day should I check?')
 state.pop('read_clarification',None)
 task=(draft or {}).get('task') or 'What are '+ ' and '.join(people[s] for s in subjects)+"'s plans?"
 return {**row,'question':task,'task':task,'window':'all_day','between':False,'duration_minutes':None,'event_focus':[],'preparation_goal':None,'timing_kind':None}

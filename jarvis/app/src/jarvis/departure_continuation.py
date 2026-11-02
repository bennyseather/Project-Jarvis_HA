"""Reuse a selected departure reference with a newly supplied origin, never an old route."""
from copy import deepcopy
from datetime import datetime,timedelta
import re
from zoneinfo import ZoneInfo
from jarvis.companion_store import digest,secret,instruction_attempt

def origin_quote(text):
    match=re.search(r'\b(?:from|fra)\s+(.+?)(?=\s+(?:instead|for|to|til|i stedet)\b|[,.?!]|$)',text,re.I)
    if not match:return None
    quote=match[1].strip()
    if not 1<len(quote)<=160 or secret(quote) or instruction_attempt(quote):return None
    return quote

def fingerprint(event):return digest({k:event.get(k) for k in ('text','source','start','end','owners','location','description')})

def remember(owner,state,event,buffer,destination):
    from jarvis.event_preparation import EventPreparation
    from jarvis.planning_context import revision
    state['departure_focus']={'event':deepcopy(EventPreparation.event_identity(event)),'fingerprint':fingerprint(event),'buffer':buffer,
        'destination':destination,'revision':owner.profile._data['revision'],'generation':owner.store.generation,'reports':revision(owner.profile),'expires':owner.clock()+600}

def current(owner,state):
    from jarvis.planning_context import revision
    ref=state.get('departure_focus')
    if not ref or ref['expires']<=owner.clock() or ref['revision']!=owner.profile._data['revision'] or ref['generation']!=owner.store.generation or ref['reports']!=revision(owner.profile):return None
    return ref

async def note(owner,state,minutes,origin,destination):
    from jarvis.event_preparation import EventPreparation
    from jarvis.calendar_insights import appointment_label
    ref=current(owner,state)
    if not ref or destination.casefold()!=ref['destination'].casefold():return None
    prior=owner.agent.reads.prior(state)
    if not prior or ref['event'] not in prior.get('event_focus',[]):return None
    evidence=await owner.container.companion_routing.dated_evidence(state)
    events=[f for f in (evidence or {}).get('facts',[]) if f.get('kind')=='appointment' and EventPreparation.event_identity(f)==ref['event']]
    if len(events)!=1 or fingerprint(events[0])!=ref['fingerprint']:
        state.pop('departure_focus',None)
        return 'The selected appointment could not be rechecked unchanged, so I have withheld its departure time.'
    event=events[0];at=datetime.fromisoformat(event['start']).astimezone(ZoneInfo('Europe/Oslo'));leave=at-timedelta(minutes=minutes+ref['buffer'])
    text='For '+appointment_label(event)+' at '+at.strftime('%H:%M')+', '
    text+=('the calculated departure from '+origin+' was '+leave.strftime('%H:%M')+'; that time has passed. ') if leave<=owner.now() else ('aim to leave '+origin+' around '+leave.strftime('%H:%M')+'. ')
    return text+'That includes the checked '+str(minutes)+'-minute drive and the '+str(ref['buffer'])+'-minute planning allowance; allow for traffic and other delays.'

"""Read-only text answers from the exact HA dashboard summary, not model guesses."""
import asyncio
from collections import OrderedDict
from datetime import date as Date, datetime, timedelta
import re
import time
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')
PERIOD_NAMES={'today':'Today','tomorrow':'Tomorrow','week_ahead':'Week ahead','this_week':'Rest of this week','next_week':'Next week'}
PERIOD_WORDS={'today':'today','tomorrow':'tomorrow','week ahead':'week_ahead','the week ahead':'week_ahead',
              'next 7 days':'week_ahead','the next 7 days':'week_ahead','next seven days':'week_ahead',
              'the next seven days':'week_ahead','this week':'this_week','next week':'next_week'}

def expected_dates(period, reference):
    start=Date.fromisoformat(reference)
    if period=='tomorrow':start+=timedelta(days=1)
    elif period=='next_week':start+=timedelta(days=7-start.weekday())
    count=7 if period in ('week_ahead','next_week') else (7-start.weekday() if period=='this_week' else 1)
    return [(start+timedelta(days=i)).isoformat() for i in range(count)]

def question_period(value):
    for words,period in sorted(PERIOD_WORDS.items(),key=lambda x:-len(x[0])):
        for suffix in (' for '+words,' '+words):
            if value.endswith(suffix):return value[:-len(suffix)]+' today',period,value[:-len(suffix)]
        if value in (words+' at home','show '+words+' at home'):return 'today at home',period,''
    return value,None,value

def normalize_question(text):
    """Tolerate ordinary typing/STT punctuation without fuzzy entity guessing."""
    value=' '.join(text.casefold().replace('’', "'").strip(' .?!').split())
    value=re.sub(r'^please\s+','',value)
    value=re.sub(r',?\s+please$','',value).rstrip(' .?!')
    value=re.sub(r"^what'?s\b",'what is',value)
    return value

class HouseholdTodayDialogue:
    def __init__(self, loader, *, clock=time.monotonic, day=None):
        self.loader, self.clock = loader, clock
        self.day = day or (lambda: datetime.now(ZONE).date().isoformat())
        self.sessions = OrderedDict()

    @staticmethod
    def result(message, status='success'):
        return {'status':status, 'message':message, 'provider':'household_today',
                'source':'shared_today_dashboard', 'cacheable':False}

    async def handle(self, text, conversation_id):
        return await self._handle(text, conversation_id)

    async def _handle(self, text, conversation_id):
        raw=normalize_question(text)
        value,explicit_period,base=question_period(raw)
        key=str(conversation_id) if conversation_id else None
        now,date=self.clock(),self.day()
        self.sessions=OrderedDict((k,v) for k,v in self.sessions.items() if v[0]>now and v[1]==date)
        previous=self.sessions.pop(key,None)
        period=explicit_period or (previous[3] if previous else 'today')
        more=raw in ('tell me more','more details','show more')
        topic=None
        if value in ('what is happening at home today', 'what is happening today',
                     'what is going on at home today', 'what is on at home today',
                     'what is planned at home today', 'what are our plans for today',
                     'what are our plans today', 'household summary today',
                     'today at home', 'show today at home', 'household summary for today'):
            topic='all'
        elif re.fullmatch(r"(?:what does mia have (?:planned|on)(?: today)?|what (?:are mia'?s|does mia have for) (?:plans|appointments|activities)(?: today)?|what is mia doing today)",value):
            topic='mia'
        elif re.fullmatch(r'(?:when|what time) does linda (?:finish(?: work)?|end work) today',value):
            topic='linda'
        elif re.fullmatch(r'is emrik (?:reported as )?(?:staying|reported) here(?: today)?',value):
            topic='emrik'
        elif previous:
            named=re.fullmatch(r'(?:and |what about )(mia|linda|emrik)(?: today)?',value)
            if named: topic=named[1]
            elif more:topic=previous[2]
            elif value in ('and her appointments', 'what about her plans', 'and her plans'):
                if previous[2]=='mia':topic='mia'
                else:return self.result('Whose plans do you mean? Please use their name.', 'clarification_required')
            elif explicit_period and base in ('what about','and'):
                topic=previous[2]
        if topic is None:
            # A recognizably household-day question with an unsupported time scope
            # should clarify locally, not become an unrelated general/web answer.
            if re.fullmatch(r'what is (?:happening|going on|planned|on) at home(?: (?:today|tomorrow|tonight|this week))?',value):
                return self.result('Please specify today, tomorrow, the week ahead, or next week for the shared household overview.', 'clarification_required')
            return None  # Unrelated questions clear this topic; never trap device/travel routes.
        pending=(now+300,date,topic,period)
        if key:
            self.sessions[key]=pending
            while len(self.sessions)>100:self.sessions.popitem(last=False)
        try:
            snapshot=await asyncio.wait_for(self.loader() if period=='today' else self.loader(period),20)
            reference=self.day()
            if snapshot.get('read_only') is not True:
                raise ValueError('Stale or invalid summary')
            if period=='today' and 'planning' not in snapshot:
                days=[snapshot['today']]
            else:
                plan=snapshot['planning']
                if plan['timezone']!='Europe/Oslo' or plan['generated_on']!=reference or plan['period']!=period:
                    raise ValueError('Wrong or stale planning period')
                days=plan['days']
            if [d['date'] for d in days]!=expected_dates(period,reference):raise ValueError('Wrong date range')
            if any(d['timezone']!='Europe/Oslo' or not isinstance(d['cards'],list) for d in days):raise ValueError('Invalid day')
        except Exception:
            if key and self.sessions.get(key) is pending:self.sessions.pop(key,None)
            return self.result('I cannot read the shared household summary for that period right now. Plans and presence are unknown; I have not used an old answer.', 'unavailable')
        if period!='today':return self.format_planning(snapshot,days,topic,period,more)
        summary=days[0];cards=summary['cards']
        if topic=='all':
            selected=[c for c in cards if not c['title'].startswith('Today ·')]
        elif topic=='emrik':
            selected=[c for c in cards if c['title']=='Emrik · reported stay']
        else:
            selected=[c for c in cards if c['title'].startswith(topic.title()+' ·')]
        if not selected:
            if topic=='linda':
                person=next((p for p in snapshot.get('profiles',[]) if p['name']=='Linda'),{})
                routine=person.get('details',{}).get('work_routine',{})
                if routine.get('work_days'):
                    return self.result('No usual work shift is listed for Linda today. This is her recorded routine, not confirmation of her actual plans.')
            return self.result('No approved shared information is available for that part of today. That does not confirm anyone is absent or has no plans.')
        limit=3 if topic=='all' else 20
        parts=[]
        for card in selected:
            lines=card['lines'][:limit]
            # Event names remain quoted data. They never become prompts or actions.
            if card['title']=='Mia · familiekalender':
                line='; '.join('“'+s+'”' for s in lines)
            else:line=' '.join(lines)
            parts.append(card['title'].replace(' · ', ': ')+': '+line)
            if len(card['lines'])>limit:parts.append(f"There are {len(card['lines'])-limit} more entries; ask what Mia has planned for the details.")
        return self.result('Today in Norway ('+summary['date']+'). '+' '.join(parts))

    def format_planning(self,snapshot,days,topic,period,more):
        groups=OrderedDict()
        for day in days:
            selected=[c for c in day['cards'] if not c['title'].startswith(('Today ·','Date ·')) and
                      (topic=='all' or (c['title']=='Emrik · reported stay' if topic=='emrik' else c['title'].startswith(topic.title()+' ·')))]
            if not selected:
                person=next((p for p in snapshot.get('profiles',[]) if p['name']==topic.title()),{})
                if topic=='linda' and person.get('details',{}).get('work_routine',{}).get('work_days'):
                    selected=[{'title':'Linda · usual work','lines':['No usual shift listed on this date; actual plans are not confirmed.']}]
                else:selected=[{'title':'Shared information','lines':['No approved information for this date; plans and presence are unknown.']}]
            for card in selected:
                lines=card['lines'][:20 if more or topic!='all' else 3]
                if len(lines)<len(card['lines']):lines=lines+[f"{len(card['lines'])-len(lines)} more calendar entries; ask about Mia or read the dashboard."]
                key=(card['title'],tuple(lines))
                groups.setdefault(key,[]).append(day['date'])
        pieces=[]
        for (title,lines),dates in groups.items():
            dates=', '.join(Date.fromisoformat(d).strftime('%a %d %b') for d in dates)
            text='; '.join('“'+line+'”' if title=='Mia · familiekalender' else line for line in lines)
            pieces.append(dates+' — '+title.replace(' · ',': ')+': '+text)
        limit=60 if more else 12
        notice=f' {len(pieces)-limit} further items are available: say tell me more or open the Household page.' if len(pieces)>limit else ''
        dates=days[0]['date'] if len(days)==1 else days[0]['date']+' to '+days[-1]['date']
        return self.result(PERIOD_NAMES[period]+' in Norway ('+dates+'). '+'\n'.join(pieces[:limit])+notice)

"""Read-only text answers from the exact HA dashboard summary, not model guesses."""
import asyncio
from collections import OrderedDict
from datetime import datetime
import re
import time
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')

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
        value=' '.join(text.casefold().replace('’', "'").strip(' .?!').split())
        key=str(conversation_id) if conversation_id else None
        now,date=self.clock(),self.day()
        self.sessions=OrderedDict((k,v) for k,v in self.sessions.items() if v[0]>now and v[1]==date)
        previous=self.sessions.pop(key,None)
        topic=None
        if value in ("what's happening at home today", 'what is happening at home today',
                     "what's happening today", 'what is happening today', 'today at home',
                     'show today at home', "what's on at home today", 'household summary for today'):
            topic='all'
        elif re.fullmatch(r"(?:what does mia have (?:planned|on)(?: today)?|what (?:are mia's|does mia have for) (?:plans|appointments|activities)(?: today)?|what is mia doing today)",value):
            topic='mia'
        elif re.fullmatch(r'(?:when|what time) does linda (?:finish(?: work)?|end work) today',value):
            topic='linda'
        elif re.fullmatch(r'is emrik (?:reported as )?(?:staying|reported) here(?: today)?',value):
            topic='emrik'
        elif previous:
            named=re.fullmatch(r'(?:and |what about )(mia|linda|emrik)(?: today)?',value)
            if named: topic=named[1]
            elif value in ('tell me more','more details','show more'):topic=previous[2]
            elif value in ('and her appointments', 'what about her plans', 'and her plans'):
                if previous[2]=='mia':topic='mia'
                else:return self.result('Whose plans do you mean? Please use their name.', 'clarification_required')
            elif value in ('what about tomorrow','and tomorrow'):
                return self.result('This overview covers today in Norway. Please ask separately for a named person’s calendar or routine tomorrow.', 'clarification_required')
        if topic is None:return None  # Unrelated questions clear this topic; never trap device/travel routes.
        pending=(now+300,date,topic)
        if key:
            self.sessions[key]=pending
            while len(self.sessions)>100:self.sessions.popitem(last=False)
        try:
            snapshot=await asyncio.wait_for(self.loader(),20)
            summary=snapshot['today']
            if snapshot.get('read_only') is not True or summary['timezone']!='Europe/Oslo' or summary['date']!=self.day():
                raise ValueError('Stale or invalid summary')
            cards=summary['cards']
            if not isinstance(cards,list):raise ValueError('Invalid cards')
        except Exception:
            if key and self.sessions.get(key) is pending:self.sessions.pop(key,None)
            return self.result('I cannot read the shared Today at home summary right now. Plans and presence are unknown; I have not used an old answer.', 'unavailable')
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

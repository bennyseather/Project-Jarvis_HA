"""Source-typed facts and immutable factual spans for natural local composition.

The model chooses ordering and bounded connective prose; it cannot rewrite measurements, their meaning,
forecast dates, observation times or the code-derived weather relevance clause.
"""
from dataclasses import asdict, dataclass
from datetime import date, datetime, timedelta
from decimal import Decimal
import math
import re
from zoneinfo import ZoneInfo

ZONE = ZoneInfo('Europe/Oslo')
CONDITIONS = {'rainy':'rain','pouring':'heavy rain','snowy':'snow','snowy-rainy':'rain and snow',
    'sunny':'sun','partlycloudy':'some cloud','cloudy':'cloud','fog':'fog','windy':'wind',
    'windy-variant':'wind','lightning':'thunderstorms','lightning-rainy':'thunderstorms and rain',
    'clear-night':'clear weather','exceptional':'exceptional conditions'}
WET = frozenset(('rainy','pouring','snowy','snowy-rainy','lightning-rainy'))
TOKEN = re.compile(r'\[\[([A-Z]\d+)\]\]')


def conversational_date(value, reference):
    """Resolve wording from the evidence's Norway date, never the host clock."""
    day=date.fromisoformat(value);offset=(day-date.fromisoformat(reference)).days
    if offset==0:return 'today'
    if offset==1:return 'tomorrow'
    return day.strftime('%A') if 0<=offset<=6 else day.strftime('%A %d %B')


def contact_name(name, device_class):
    """Friendly label only; a generic opening is never promoted to a window."""
    kind={'window':'window','door':'door','garage_door':'garage door','opening':'contact'}.get(device_class)
    if not kind:return name
    if (re.match(r'^door[ _-]+sensor\b',name,re.I) and device_class=='window' or
            re.match(r'^window[ _-]+sensor\b',name,re.I) and device_class in ('door','garage_door')):return name
    short=re.sub(r'^(?:magnet(?:ic)?[ _-]+sensor|contact[ _-]+sensor|window[ _-]+sensor|door[ _-]+sensor|sensor)[ _:–-]+','',name,flags=re.I).strip()
    if short==name or not short or len(short)>65:return name
    if short.casefold() in ('master bedroom','living room','kitchen','office','hallway','entryway','main bathroom','upstairs bathroom','upstairs lounge','porch'):
        short=short.lower()
    return short if short.casefold().endswith(kind) else short+' '+kind


def home_observation(data, checked_at):
    """Validate the typed aggregation, independently of any model wording."""
    meanings={'contacts':'open','lights':'on','locks':'unlocked','covers':'open'}
    if not isinstance(data,dict) or data.get('category') not in meanings:raise ValueError('Invalid observation fields')
    if data.get('meaning')!=meanings[data['category']]:raise ValueError('Invalid observation meaning')
    counts=[data.get(k) for k in ('checked','active_count','unknown_count')]
    if any(not isinstance(v,int) or isinstance(v,bool) or v<0 for v in counts) or counts[1]+counts[2]>counts[0]:
        raise ValueError('Invalid observation counts')
    names=data.get('active_examples')
    if (not isinstance(names,list) or len(names)>4 or len(names)>data['active_count'] or
            bool(names)!=bool(data['active_count']) or any(not isinstance(n,str) or not 1<=len(n)<=90 for n in names)):
        raise ValueError('Invalid observation labels')
    details=data.get('active_details')
    if details is not None:
        if (not isinstance(details,list) or len(details)!=len(names) or any(
                not isinstance(row,dict) or set(row)!= {'name','device_class'} or row['name']!=name or
                row['device_class'] not in ('window','door','garage_door','opening',None)
                for row,name in zip(details,names))):raise ValueError('Invalid observation metadata')
    stamp=datetime.fromisoformat(data['observed_at'])
    checked=datetime.fromisoformat(checked_at)
    if stamp.tzinfo is None or checked.tzinfo is None or abs((checked-stamp).total_seconds())>120:
        raise ValueError('Invalid observation scope')
    return data


@dataclass(frozen=True)
class ForecastDay:
    date: str
    condition: str
    precipitation_probability: float | None

    @classmethod
    def read(cls, item):
        stamp = datetime.fromisoformat(item['datetime'].replace('Z','+00:00'))
        if stamp.tzinfo is None: raise ValueError('Ambiguous forecast date')
        condition = item.get('condition')
        condition = condition if condition in CONDITIONS else 'unknown'
        value = item.get('precipitation_probability')
        if not isinstance(value,(int,float)) or isinstance(value,bool) or not math.isfinite(value) or not 0<=value<=100:
            value = None
        return cls(stamp.astimezone(ZONE).date().isoformat(),condition,value)

    @property
    def relevance(self):
        p = self.precipitation_probability
        if self.condition in WET and p == 0: return 'conflicting'
        if self.condition in WET or p is not None and p >= 60: return 'wet'
        if p is None: return 'unknown'
        return 'low' if p <= 20 else 'possible'

    def clause(self):
        day = datetime.fromisoformat(self.date).strftime('%A %d %B')
        condition={'cloudy':'cloudy weather','partlycloudy':'partly cloudy weather','sunny':'sunny weather'}.get(
            self.condition,CONDITIONS.get(self.condition,'unspecified conditions'))
        text = 'the home-area forecast for '+day+' calls for '+condition
        if self.precipitation_probability is not None:
            probability=format(Decimal(str(self.precipitation_probability)),'f')
            if '.' in probability:probability=probability.rstrip('0').rstrip('.')
            integer=int(self.precipitation_probability)
            article='an' if integer in (8,11,18) or 80<=integer<=89 else 'a'
            text += ', with '+article+' '+probability+'% chance of precipitation'
        return text

    def implication(self):
        return {'conflicting':"the condition and precipitation probability disagree, so I would recheck that forecast before planning around it",
            'wet':"waterproofs could be useful for any time outside near home",
            'low':"the precipitation chance is low, so extra rain preparation does not look like a priority",
            'possible':"I would check the forecast again before spending time outdoors here",
            'unknown':"that forecast does not give a precipitation probability"}[self.relevance]

    def conversational_clause(self, reference, *, personal_plans=False, single_day=True):
        outlook={'cloudy':'cloudy','partlycloudy':'partly cloudy','sunny':'sunny','rainy':'rainy',
            'pouring':'very wet','snowy':'snowy','snowy-rainy':'wet and snowy','fog':'foggy',
            'windy':'windy','windy-variant':'windy','lightning':'stormy','lightning-rainy':'stormy and rainy',
            'clear-night':'clear','exceptional':'unusual'}.get(self.condition)
        when=conversational_date(self.date,reference)
        text=when+' looks '+outlook+' around home' if outlook else 'the local conditions for '+when+' are unspecified'
        if personal_plans and single_day:
            text='if those plans involve time outside near home '+('today' if when=='today' else 'tomorrow' if when=='tomorrow' else 'on '+when)+', '+(
                'it looks '+outlook if outlook else 'the forecast does not specify the conditions')
        if self.precipitation_probability is not None:
            probability=format(Decimal(str(self.precipitation_probability)),'f')
            if '.' in probability:probability=probability.rstrip('0').rstrip('.')
            integer=int(self.precipitation_probability)
            article='an' if integer in (8,11,18) or 80<=integer<=89 else 'a'
            text+=', with '+('only ' if self.relevance=='low' else '')+article+' '+probability+'% chance of precipitation'
        return text


@dataclass(frozen=True)
class ForecastReport:
    source: str | None
    start: str
    end: str
    checked_at: str
    days: tuple[ForecastDay,...] = ()
    problem: str | None = None

    def data(self):
        return {'schema':'home_forecast_v1',**asdict(self),'days':[asdict(d) for d in self.days],
            'scope':'home_area_only','probability_property':'precipitation'}

    @classmethod
    def from_data(cls, data, start, end):
        if (not isinstance(data,dict) or data.get('schema')!='home_forecast_v1' or data.get('scope')!='home_area_only'
                or data.get('probability_property')!='precipitation' or data.get('start')!=start or data.get('end')!=end):
            raise ValueError('Invalid typed forecast')
        checked = datetime.fromisoformat(data['checked_at'])
        if checked.tzinfo is None: raise ValueError('Ambiguous forecast observation')
        if not isinstance(data['days'],list) or len(data['days'])>3: raise ValueError('Invalid forecast coverage')
        rows=[]
        for row in data['days']:
            if set(row)!= {'date','condition','precipitation_probability'}: raise ValueError('Invalid forecast fields')
            datetime.strptime(row['date'],'%Y-%m-%d')
            p=row['precipitation_probability']
            if (not start<=row['date']<end or row['condition'] not in (*CONDITIONS,'unknown') or
                    p is not None and (not isinstance(p,(int,float)) or isinstance(p,bool) or not math.isfinite(p) or not 0<=p<=100)):
                raise ValueError('Invalid forecast value')
            rows.append(ForecastDay(**row))
        if len({r.date for r in rows})!=len(rows): raise ValueError('Duplicate forecast date')
        if rows!=sorted(rows,key=lambda r:r.date): raise ValueError('Unsorted forecast dates')
        problem=data.get('problem')
        if problem not in (None,'partial_coverage','not_connected','not_covered','unavailable'):
            raise ValueError('Invalid forecast status')
        if rows and problem in ('not_connected','not_covered','unavailable'):raise ValueError('Conflicting forecast status')
        if not rows and problem is None:problem='unavailable'
        if rows and len(rows)<(datetime.fromisoformat(end)-datetime.fromisoformat(start)).days:problem='partial_coverage'
        return cls(data.get('source'),start,end,data['checked_at'],tuple(rows),problem)


class FactContract:
    """High-risk fact clauses are code rendered; Qwen arranges/explains them."""
    def __init__(self, evidence, plan):
        self.clauses={};self.required=[];self.plan=plan;self.lead=[]
        self.protected_labels=[]
        self.weather_days=[]
        for fact in evidence['facts']:
            if any(p not in evidence['people'] for p in fact['owners']):raise ValueError('Invalid fact owner')
            if fact['kind'] in ('appointment','overlap','travel_summary') and not fact['owners']:raise ValueError('Invalid fact owner')
            if fact['kind'] in ('appointment','overlap','travel_summary') and plan['subject']!='all' and set(fact['owners'])-{plan['subject']}:
                raise ValueError('Invalid fact owner scope')
        def add(key,text,kind,required=True):
            self.clauses[key]={'text':text.replace('[[','［［').replace(']]','］］'),'kind':kind}
            if required:self.required.append(key)
        homes=[f for f in evidence['facts'] if f['kind']=='home_state']
        if homes:
            import json
            rows=[home_observation(f.get('data') or json.loads(f['text']),evidence['checked_at']) for f in homes]
            for row in rows:self.protected_labels+=row.get('active_examples',[])
            row=next((r for r in rows if 'door/window contacts' in r['scope'] and r['active_count']),None)
            row=row or next((r for r in rows if r['active_count']),None) or rows[0]
            if row['active_count']:
                details=row.get('active_details') or [{'name':n,'device_class':None} for n in row['active_examples']]
                labels=[contact_name(d['name'],d['device_class']) for d in details[:2]]
                names=' and '.join('the '+label if label!=d['name'] else '“'+label+'”' for label,d in zip(labels,details))
                meaning=row.get('meaning','open')
                verb='is' if len(labels)==1 else 'are'
                text=names+' '+verb+' reporting '+meaning+' now'
                if plan['goal']=='predeparture':
                    text="I would check "+names+" before you leave; "+('it is' if len(labels)==1 else 'they are')+' reporting '+meaning+' now'
                if row['active_count']>2:text+='; other exposed readings also report '+meaning
            elif row['unknown_count']:text='some exposed home readings are unknown right now'
            else:text='none of the exposed '+row['scope'].split('exposed ',1)[-1].split(' only;',1)[0]+' reports '+row.get('meaning','open')+' right now'
            add('H1',text,'home_observation')
            if plan['goal']=='predeparture' and row['active_count']:self.lead=['H1']
        weather=next((f for f in evidence['facts'] if f['kind']=='home_weather'),None)
        if weather:
            report=ForecastReport.from_data(weather['data'],plan['start'],plan['end'])
            self.weather_days=list(report.days)
            for i,day in enumerate(report.days,1):
                personal=(plan['subject']!='all' and 'calendar' in plan['sources'] and plan['goal']!='predeparture'
                    and any(f['kind']=='appointment' for f in evidence['facts']))
                add('W'+str(i),day.conversational_clause(evidence['checked_on'],personal_plans=personal,
                    single_day=len(report.days)==1),'forecast')
                if day.relevance!='low':add('I'+str(i),day.implication(),'weather_relevance')
            if not report.days:add('W1',"I could not get the local forecast for that period",'source_gap')
        if 'weather' in plan['sources'] and not weather:
            add('W1',"I could not get the local forecast for that period",'source_gap')
        appointments=sorted((f for f in evidence['facts'] if f['kind']=='appointment'),
            key=lambda f:(f['date'],f.get('local_start','')))
        personal_plans=plan['subject']!='all' and plan['goal']!='predeparture' and 'calendar' in plan['sources']
        selected=appointments[:3] if personal_plans else appointments[:1]
        appointment_groups={}
        for fact in selected:
            appointment_groups.setdefault((tuple(fact['owners']),fact['date']),[]).append(fact)
        for index,((owners,day_value),group) in enumerate(appointment_groups.items(),1):
            if plan['subject']=='all':break
            who=' and '.join(evidence['people'][p] for p in owners)
            day=conversational_date(day_value,evidence['checked_on'])
            when=day if day in ('today','tomorrow') else 'on '+day
            if len(group)==1:
                fact=group[0]
                stamp=(' as an all-day calendar entry '+when if fact.get('all_day') else
                    ' in the calendar for '+fact['local_start']+' '+when)
                text=who+' has “'+fact['text'][:120]+'”'+stamp
            else:
                items=['“'+f['text'][:120]+'”'+(' (all-day)' if f.get('all_day') else ' at '+f['local_start']) for f in group]
                text=who+"'s calendar has "+(', '.join(items[:-1])+', and '+items[-1] if len(items)>2 else ' and '.join(items))+' '+when
            add('A'+str(index),text,'appointment',personal_plans)
        if personal_plans and selected:self.lead=['A'+str(i) for i in range(1,len(appointment_groups)+1)]
        if personal_plans and not selected:
            who=evidence['people'][plan['subject']]
            when=conversational_date(plan['start'],evidence['checked_on'])
            when=when if when in ('today','tomorrow') else 'on '+when
            if (date.fromisoformat(plan['end'])-date.fromisoformat(plan['start'])).days>1:
                last=(date.fromisoformat(plan['end'])-timedelta(days=1)).isoformat()
                when='from '+conversational_date(plan['start'],evidence['checked_on'])+' to '+conversational_date(last,evidence['checked_on'])
            coverage=any(f['kind']=='coverage' and plan['subject'] in f['owners'] for f in evidence['facts'])
            add('G1',("I did not find an appointment for "+who+" in the connected calendar "+when) if coverage else
                ("I could not check "+who+"'s calendar for that period"),'calendar_gap')
            self.lead=['G1']
        if personal_plans and len(appointments)>len(selected):
            add('C1','there '+('is ' if len(appointments)-len(selected)==1 else 'are ')+str(len(appointments)-len(selected))+
                ' more calendar '+('entry' if len(appointments)-len(selected)==1 else 'entries')+' in that period; ask for the full day if you want the rest','calendar_coverage')
        for fact in evidence['facts']:
            kind=fact['kind']
            who=' and '.join(evidence['people'].get(p,p) for p in fact['owners'])
            if kind=='overlap' and 'O1' not in self.clauses:
                overlap_day=datetime.fromisoformat(fact['date']).strftime('%A %d %B')
                title=fact['text'].removeprefix('Scheduled entries overlap: ')
                title='; '.join('“'+t.strip()[:100]+'”' for t in title.split(';')[:2])
                add('O1',who+"'s calendar shows overlapping entries on "+overlap_day+': '+title,'calendar_overlap')
            if kind in ('travel_summary','public_information'):
                key='T1' if kind=='travel_summary' else 'P1'
                text=fact.get('render_text') or fact['text']
                if kind=='travel_summary':text='for '+who+', the selected travel summary says: “'+text+'”'
                add(key,text,kind)

    def context(self):
        return {'fact_clauses':self.clauses,'required_clauses':self.required,'lead_fact_ids':self.lead,
            'rule':'Choose fact IDs in segments; code inserts each fact clause. before/after are short natural connective prose, NEVER replacement facts.'}

    def frames(self,key):
        kind=self.clauses[key]['kind']
        before=['','Also, ','Meanwhile, ']
        after=['.']
        if kind=='home_observation':
            before=[''] if self.plan['goal']=='predeparture' else ['','A useful check: ']
            if self.plan['goal']!='predeparture':after+=['; it is worth a quick check.']
            if self.plan['goal']!='predeparture' and 'T1' in self.clauses:
                before+=['Before you go, ']
                after+=['; I would recheck that before you go.']
        if kind=='forecast':
            before=['']
            if 'I'+key[1:] in self.clauses:after=['; ']
        if kind=='weather_relevance':before=['','In practical terms, ']
        if kind=='calendar_overlap':after+=['; it is worth checking which commitments apply.']
        return before,after

    def schema(self):
        choices=[]
        for key in self.clauses:
            before,after=self.frames(key)
            choices.append({'type':'object','properties':{'fact':{'type':'string','enum':[key]},
                'before':{'type':'string','enum':before},'after':{'type':'string','enum':after}},
                'required':['fact','before','after'],'additionalProperties':False})
        return {'type':'object','properties':{'segments':{'type':'array','minItems':len(self.required),
            'maxItems':len(self.clauses),'items':{'oneOf':choices}}},
            'required':['segments'],'additionalProperties':False}

    def render(self, raw, *, require_structured=False):
        import json
        obj=json.loads(raw)
        if require_structured and (not isinstance(obj,dict) or set(obj)!= {'segments'}):raise ValueError('Invalid fact template')
        structured=False
        if isinstance(obj,dict) and set(obj)=={'segments'}:
            structured=True
            segments=obj['segments']
            if not isinstance(segments,list) or not 1<=len(segments)<=len(self.clauses):raise ValueError('Invalid fact template')
            pieces=[]
            for s in segments:
                if (not isinstance(s,dict) or set(s)!= {'fact','before','after'} or not isinstance(s['fact'],str) or s['fact'] not in self.clauses
                        or any(not isinstance(s[k],str) or len(s[k])>160 for k in ('before','after'))):
                    raise ValueError('Invalid fact template')
                before,after=self.frames(s['fact'])
                if s['before'] not in before or s['after'] not in after:raise ValueError('Invalid fact frame')
                pieces.append(s['before']+'[['+s['fact']+']]'+s['after'])
            obj={'answer':' '.join(pieces)}
        if not isinstance(obj,dict) or set(obj)!={'answer'} or not isinstance(obj['answer'],str):raise ValueError('Invalid fact template')
        text=obj['answer'].strip()
        keys=TOKEN.findall(text)
        if not set(self.required)<=set(keys) or any(k not in self.clauses for k in keys) or len(keys)!=len(set(keys)):
            raise ValueError('Missing or invalid fact binding')
        if keys[:len(self.lead)]!=self.lead:raise ValueError('Question focus order')
        for i,key in enumerate(keys):
            if self.clauses[key]['kind']=='forecast' and 'I'+key[1:] in self.clauses:
                if i+1>=len(keys) or keys[i+1]!='I'+key[1:]:raise ValueError('Forecast relevance binding order')
        free='' if structured else TOKEN.sub(' ',text)
        if '[' in free or ']' in free or '{' in free or '}' in free:raise ValueError('Invalid fact binding')
        # Factual domains have a typed channel. Synonym/phrase matching is not
        # used to determine whether an unbound numeric claim is "close enough".
        if re.search(r'\d|%|\b(?:percent|percentage|zero|one|two|three|four|five|six|seven|eight|nine|ten|hundred)\b',free,re.I):
            raise ValueError('Unbound quantity')
        if re.search(r'\b(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday|today|tomorrow|yesterday|forecast|weather|rain\w*|snow\w*|cloud\w*|precipitation|sunny|wind\w*|fog\w*|probability|chance|dry|wet)\b',free,re.I):
            raise ValueError('Unbound forecast or date claim')
        if re.search(r'\b(?:home|house|sensor\w*|contact\w*|window\w*|door\w*|lock\w*|blind\w*|cover\w*|reading\w*|snapshot|open|closed|unlocked)\b',free,re.I):
            raise ValueError('Unbound home observation')
        if any(label and label.casefold() in free.casefold() for label in self.protected_labels):
            raise ValueError('Unbound home observation')
        if re.search(r'\b(?:school|classes|routine|timetable|unchanged|attend\w*|cancel\w*|safe|secure|stay|remain|indoor\w*|outdoor\w*|umbrella\w*|coat\w*|protection|guarantee\w*|always|certain|nothing|ignore|disregard|must|required)\b',free,re.I):
            raise ValueError('Unbound planning conclusion')
        # Unsupported negation/comparison cannot reverse an immutable clause.
        if re.search(r'\b(?:not|never|no|without|unlike|less|more|except|instead|incorrect|wrong|false)\b|n[\x27’]t\b',free,re.I):
            raise ValueError('Fact binding reversed')
        result=TOKEN.sub(lambda m:self.clauses[m[1]]['text'],text)
        result=re.sub(r'\s+',' ',result)
        result=re.sub(r'^(?:Alongside that, |Also, |Meanwhile, )','',result)
        result=result.replace('; In practical terms, ','; ')
        if len(result)>3200:raise ValueError('Bound answer too long')
        result=re.sub(r'(^|[.!?]\s+)([a-z])',lambda m:m[1]+m[2].upper(),result)
        return result

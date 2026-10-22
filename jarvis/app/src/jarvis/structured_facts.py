"""Source-typed facts and immutable factual spans for natural local composition.

The model chooses ordering and bounded connective prose; it cannot rewrite measurements, their meaning,
forecast dates, observation times or the code-derived weather relevance clause.
"""
from dataclasses import asdict, dataclass
from datetime import datetime
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
            'wet':"wet-weather protection could help if heading outside",
            'low':"the precipitation chance is low, so extra rain preparation does not look like a priority",
            'possible':"precipitation is possible, so it is worth checking again closer to any outdoor plans",
            'unknown':"the precipitation probability is not supplied, so I cannot judge its likelihood from this forecast"}[self.relevance]


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
        self.clauses={};self.required=[];self.plan=plan
        self.protected_labels=[]
        self.weather_days=[]
        for fact in evidence['facts']:
            if any(p not in evidence['people'] for p in fact['owners']):raise ValueError('Invalid fact owner')
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
                names=' and '.join('“'+n+'”' for n in row['active_examples'][:2])
                meaning=row.get('meaning','open')
                text='HA currently reports '+names+' as '+meaning
                if row['active_count']>2:text+='; other exposed readings also report '+meaning
            elif row['unknown_count']:text='some exposed home readings are unknown right now'
            else:text='none of the exposed '+row['scope'].split('exposed ',1)[-1].split(' only;',1)[0]+' reports '+row.get('meaning','open')+' right now'
            add('H1',text,'home_observation')
        weather=next((f for f in evidence['facts'] if f['kind']=='home_weather'),None)
        if weather:
            report=ForecastReport.from_data(weather['data'],plan['start'],plan['end'])
            self.weather_days=list(report.days)
            for i,day in enumerate(report.days,1):
                add('W'+str(i),day.clause(),'forecast')
                add('I'+str(i),day.implication(),'weather_relevance')
            if not report.days:add('W1',"I could not get the local forecast for that period",'source_gap')
        if 'weather' in plan['sources'] and not weather:
            add('W1',"I could not get the local forecast for that period",'source_gap')
        for fact in evidence['facts']:
            kind=fact['kind']
            who=' and '.join(evidence['people'].get(p,p) for p in fact['owners'])
            if kind=='overlap' and 'O1' not in self.clauses:
                date=datetime.fromisoformat(fact['date']).strftime('%A %d %B')
                title=fact['text'].removeprefix('Scheduled entries overlap: ')
                title='; '.join('“'+t.strip()[:100]+'”' for t in title.split(';')[:2])
                add('O1',who+"'s calendar shows overlapping entries on "+date+': '+title,'calendar_overlap')
            if kind=='appointment' and plan['subject']!='all' and 'A1' not in self.clauses:
                date=datetime.fromisoformat(fact['date']).strftime('%A %d %B')
                stamp=' as an all-day entry' if fact.get('all_day') else ' at '+fact['local_start']
                add('A1',who+' has “'+fact['text'][:120]+'” scheduled'+stamp+' on '+date,'appointment',plan['goal']!='predeparture')
            if kind in ('travel_summary','public_information'):
                key='T1' if kind=='travel_summary' else 'P1'
                text=fact.get('render_text') or fact['text']
                if kind=='travel_summary':text='for '+who+', the selected travel summary says: “'+text+'”'
                add(key,text,kind)

    def context(self):
        return {'fact_clauses':self.clauses,'required_clauses':self.required,
            'rule':'Choose fact IDs in segments; code inserts each fact clause. before/after are short natural connective prose, NEVER replacement facts.'}

    def frames(self,key):
        kind=self.clauses[key]['kind']
        before=['','Also, ','Meanwhile, ']
        after=['.']
        if kind=='home_observation':
            before=['','A useful check: ']
            after+=['; it is worth a quick check.']
            if self.plan['goal']=='predeparture' or 'T1' in self.clauses:
                before+=['Before you go, ']
                after+=['; I would recheck that before you go.']
        if kind=='forecast':
            before=['','Alongside that, ']
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

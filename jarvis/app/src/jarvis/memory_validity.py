"""Deterministic validity intervals, separate from retaining the original quote."""
import re
from datetime import datetime,timedelta
from zoneinfo import ZoneInfo
ZONE=ZoneInfo('Europe/Oslo')
DAY=r'(?:\d{4}-\d{2}-\d{2}|(?:next |this )?(?:monday|tuesday|wednesday|thursday|friday|saturday|sunday)|today|tomorrow|(?:neste |denne )?(?:mandag|tirsdag|onsdag|torsdag|fredag|lørdag|søndag)|i morgen|i dag)'
NUMBER=r'(?:\d{1,3}|one|two|three|four|five|six|seven|eight|nine|ten|en|ei|ett|to|tre|fire|fem|seks|sju|syv|åtte|ni|ti)'
INTERVAL=re.compile(r'\b(?:(?:from|fra) '+DAY+r' (?:through|to|til og med) '+DAY+r'|(?:through|until(?: the)? end of|til og med) '+DAY+r'|(?:until|frem til|fram til|til) '+DAY+r'|(?:for(?: the next)?|i) '+NUMBER+r' (?:days?|weeks?|dager|uker))\b',re.I)

def temporal_phrase(text):
    match=INTERVAL.search(text)
    return match.group() if match else None

def interval_scope(phrase,anchor,resolve):
    """Return None for a point date; unresolved bare 'until Friday' stays qualified."""
    value=' '.join(phrase.casefold().strip(' .').split())
    value=re.sub(r'^til og med ','through ',value)
    value=re.sub(r'^(?:frem til|fram til|til) ','until ',value)
    value=re.sub(r'^fra ','from ',value).replace(' til og med ',' through ')
    duration=re.fullmatch(r'(?:for(?: the next)?|i) ('+NUMBER+r') (days?|weeks?|dager|uker)',value)
    start=datetime.fromisoformat(anchor).date()
    if duration:
        numbers=dict(zip(('one','two','three','four','five','six','seven','eight','nine','ten'),range(1,11)))
        numbers.update(dict(zip(('en','to','tre','fire','fem','seks','sju','åtte','ni','ti'),range(1,11))));numbers.update(ei=1,ett=1,syv=7)
        count=int(duration[1]) if duration[1].isdigit() else numbers[duration[1]]
        days=count*(7 if duration[2].startswith(('week','uke')) else 1)
        if not 1<=days<=366:return None,None,True
        return datetime.combine(start,datetime.min.time(),ZONE).isoformat(),datetime.combine(start+timedelta(days=days),datetime.min.time(),ZONE).isoformat(),False
    span=re.fullmatch(r'from (.+?) (?:through|to) (.+)',value)
    through=re.fullmatch(r'(?:through|until(?: the)? end of) (.+)',value)
    until=re.fullmatch(r'until (.+)',value)
    if not (span or through or until):return None
    if until and not through:return None,None,True # No invented start/end-of-day interpretation.
    a,_,bad=resolve(span[1],anchor) if span else (datetime.combine(start,datetime.min.time(),ZONE).isoformat(),None,False)
    _,b,bad_end=resolve(span[2] if span else through[1],anchor)
    if bad or bad_end or a is None or b is None:return None,None,True
    if not 0<(datetime.fromisoformat(b)-datetime.fromisoformat(a)).total_seconds()<=367*86400:return None,None,True
    return a,b,False

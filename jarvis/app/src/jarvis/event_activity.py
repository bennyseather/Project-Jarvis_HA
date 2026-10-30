"""Positive activity evidence for event reasoning, not a household fact store.

Small English/Norwegian lexical groups bridge known activity words. They are not
personal preferences or proof of attendance. Unknown labels require literal
support; the local model can still reject a supported candidate as irrelevant.
An opaque title is not classified from a venue, emoji, person or equipment note.
"""
import re
import unicodedata

from jarvis.household_planning import DATE_PATTERN


SPECIFIC={
    'rhythmic_gymnastics':r'rhythmic gymnastics|rytmisk gymnastikk',
    'swimming':r'swim(?:ming)?|svømm(?:ing|e(?:trening|kurs|time|skole|økt|hallen)?)?',
    'gymnastics':r'gymnastics?|gymnastikk|turntrening|turnøkt|turntime',
    'music':r'music(?:al)?|musikk',
    'band':r'band|korps',
    'piano':r'piano|pianotime',
    'choir':r'choir|korøving',
    'dance':r'danc(?:e|ing)|dans|dansetime|danseøving',
    'football':r'football|soccer|fotball(?:trening|kamp)?',
    'handball':r'handball|håndball(?:trening|kamp)?',
    'basketball':r'basketball(?:trening|kamp)?',
    'volleyball':r'volleyball(?:trening|kamp)?',
    'tennis':r'tennis(?:trening|time)?',
    'running':r'running|jogging|løping|løpetrening',
    'cycling':r'cycling|biking|sykling|sykkeltrening',
    'skiing':r'skiing|skitrening|langrenn',
    'chess':r'chess|sjakk(?:trening|klubb)?',
}
BROAD={
    'training':r'training|workout|fitness|trening|treningsøkt',
    'rehearsal':r'rehearsal|practice|(?:felles|gruppe)?øving|øvelse',
    'competition':r'competition|contest|(?:krets)?konkurranse',
}
PATTERNS={k:re.compile(r'(?<!\w)(?:'+v+r')(?!\w)',re.I) for k,v in {**SPECIFIC,**BROAD}.items()}
CHILDREN={'music':('band','piano','choir'),'gymnastics':('rhythmic_gymnastics',)}
STOP=set(('what when where which how should could would can do does did is are am will i we us me my our your you '
    'her his their she he they s it that this those these for to of on in at and the a an please jarvis help '
    'need needs needed prepare preparation bring pack equipment kit get ready anything something else '
    'left remaining still already packed checked checking before done '
    'event events appointment appointments activity activities session sessions class classes lesson lessons '
    'commitment commitments day household family one ones meant mean about '
    'morning afternoon evening tonight later early upcoming scheduled coming up '
    'have has got doing leave leaving depart departing departure set off time arrive arrival '
    'home drive driving journey travel minutes minute mins min hours hour allowance').split())
UNCERTAIN=re.compile(r'\b(?:no|not|non|never|without|excluding|if|unless|maybe|possibly|might|could|may|'
    r'cancel\w*|example|or|whether|tbc|tbd|unconfirmed|uncertain|unknown|possible|perhaps|'
    r'ikke|ingen|hvis|dersom|kanskje|muligens|eventuelt|avlyst|eller|uavklart|ubekreftet)\b|'
    r"don['’]t|instead of|used to|rather than|[/\\?]",re.I)


def normalise(text):return unicodedata.normalize('NFKC',text).casefold()


def requirement(question,people):
    """Only actual question words establish a requested kind, not model claims."""
    value=DATE_PATTERN.sub(' ',normalise(question))
    for name in people:value=re.sub(r'(?<!\w)'+re.escape(normalise(name))+r'(?!\w)',' ',value)
    groups=[]
    # Strip matched aliases before retrieving unknown literal labels. Specific
    # groups do not make a generic source a positive example of the subtype.
    for key,pattern in PATTERNS.items():
        if pattern.search(value):groups.append(key);value=pattern.sub(' ',value)
    literals=sorted(set(re.findall(r'[^\W\d_]+',value,re.UNICODE))-STOP)
    return {'groups':groups,'literals':literals}


def requested(scope):return bool(scope['groups'] or scope['literals'])


def assertions(event):
    # Deliberately exclude locations and approved personal notes. Conditional,
    # cancelled, negative and truncated clauses cannot establish activity kind.
    values=[event['text'],*event.get('description_units',[])]
    return [v for v in values if not v.endswith(('…','...')) and not UNCERTAIN.search(v)]


def support(scope,event):
    values=assertions(event)
    text=normalise(' '.join(values))
    words=set(re.findall(r'[^\W\d_]+',text,re.UNICODE))
    def matches(key,value):
        return PATTERNS[key].search(value) or any(PATTERNS[child].search(value) for child in CHILDREN.get(key,()))
    # Do not silently drop a source clause contradicting the requested kind.
    # Conservative uncertainty handling may ask again; it must not assert a kind
    # solely by quoting a positive title alongside a cancelled/conditional notice.
    for clause in [event['text'],*event.get('description_units',[])]:
        if UNCERTAIN.search(clause) and (any(matches(key,normalise(clause)) for key in scope['groups']) or
                any(re.search(r'(?<!\w)'+re.escape(word)+r'(?!\w)',normalise(clause)) for word in scope['literals'])):
            return False
    return (all(matches(key,text) for key in scope['groups']) and
            all(word in words for word in scope['literals']))


def generic_candidate(event):
    text=normalise(' '.join(assertions(event)))
    return (any(p.search(text) for k,p in PATTERNS.items() if k in BROAD) and
            not any(p.search(text) for k,p in PATTERNS.items() if k in SPECIFIC))

"""Conservative lexical evidence for an item reported at its checked venue."""
import re

def terms(text):
    words=set(re.findall(r'\w+',text.casefold()))
    aliases={'instrumentet':{'instrument'},'noter':{'sheet','music'},'notene':{'sheet','music'},'vannflasken':{'water','bottle'},'vannflaske':{'water','bottle'}}
    return words|set().union(*(aliases.get(w,set()) for w in words))

def at_venue_items(text,item):
    if item.get('venue_basis') not in ('calendar','reported for this appointment'):return []
    if re.search(r'\b(?:not|never|isnt|isn.t|isn’t|ikke|ikkje|if|maybe|might|should|needs?|trenger)\b',text,re.I) or '?' in text:return []
    if not re.search(r'\b(?:already at|already in|allerede på|allereie på)\b',text,re.I):return []
    venue=item.get('venue','').casefold();match=re.search(r'\b(?:already at|already in|allerede på|allereie på)\s+(?:the\s+)?(.+?)[.!]*$',text,re.I)
    if not match:return []
    reported=match[1].strip(' .!').casefold()
    school={'school','school building','skolen','skulen','skole','skule'}
    if reported!=venue and not (reported in school and re.search(r'\b(?:school|skule|skole)\b',venue)):return []
    mentioned=terms(text)
    return [s['id'] for s in item.get('checklist',[]) if s['kind']=='equipment' and (terms(s['text'])-{'the','a','and'}) and (terms(s['text'])-{'the','a','and'})<=mentioned]

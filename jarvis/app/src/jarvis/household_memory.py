"""Deterministic household memory language; no inferred facts or new store."""
import re
from jarvis.household_speaker import speaker_context


def clean(text):
    return ' '.join(str(text).replace('’', "'").strip().rstrip('.!?').split())


def bind_statement(text, document):
    """Bind first-person statements to this request's speaker, never history."""
    value=clean(text)
    if re.search(r"\b(?:i|my|mine|myself)\b|\bi'm\b",value,re.I):
        name=speaker_context(document)['preferred_name']
        if not name:
            return None, 'Whose information should I remember? Please use their name, or ask again when your voice is matched.'
        value=re.sub(r"\bi'm\b",name+' is',value,flags=re.I)
        for pattern,replacement in (
            (r'\bi am\b',name+' is'),(r"\bi (?:don't|do not)\b",name+' does not'),
            (r'\bi (prefer|like|enjoy|work|need|want|live)\b',None),
            (r'\bi have\b',name+' has'),(r'\bmy\b',name+"'s"),
            (r'\bmyself\b',name),(r'\bmine\b',name+"'s")):
            value=re.sub(pattern,(lambda m:name+' '+m[1].lower()+'s') if replacement is None else replacement,
                         value,flags=re.I)
        # Keep uncommon verbs verbatim with explicit attribution rather than
        # inventing a grammatical transformation or the identity of a pronoun.
        if re.search(r'\bi\b',value,re.I):value=name+' reports: "'+value+'"'
    return value,None


def find_note(document, phrase):
    phrase=clean(phrase).strip('"“”\'')
    notes=document.get('conversation_notes',[])
    by_id=[n for n in notes if n.get('id','').casefold()==phrase.casefold()]
    if by_id:return by_id[0]
    matches=[n for n in notes if clean(n['text']).casefold()==phrase.casefold()]
    return matches[0] if len(matches)==1 else None


def memory_question(text, profile):
    """Answer memory review questions from confirmed data, without an LLM."""
    from jarvis.household_speaker import shared_knowledge_enabled
    document=getattr(profile,'_data',{})
    if not shared_knowledge_enabled(document):return None
    value=clean(text).casefold()
    match=re.fullmatch(r"(?:what do you (?:know|remember)|what have you (?:remembered|saved)) about (.+)",value)
    list_all=value in ('show household notes','list household notes','what have you remembered',
                       'what have you saved','what do you remember about the household')
    if not match and not list_all:return None
    target=match[1] if match else 'the household'
    people=document.get('members',[])+document.get('extended_family',[])
    hint=speaker_context(document)
    if target in ('me','myself'):
        if not hint['member_id']:
            return result('Whose information do you mean? Please name a household member.', 'clarification_required')
        target=hint['preferred_name'].casefold()
    household=target in ('us','our household','the household','our family','the family','household')
    person=next((p for p in people if p['preferred_name'].casefold()==target),None)
    if not household and not person:
        return result('Which household member do you mean? Please use their recorded name.', 'clarification_required')
    context=profile.context()
    notes=context.get('shared_household_notes',[])
    if person:
        name=person['preferred_name']
        notes=[n for n in notes if re.search(r'\b'+re.escape(name)+r'\b',n['text'],re.I)]
        subject='you' if hint['member_id']==person['id'] else name
        sentences=[]
        work=person.get('employment',{})
        if work.get('status')=='confirmed':
            roles=work.get('roles') or ([work['role']] if work.get('role') else [])
            employer=work.get('employer') or work.get('workplace')
            if roles and employer:sentences.append(('You work' if subject=='you' else name+' works')+' as '+' and '.join(roles)+' at '+employer+'.')
        details=context.get('approved_personal_details',{}).get(name,{})
        if 'age_years' in details:
            sentences.append(('You are' if subject=='you' else name+' is')+' '+str(details['age_years'])+' years old.')
        school=details.get('school',{}).get('name') or details.get('school_routine',{}).get('school')
        if isinstance(school,str):sentences.append(('Your recorded school is ' if subject=='you' else name+"'s recorded school is ")+school+'.')
        room=next((r for r in context.get('directory',{}).get('rooms',[]) if r['id']==person.get('room')),None)
        if room:sentences.append(('Your assigned bedroom is ' if subject=='you' else name+"'s assigned bedroom is ")+room['name']+'. This is a room assignment, not live presence.')
        for relationship in context.get('directory',{}).get('relationships',[]):
            if re.search(r'\b'+re.escape(name)+r'\b',relationship,re.I):sentences.append(relationship.rstrip('.')+'.')
        for fact in person.get('facts',[]):
            if fact.get('status')=='confirmed':sentences.append('Recorded fact: '+fact['value'].rstrip('.')+'.')
        if not sentences:sentences=['Here is what I have saved about '+subject+'.']
        lead=' '.join(sentences[:6])
        if len(sentences)>6:lead+=' More profile details and routines are available on the household information page.'
    else:lead='Here are the shared household notes I have saved.'
    if notes:
        lines=['“'+n['text']+'” (note '+n['id']+')' for n in notes[:8]]
        lead+=' '+ '; '.join(lines)+'.'
        if len(notes)>8:lead+=' More notes are available on the household information page.'
        lead+=' To correct or remove a note, quote its exact text; I will ask you to confirm.'
    else:lead+=' I do not have any '+('additional notes about '+subject if person else 'shared household notes')+' saved.'
    return result(lead)


def result(message,status='success'):
    return {'status':status,'message':message,'provider':'household_memory','cacheable':False}


def relevant_notes(notes, text, document, maximum=8):
    """Bound local-model memory context without another model/vector request.

    Keep whole notes; the complete approved list remains on the household page.
    Selection changes relevance, never sharing/authorization or stored facts.
    """
    names=[p['preferred_name'] for p in document.get('members',[])+document.get('extended_family',[])]
    explicit=[n for n in names if re.search(r'\b'+re.escape(n)+r'\b',text,re.I)]
    if not explicit and re.search(r'\b(i|me|my|mine)\b',text,re.I):
        name=speaker_context(document)['preferred_name']
        if name:explicit=[name]
    stop={'what','when','where','which','tell','about','does','have','with','that','this','the','and','for','you','your','remember','know'}
    words={w for w in re.findall(r'[\w]+',text.casefold()) if len(w)>2 and w not in stop}
    ranked=[]
    for index,note in enumerate(notes):
        mentioned=[n for n in names if re.search(r'\b'+re.escape(n)+r'\b',note['text'],re.I)]
        if explicit and mentioned and not set(explicit).intersection(mentioned):continue
        tokens=set(re.findall(r'[\w]+',note['text'].casefold()))
        score=len(words & tokens)+(10 if set(explicit).intersection(mentioned) else 0)
        if score or not mentioned:ranked.append((score,index,note))
    ranked.sort(key=lambda x:(x[0],x[1]),reverse=True)
    return [dict(n) for _,_,n in ranked[:maximum]]


def style_note(text, document):
    """One explicit presentation-only preference, never free-form instructions."""
    for person in document.get('members',[]):
        match=re.fullmatch(re.escape(person['preferred_name'])+
            r' prefers? (concise|short|brief|detailed|longer) (?:answers|replies|briefings)',clean(text),re.I)
        if match:return person['id'],('concise' if match[1].casefold() in ('concise','short','brief') else 'detailed')
    return None


def response_style(document, member_id):
    choices={record[1] for note in document.get('conversation_notes',[])
             if (record:=style_note(note['text'],document)) and record[0]==member_id}
    return next(iter(choices)) if len(choices)==1 else 'balanced'

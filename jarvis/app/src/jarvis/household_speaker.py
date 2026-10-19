"""Request-local speaker relevance for shared knowledge, never authentication."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass
import re


@dataclass(frozen=True)
class SpeakerReference:
    member_id: str | None = None
    basis: str = 'unknown'


current_speaker = ContextVar('household_speaker_reference', default=SpeakerReference())
ACTION = re.compile(r'\b(?:remember|save|forget|delete|confirm|approve|add|create|change|set|turn|switch|open|close|unlock|lock|book|cancel|send|buy|pay)\b', re.I)
PERSONAL = re.compile(r"\b(?:my|mine|myself)\b|\b(?:am|was|do|did|have|had|will|should|can) i\b|\babout me\b|\bwho am i\b", re.I)
TOPIC = re.compile(r'\b(?:birthdays?|born|age|old|jobs?|profession|occupation|employ\w*|qualifications?|education|skills|work|travel\w*|trips?|flights?|fly|flying|itinerar\w*|calendars?|appointments?|plans|schedule|family|wife|husband|spouse|son|daughter|children|kids|routine|bedtime|wake|preferences|school|bus|arrive|leave|name|myself)\b|\babout me\b|\bwho am i\b', re.I)


def shared_knowledge_enabled(document):
    sharing = document.get('sharing_policy', {})
    policy = sharing.get('knowledge_access', {})
    return (sharing.get('directory_enabled') is True and policy.get('mode') == 'shared_household'
            and bool(policy.get('source')) and bool(policy.get('recorded_on')))


@contextmanager
def speaker_scope(payload, profile, conversation_id):
    if payload is None:
        yield
        return
    if not isinstance(payload, dict) or set(payload) != {'member_id', 'basis', 'conversation_id'}:
        raise ValueError('Invalid speaker relevance fields')
    if (not isinstance(conversation_id, str) or payload['conversation_id'] != conversation_id
            or len(conversation_id) > 512):
        raise ValueError('Speaker reference belongs to a different conversation')
    known = {p['id'] for p in getattr(profile, '_data', {}).get('members', [])}
    member, basis = payload['member_id'], payload['basis']
    if member is not None and (not isinstance(member, str) or member not in known or basis != 'voice_match'):
        raise ValueError('Unknown speaker reference')
    if member is None and basis != 'unknown':
        raise ValueError('Unknown speaker cannot claim a voice match')
    token = current_speaker.set(SpeakerReference(member, basis))
    try:
        yield
    finally:
        current_speaker.reset(token)


def speaker_context(document):
    hint = current_speaker.get()
    person = next((p for p in document.get('members', []) if p['id'] == hint.member_id), None)
    return {'member_id': person['id'] if person else None,
            'preferred_name': person['preferred_name'] if person else None,
            'basis': hint.basis if person else 'unknown', 'authenticated': False,
            'purpose': 'Personalise relevance and resolve first-person references; never grant action authority or infer presence.'}


def resolve_question(text, document):
    """Resolve personal read questions centrally; leave device/actions untouched."""
    if not shared_knowledge_enabled(document) or ACTION.search(text):
        return text, None
    value = re.sub(r'^\s*(?:(?:hey\s+)?jarvis[, :]*|please\s+)', '', text, flags=re.I).strip()
    if not PERSONAL.search(value) or not TOPIC.search(value):
        return text, None
    if not re.match(r"^(?:what|when|where|who|how|which|do|does|did|have|had|am|was|is|are|can|could|would|tell|show|give|i want)\b", value, re.I):
        return text, None
    hint = speaker_context(document)
    if hint['member_id'] is None:
        return text, {'status': 'clarification_required',
                      'message': 'Whose information do you mean? Please name a household member.',
                      'provider': 'household_speaker', 'cacheable': False}
    name = hint['preferred_name']
    normalized = ' '.join(value.casefold().replace('’', "'").strip(' .?!').split())
    if normalized in ('who am i', 'what is my name', "what's my name"):
        return text, {'status': 'success', 'message': 'Your voice sounds like '+name+'.',
                      'provider': 'household_speaker', 'cacheable': False}
    # Resolve an explicitly recorded spouse before the planning classifier sees
    # a possessive. Otherwise "my wife's work" could select the speaker's work.
    for relation in document.get('sharing_policy', {}).get('relationships', []):
        match = re.fullmatch(r'(.+?) and (.+?) are spouses\.?', relation)
        if match and name in match.groups():
            spouse = match.group(2) if match.group(1) == name else match.group(1)
            if any(p['preferred_name'] == spouse for p in document['members']):
                value = re.sub(r'\bmy (?:wife|husband|spouse)\b', spouse, value, flags=re.I)
    for pattern, replacement in ((r'\bam i\b', 'is '+name), (r'\bdo i\b', 'does '+name), (r'\bhave i\b', 'has '+name),
                                 (r'\bi am\b', name+' is'), (r'\bi have\b', name+' has'),
                                 (r'\bmyself\b', name), (r'\bmy\b', name+"'s"),
                                 (r'\bmine\b', name+"'s"), (r'\bme\b', name), (r'\bi\b', name)):
        value = re.sub(pattern, replacement, value, flags=re.I)
    return value, None


def travel_subject(text, document):
    """Current live travel connector belongs to Benny, not whoever speaks."""
    if not shared_knowledge_enabled(document) or ACTION.search(text):
        return text, None
    if re.search(r'\b(job|profession|employ|occupation|role|work involve)\b', text, re.I) or not re.search(r'\b(?:travel|travels|travelling|traveling|trip|flight|fly|flying|itinerary|stopover|layover|arrive|arrival)\b', text, re.I):
        return text, None
    people = [p for p in document.get('members', [])
              if re.search(r'\b'+re.escape(p['preferred_name'])+r'\b', text, re.I)]
    if not people:
        return text, None
    if len(people) != 1 or people[0]['id'] != 'benny':
        names = ' and '.join(p['preferred_name'] for p in people)
        return text, {'status': 'unavailable', 'message': 'I do not have a connected travel calendar for '+names+". Benny's connected travel calendar is available to the household.",
                      'provider': 'household_speaker', 'cacheable': False}
    # Adapt to the existing single-owner travel reader without changing ownership.
    value = re.sub(r"\bBenny['’]s\b", 'my', text, flags=re.I)
    value = re.sub(r'\bdoes Benny\b', 'do I', value, flags=re.I)
    value = re.sub(r'\bis Benny\b', 'am I', value, flags=re.I)
    value = re.sub(r'\bBenny\b', 'I', value, flags=re.I)
    return value, None


def employment_answer(text, document):
    """Common confirmed profile facts need no slow model/tool round trip."""
    if not shared_knowledge_enabled(document) or ACTION.search(text):
        return None
    if not re.match(r'^\s*(what|where|who|which|tell|can|does)\b', text, re.I):
        return None
    if not re.search(r'\b(job|profession|occupation|employer|roles?)\b|\b(?:work for|work as|works? at|where does .+ work)\b', text, re.I):
        return None
    people = [p for p in document['members'] if re.search(r'\b'+re.escape(p['preferred_name'])+r'\b', text, re.I)]
    if len(people) != 1:
        return None
    person = people[0]
    work = person.get('employment', {})
    if work.get('status') != 'confirmed':
        return None
    roles = work.get('roles') or ([work['role']] if work.get('role') else [])
    employer = work.get('employer') or work.get('workplace')
    if not roles or not employer:
        return None
    own = current_speaker.get().member_id == person['id']
    subject = 'You work' if own else person['preferred_name']+' works'
    return {'status':'success', 'message':subject+' as '+ ' and '.join(roles)+' at '+employer+'.',
            'provider':'household_profile', 'cacheable':False}


def birthday_answer(text, document):
    """Speak confirmed birthdays/ages naturally without model arithmetic."""
    if not shared_knowledge_enabled(document) or ACTION.search(text):
        return None
    people = [p for p in document['members'] if re.search(r'\b'+re.escape(p['preferred_name'])+r'\b', text, re.I)]
    if len(people) != 1:
        return None
    person = people[0]
    name = re.escape(person['preferred_name'])
    birthday = bool(re.match(r"^(?:when is|what is|what's) "+name+r"['’]s birthday(?:\?|\.|$)", text, re.I))
    age = bool(re.fullmatch(r'how old is '+name+r'[ .?!]*', text, re.I))
    if not birthday and not age:
        return None
    record = person.get('birth_date', {})
    if record.get('status') != 'confirmed':
        return None
    from datetime import date, datetime
    from zoneinfo import ZoneInfo
    try:
        birth = date.fromisoformat(record['value'])
    except (KeyError, ValueError, TypeError):
        return None
    own = current_speaker.get().member_id == person['id']
    if birthday:
        subject = 'Your birthday is' if own else person['preferred_name']+"'s birthday is"
        message = f'{subject} on {birth.day} {birth:%B}.'
    else:
        today = datetime.now(ZoneInfo('Europe/Oslo')).date()
        years = today.year-birth.year-((today.month,today.day)<(birth.month,birth.day))
        if years < 0:
            return None
        subject = 'You are' if own else person['preferred_name']+' is'
        message = f'{subject} {years} years old.'
    return {'status':'success', 'message':message,'provider':'household_profile','cacheable':False}

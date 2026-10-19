"""Optional shared-read wording only; never identity, presence or action access."""
import hashlib
import re
import secrets
import time

ACTION = re.compile(r'\b(?:remember|save|forget|delete|confirm|approve|add|create|change|set|turn|switch|open|close|unlock|lock|book|cancel)\b', re.I)
READ = re.compile(r'\b(?:routine|schedule|plans|school|work|birthday|age|old|family|job|profession)\b', re.I)
PERSON = {'benny': 'Benny', 'linda': 'Linda', 'emrik': 'Emrik', 'mia': 'Mia'}


def personalise_shared_question(text, member):
    """Select an already-shared profile only for a bounded first-person read."""
    if member not in PERSON or len(text) > 1000 or ACTION.search(text) or not READ.search(text):
        return text
    if not re.match(r'^\s*(?:what|when|how|which|do|does|am|is|can you tell)\b', text, re.I):
        return text
    name = PERSON[member]
    result = re.sub(r'\bmy\b', name+"'s", text, flags=re.I)
    result = re.sub(r'\bhow old am i\b', 'How old is '+name, result, flags=re.I)
    return result


class SharedSpeakerTurns:
    def __init__(self, *, clock=time.monotonic):
        self.clock = clock
        self._sessions = {}

    def route(self, grant_id, conversation_id, member):
        now = self.clock()
        self._sessions = {key: value for key, value in self._sessions.items() if now-value[1] < 300}
        if not conversation_id.startswith('jarvis-voice-v3:development_computer:'):
            raise ValueError('Development microphone only')
        group = conversation_id.rsplit(':', 1)[0]
        key = grant_id, group
        if member not in PERSON:
            member = None
        old = self._sessions.get(key)
        if not old or old[0] != member or member is None:
            nonce = secrets.token_hex(16)
        else:
            nonce = old[2]
        if len(self._sessions) >= 64 and key not in self._sessions:
            self._sessions.clear()
        self._sessions[key] = member, now, nonce
        digest = hashlib.sha256((grant_id+'|'+group+'|'+nonce).encode()).hexdigest()
        return 'speaker-personalisation:'+digest

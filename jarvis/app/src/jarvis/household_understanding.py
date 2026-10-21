"""Conservative read-question repair, never action or identity inference.

No model pass, audio retention, accent claim or permanent transcript logging.
The source of truth remains what STT returned; the short-lived echo is inspectable.
"""
from collections import OrderedDict
import re
import time

from jarvis.household_memory import clean, result
from jarvis.household_speaker import speaker_context, shared_knowledge_enabled


class HouseholdUnderstanding:
    def __init__(self, profile, *, clock=time.monotonic):
        self.profile, self.clock = profile, clock
        self.recent = OrderedDict()

    def process(self, text, key):
        if not shared_knowledge_enabled(self.profile._data):
            self.recent.clear()
            return text, None
        speaker = speaker_context(self.profile._data)['member_id']
        now = self.clock()
        self.recent = OrderedDict((k, v) for k, v in self.recent.items() if v[0] > now)
        identity = (str(key), speaker) if key else None
        value = clean(text)
        lower = value.casefold()
        if lower in ('what did you hear', 'what did you hear me say', 'what words did you hear',
                     'what did you understand', 'hva hørte du'):
            previous = self.recent.get(identity)
            message = ('I received these words: “' + previous[1] + '”.'
                       if previous else 'I have no recent question for this speaker in this conversation.')
            return text, {**result(message), 'provider': 'household_understanding'}
        # Only echo non-secret, bounded questions in this exact speaker/session.
        if identity:
            if (len(value) <= 400 and re.match(r'^(what|when|where|who|how|is|are|do|does|can|could|hva|når)\b', lower)
                    and not re.search(r'\b(password|token|secret|api.?key)\b|sk-[\w-]+', lower)):
                self.recent[identity] = (now + 300, value)
                self.recent.move_to_end(identity)
                while len(self.recent) > 100:
                    self.recent.popitem(last=False)
            else:
                self.recent.pop(identity, None)
        # Preserve writes verbatim, including reminder labels and quoted notes.
        if len(value) > 500 or re.search(
                r'\b(remember|save|forget|delete|confirm|approve|add|create|change|set|turn|switch|'
                r'open|close|unlock|lock|book|cancel|send|buy|pay|remind|flytt|slett|husk|slå)\b', lower):
            return text, None
        value = re.sub(r'^(?:please[, ]+|jarvis[, ]+)+', '', value, flags=re.I)
        value = re.sub(r'^(?:can|could|would) you (?:please )?(?:tell me |say )(?=(?:what|when|who|where|how)\b)', '', value, flags=re.I)
        lower = value.casefold().replace('whats ', 'what is ').replace("what's ", 'what is ')
        names = '|'.join(re.escape(p['preferred_name']) for p in self.profile._data['members'])
        # Exact household names only: never guess Mia from "Maya"/"me a".
        match = re.fullmatch(r'(?:when|what time) (?:does |do |is )?(' + names +
                             r') (?:get out of|finish(?: at)?|finishes|end|ends) school(.*)', lower, re.I)
        if match:
            value = 'When does ' + match[1] + ' get out of school' + match[2] + '?'
        else:
            match = re.fullmatch(r'når (?:slutter|er) (' + names + r') (?:ferdig på skolen|ferdig med skolen|på skolen)(.*)', lower, re.I)
            if match:
                value = 'When does ' + match[1] + ' get out of school' + self._dates(match[2]) + '?'
            elif lower in ('hva er planene i morgen', 'hva har vi planlagt i morgen'):
                value = 'Give us a briefing tomorrow'
            elif lower in ('hva har vi planlagt i helgen', 'hva er planene i helgen'):
                value = 'Give us a briefing this weekend'
            elif lower in ('hva jobber jeg med', 'hva er jobben min'):
                value = 'What is my job?'
            elif lower in ('når har jeg bursdag', 'når er bursdagen min'):
                value = 'When is my birthday?'
            else:
                match = re.fullmatch(r'(?:what is|what are|what have we got|what we have) (?:the |our )?plans(.*)', lower)
                if match:
                    value = 'Give us a briefing' + match[1]
                elif re.fullmatch(r'(?:what is|what are|when is|when does) (?:my|our|the)', lower):
                    return text, {**result('That question seems incomplete. Could you say the missing part?',
                                          'clarification_required'), 'provider': 'household_understanding'}
                else:
                    # A stripped polite prefix is safe only for these read questions.
                    value = value if clean(value) != clean(text) and re.match(r'^(what|when|who|where|how)\b', value, re.I) else text
        return value, None

    @staticmethod
    def _dates(value):
        translations = {'i morgen': 'tomorrow', 'i dag': 'today', 'neste uke': 'next week',
                        'neste torsdag': 'next thursday', 'på torsdag': 'thursday',
                        'på fredag': 'friday', 'neste fredag': 'next friday'}
        return ' ' + translations.get(value.strip(), value.strip()) if value.strip() else ''

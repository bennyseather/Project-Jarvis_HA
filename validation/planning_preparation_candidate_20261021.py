"""Isolated runtime/live-source candidate. No production writes or audio.

Use candidate PYTHONPATH; reports assertions/counts only, not household contents,
credentials, voiceprints, scores, calendar titles or transcripts.
"""
import asyncio
from datetime import datetime, timedelta, timezone
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import yaml

from jarvis.core.application import JarvisApplication
from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.access_policy import resolve_entities
from jarvis.homeassistant.travel_calendar_intelligence import TravelCalendarIntelligence
from jarvis.household_profile import HouseholdProfile
from jarvis.household_speaker import speaker_scope
from jarvis.household_understanding import HouseholdUnderstanding
from jarvis.household_planning import HouseholdConversation
from jarvis.personal_reminders import PersonalReminders, ZONE
from jarvis.planning_preparation import PlanningPreparation
from jarvis.providers.local_first_provider import LocalReasoningPolicy, LocalFirstReasoningProvider


async def main():
    old = json.loads(Path('/config/personalisation-20261021-preservation.json').read_text())
    protected = {p: hashlib.sha256(Path(p).read_bytes()).hexdigest() for p in old}
    live_reminders = Path('/config/personal_reminders.json')
    reminder_before = live_reminders.read_bytes() if live_reminders.exists() else None
    config = yaml.safe_load(Path('/app/config/general.yaml').read_text())
    assert not config['local_reasoning']['fallback_to_openai']
    opts = json.loads(Path('/data/options.json').read_text())
    assert not opts.get('openai_api_key') and not opts.get('openai_fallback_enabled')
    p = HouseholdProfile.load('/config/household_profile.json')
    client = HomeAssistantClient('http://supervisor/core', os.environ['SUPERVISOR_TOKEN'], logging.getLogger('planning-candidate'))
    await client.connect()
    states = await client.get_states()
    ha = config['home_assistant']
    allowed = resolve_entities(SimpleNamespace(entity_ids={s['entity_id'] for s in states}),
        ha.get('allowed_read_entities', ()), ha.get('allowed_read_domains', ()), ha.get('excluded_entities', ()), all_entities=ha.get('all_entities', False))
    registry = SimpleNamespace(all=lambda: [SimpleNamespace(entity_id=s['entity_id'], domain=s['entity_id'].split('.')[0], attributes=s.get('attributes',{})) for s in states])
    provider = LocalFirstReasoningProvider(LocalReasoningPolicy.from_config(config['local_reasoning']), logging.getLogger('candidate-qwen'), fallback=None)
    with tempfile.TemporaryDirectory(prefix='planning-synthetic-') as folder:
        deliveries = []
        async def fake_notify(*args): deliveries.append(args)
        now = [datetime.now(timezone.utc)]
        reminders = PersonalReminders(p, Path(folder)/'reminders.json', SimpleNamespace(call_service=fake_notify), now=lambda: now[0])
        prep = PlanningPreparation(p, client, registry, allowed, reminders=reminders,
            travel=TravelCalendarIntelligence(client,registry,allowed))
        app = JarvisApplication.__new__(JarvisApplication)
        app.container = SimpleNamespace(household_profile=p, home_assistant=client,
            personal_reminders=reminders, planning_preparation=prep,
            proactive_allowed_entities=allowed, local_reasoning_provider=provider,
            household_today_dialogue=HouseholdConversation(client.get_household_today, provider))
        cases = [('benny','What should I prepare for tomorrow?'), ('mia','What should I prepare for tomorrow?'),
                 ('linda','Help me plan tomorrow'), (None,'What should I prepare for tomorrow?'),
                 (None,'What should Mia prepare for tomorrow?'), ('benny','Help us plan next week'),
                 ('benny','Help me prepare for my next trip'), ('linda','Help me prepare for my next trip')]
        for i, (member, question) in enumerate(cases):
            key = 'isolated-preparation-' + str(i)
            start = time.monotonic()
            with speaker_scope({'member_id':member,'basis':'voice_match' if member else 'unknown','conversation_id':key}, p, key):
                answer = await asyncio.wait_for(app.handle_request(question,key), 30)
            assert answer['provider'] == 'planning_preparation'
            assert not answer['cacheable']
            assert answer['status'] == ('clarification_required' if i == 3 else 'unavailable' if i == 7 else 'success')
            print(json.dumps({'live_read_case':i+1,'pass':True,'seconds':round(time.monotonic()-start,3)}),flush=True)
        # These are text-understanding/model cases, not accent/audio benchmarks.
        questions = ['When Mia finish school tomorrow?', 'What time does Mia finishes school tomorrow?',
                     'Can you tell me when Mia finish school tomorrow?', 'Når slutter Mia på skolen i morgen?',
                     'What are our plans tomorrow?', 'What we have plans tomorrow?',
                     'When does Mia get out of school next Thursday?']
        for i, question in enumerate(questions):
            key = 'isolated-language-' + str(i)
            with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':key}, p, key):
                answer = await asyncio.wait_for(app.handle_request(question,key), 35)
            assert answer is not None and answer['status']=='success'
            assert not answer.get('cacheable',False)
            print(json.dumps({'live_language_text_case':i+1,'pass':True}),flush=True)
        tomorrow=(datetime.now().astimezone(ZONE).date()+timedelta(days=1)).isoformat()
        weather=await prep.weather(tomorrow,(datetime.fromisoformat(tomorrow)+timedelta(days=1)).date().isoformat())
        print(json.dumps({'live_weather_coverage':'available' if weather.startswith('Home-area forecast') else 'explicitly_unknown'}),flush=True)
        # Real local-Qwen interpretation of non-native grammar, with synthetic
        # input and a fake loader: no family/calendar facts sent to the model.
        from jarvis.household_planning import HouseholdPlanningDialogue
        parser = HouseholdPlanningDialogue(None, provider)
        for i, question in enumerate(('When is Mia finished with school tomorrow?',
                                      'What appointments Mia have after school tomorrow?')):
            focus = await asyncio.wait_for(asyncio.to_thread(parser.interpret, question.casefold(), ('mia',), None), 15)
            assert focus == ('school_end' if i == 0 else 'after_school')
            print(json.dumps({'local_qwen_grammar_case':i+1,'pass':True}),flush=True)
        key = 'isolated-reminders'
        with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':key}, p, key):
            assert 'Proposed' in reminders.handle('Remind me to check the synthetic fixture in 1 minute', key)['message']
            assert not reminders.path.exists()
            assert 'Saved' in reminders.handle('confirm reminder',key)['message']
            assert len(reminders._load()['items']) == 1
            # Reload to exercise restart persistence; notification call stays fake.
            restarted = PersonalReminders(p, reminders.path, SimpleNamespace(call_service=fake_notify), now=lambda: now[0])
            now[0] += timedelta(minutes=2)
            await restarted.deliver_due(); await restarted.deliver_due()
            assert len(deliveries) == 1
            row = restarted._load()['items'][0]
            assert row['state'] == 'delivered'
            assert 'Proposed' in restarted.handle('Cancel reminder '+row['id'],key)['message']
            assert 'Saved' in restarted.handle('yes',key)['message']
            print(json.dumps({'runtime_reminder_persist_delivery_cancel':True,'real_notifications':0}),flush=True)
    await client.disconnect()
    assert all(hashlib.sha256(Path(path).read_bytes()).hexdigest()==digest for path,digest in protected.items())
    assert (live_reminders.read_bytes() if live_reminders.exists() else None)==reminder_before
    print(json.dumps({'candidate_pass':True,'protected_files_unchanged':len(protected),'production_reminder_writes':0,
                      'audio_recordings':0,'cloud_inference':0}),flush=True)


if __name__=='__main__':
    try:
        asyncio.run(main())
    except Exception as error:
        print(json.dumps({'candidate_pass':False,'error_type':type(error).__name__,'details_suppressed':True}),flush=True)
        raise SystemExit(1)

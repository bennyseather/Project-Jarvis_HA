"""Isolated candidate tests using live read-only HA data and local-only Qwen.

Run with staged candidate PYTHONPATH in the existing app. No authoritative
profile writes, device actions, calendar edits, audio or cloud inference.
All memory writes use a disposable private profile; synthetic notes stay there.
"""
import asyncio
from copy import deepcopy
from datetime import datetime, timedelta
import hashlib
import json
import logging
import os
from pathlib import Path
import tempfile
import time
from types import SimpleNamespace
import yaml
from zoneinfo import ZoneInfo

from jarvis.homeassistant.client import HomeAssistantClient
from jarvis.homeassistant.access_policy import resolve_entities
from jarvis.household_briefing import HouseholdBriefing, SOURCES
from jarvis.household_profile import HouseholdProfile
from jarvis.household_speaker import speaker_scope, resolve_question
from jarvis.household_dialogue import HouseholdDialogue
from jarvis.providers.local_first_provider import LocalReasoningPolicy, LocalFirstReasoningProvider

ZONE=ZoneInfo('Europe/Oslo')


async def main():
    checkpoint=json.loads(Path('/config/personalisation-20261021-preservation.json').read_text())
    def unchanged():
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==d for p,d in checkpoint.items())
    unchanged()
    profile=HouseholdProfile.load('/config/household_profile.json')
    config=yaml.safe_load(Path('/app/config/general.yaml').read_text())
    assert not config['local_reasoning']['fallback_to_openai']
    client=HomeAssistantClient('http://supervisor/core',os.environ['SUPERVISOR_TOKEN'],logging.getLogger('candidate'))
    states=await client.get_states()
    ha=config['home_assistant']
    allowed=resolve_entities(SimpleNamespace(entity_ids={s['entity_id'] for s in states}),ha.get('allowed_read_entities',()),ha.get('allowed_read_domains',()),ha.get('excluded_entities',()),all_entities=ha.get('all_entities',False))
    briefing=HouseholdBriefing(profile,client,allowed)
    cases=[('benny','Give me my briefing today','work'),('benny',"What's next for me?",'work'),
        ('linda','What does my day look like?',None),('mia','What do I have planned tomorrow?','family'),
        (None,'What does my day look like?',None),(None,"What does Mia's day look like tomorrow?",'family'),
        ('benny','Give me my briefing for next week','travel'),('benny','And the following week?','travel')]
    for index,(member,question,source) in enumerate(cases,1):
        identifier='isolated-personalisation' if index>=7 else 'isolated-personalisation-'+str(index)
        hint={'member_id':member,'basis':'voice_match' if member else 'unknown','conversation_id':identifier}
        started=time.monotonic()
        with speaker_scope(hint,profile,identifier):answer=await briefing.handle(question,identifier)
        assert answer is not None
        if index==5:assert answer['status']=='clarification_required'
        else:
            assert answer['provider']=='household_briefing' and answer['read_only'] and not answer['cacheable']
            if source and SOURCES[source] in allowed:assert source in answer['sources_checked'], 'Expected live calendar could not be read for case '+str(index)
            if member=='linda':assert not answer['sources_checked']
        print(json.dumps({'live_candidate_case':index,'pass':True,'seconds':round(time.monotonic()-started,3),
            'sources':answer.get('sources_checked',[]),'characters':len(answer['message'])}),flush=True)
    with tempfile.TemporaryDirectory(prefix='jarvis-memory-candidate-') as folder:
        path=Path(folder)/'profile.json';path.write_text(json.dumps(deepcopy(profile._data)))
        temporary=HouseholdProfile.load(path)
        hint={'member_id':'benny','basis':'voice_match','conversation_id':'isolated-memory'}
        with speaker_scope(hint,temporary,'isolated-memory'):
            for command in ('Remember I prefer synthetic fixture breakfasts', 'yes',
                'What do you remember about me?',
                'Change "Benny prefers synthetic fixture breakfasts" to "Benny prefers synthetic fixture lunches"',
                'yes','Forget "Benny prefers synthetic fixture lunches"','yes','undo last household change','yes'):
                from jarvis.household_memory import memory_question
                response=memory_question(command,temporary) or temporary.edit_request(command,'isolated-memory')
                assert response is not None and response['status'] in ('success','clarification_required')
            assert any(n['text']=='Benny prefers synthetic fixture lunches' for n in temporary._data['conversation_notes'])
        print(json.dumps({'disposable_profile_memory_sequence':9,'pass':True,'authoritative_writes':False}),flush=True)
    # Test semantic recall with a real local model, synthetic facts only.
    fake=HouseholdProfile({'schema_version':1,'revision':1,'roster_complete':True,'assistant':{'name':'Jarvis'},
        'members':[{'id':'benny','preferred_name':'Benny'}],
        'sharing_policy':{'directory_enabled':True,'source':'Synthetic approval','recorded_on':'2026-10-21',
            'relationships':[],'knowledge_access':{'mode':'shared_household','source':'Synthetic approval','recorded_on':'2026-10-21'}},
        'conversational_updates':{'mode':'shared_confirmation','source':'Synthetic approval'},
        'conversation_notes':[{'id':'abcdef12','text':'Benny prefers jasmine tea'}]})
    provider=LocalFirstReasoningProvider(LocalReasoningPolicy.from_config(config['local_reasoning']),logging.getLogger('candidate-model'),fallback=None)
    with speaker_scope({'member_id':'benny','basis':'voice_match','conversation_id':'synthetic-recall'},fake,'synthetic-recall'):
        text,clarification=resolve_question('What drink do I prefer?',fake._data);assert clarification is None
        started=time.monotonic()
        answer=await asyncio.wait_for(asyncio.to_thread(HouseholdDialogue(fake,provider).handle,text,'synthetic-recall'),40)
        assert answer is not None and 'jasmine' in answer['message'].lower() and 'tea' in answer['message'].lower()
        print(json.dumps({'local_model_semantic_memory_recall':True,'seconds':round(time.monotonic()-started,3),
            'reference_characters':len(json.dumps(fake.reasoning_context(text))),'real_household_facts_sent':False}),flush=True)
    await client.disconnect();unchanged()
    print(json.dumps({'all_candidate_checks_passed':True,'protected_files_byte_identical':len(checkpoint)}),flush=True)

if __name__=='__main__':asyncio.run(main())

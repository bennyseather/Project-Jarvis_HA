"""Actual HA Assist and authenticated text-only backend acceptance.

One explicitly diagnostic memory proposal is cancelled, never confirmed. No
calendar writes, devices, TTS playback, microphone recording or cloud calls.
Credentials stay in memory; output contains case results/timings only.
"""
import asyncio
from datetime import datetime,timedelta
import hashlib
import json
import os
from pathlib import Path
import sqlite3
import time
import urllib.request
import websockets
from zoneinfo import ZoneInfo


async def main():
    baseline=json.loads(Path('/config/personalisation-20261021-preservation.json').read_text())
    def unchanged():
        assert all(hashlib.sha256(Path(p).read_bytes()).hexdigest()==d for p,d in baseline.items())
    unchanged()
    opts=json.loads(Path('/data/options.json').read_text())
    assert not opts['openai_api_key'] and not opts['openai_fallback_enabled']
    def post(url,token,body):
        req=urllib.request.Request(url,data=json.dumps(body).encode(),headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
        with urllib.request.urlopen(req,timeout=40) as response:return json.load(response)
    async with websockets.connect('ws://supervisor/core/websocket',open_timeout=10) as ws:
        await ws.recv();await ws.send(json.dumps({'type':'auth','access_token':os.environ['SUPERVISOR_TOKEN']}))
        assert json.loads(await ws.recv())['type']=='auth_ok'
        await ws.send(json.dumps({'id':1,'type':'conversation/agent/list'}))
        d=json.loads(await ws.recv());agent=next(a['id'] for a in d['result']['agents'] if a['name']=='Project Jarvis')
    now=datetime.now(ZoneInfo('Europe/Oslo')).date()
    tomorrow=now+timedelta(days=1)
    monday=now+timedelta(days=7-now.weekday())
    following=monday+timedelta(days=7)
    cases=[('Give us a household briefing today',('household briefing',)),
        ('And tomorrow?',(str(tomorrow.day)+' '+tomorrow.strftime('%B'),)),
        ('Give us a household briefing for next week',('household briefing',str(monday.day)+' '+monday.strftime('%B'))),
        ('And the following week?',(str(following.day)+' '+following.strftime('%B'),)),
        ("What does Mia's day look like tomorrow?",("Mia's briefing",)),
        ('What does my day look like?',('Whose',)),
        ('How old is Mia?',('9 years old',)),
        ("What is Benny's job?",('Reach Subsea',)),
        ('Is anything scheduled after school tomorrow?',('Whose','Mia','Emrik')),
        ('When does Mia get out of school next Thursday?',('12:50',)),
        ('And Friday?',('12:50',))]
    conversation=None
    for index,(question,expected) in enumerate(cases,1):
        payload={'agent_id':agent,'text':question,'language':'en'}
        if conversation:payload['conversation_id']=conversation
        started=time.monotonic()
        reply=await asyncio.to_thread(post,'http://supervisor/core/api/conversation/process',os.environ['SUPERVISOR_TOKEN'],payload)
        conversation=reply['conversation_id'];text=reply['response']['speech']['plain']['speech']
        assert all(s in text for s in expected),'HA Assist acceptance case '+str(index)+' failed'
        print(json.dumps({'ha_assist_case':index,'pass':True,'seconds':round(time.monotonic()-started,3),'characters':len(text)}),flush=True)
    key='postdeploy-personalisation-20261021'
    backend_cases=[('benny','Give me my briefing today',('your briefing',)),
        ('benny',"What's next for me?",('your next-up briefing',)),
        ('linda','What does my day look like?',('your briefing','Linda')),
        (None,'What does my day look like?',('Whose',)),
        ('benny','Remember I prefer a synthetic diagnostic note that must not be saved',('Proposed','Benny')),
        ('benny','cancel household change',('cancelled','Nothing was saved')),
        ('benny','What do you remember about me?',('You work','41 years old'))]
    for index,(member,question,expected) in enumerate(backend_cases,1):
        hint={'member_id':member,'basis':'voice_match' if member else 'unknown','conversation_id':key}
        started=time.monotonic()
        reply=await asyncio.to_thread(post,'http://127.0.0.1:8099/v1/conversation',opts['bridge_api_key'],
            {'text':question,'conversation_id':key,'voice_mode':False,'speaker_context':hint})
        assert all(s in reply['message'] for s in expected),'Structured-speaker acceptance case '+str(index)+' failed'
        print(json.dumps({'structured_speaker_case':index,'pass':True,'seconds':round(time.monotonic()-started,3)}),flush=True)
    unchanged()
    with sqlite3.connect('file:/config/jarvis.sqlite3?mode=ro',uri=True) as db:assert db.execute('PRAGMA quick_check').fetchone()[0]=='ok'
    print(json.dumps({'all_live_checks_passed':True,'protected_files_byte_identical':len(baseline),
        'sqlite_quick_check':'ok','synthetic_note_confirmed':False,'acoustic_voice_test':False}),flush=True)

if __name__=='__main__':asyncio.run(main())

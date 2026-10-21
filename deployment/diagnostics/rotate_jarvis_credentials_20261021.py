"""Approved HA-host orchestration. Secrets stay in process memory on HA.

Run through SSH as benny on HA, not on the development computer. Inner docker
output is captured, never forwarded. Uses supported Supervisor and HA flows;
does not edit .storage or operate devices. New bridge key replaces existing
authority only. OpenAI account-side revocation remains an owner task.
"""
import json
import os
import secrets
import subprocess
import time
import urllib.request

APP='app_85a88fc0_jarvis'
ENTRY='01KYDZZ4CVVFT94CK33KAW65JA'
REMOTE=r'''
import json,os,sys,urllib.request,urllib.error
from pathlib import Path
p=json.load(sys.stdin)
token=os.environ['SUPERVISOR_TOKEN']
def call(url,method='GET',body=None):
 req=urllib.request.Request(url,data=json.dumps(body).encode() if body is not None else None,
    method=method,headers={'Authorization':'Bearer '+token,'Content-Type':'application/json'})
 with urllib.request.urlopen(req,timeout=40) as r:return json.load(r)
if p['mode']=='read':
 options=json.loads(Path('/data/options.json').read_text())
 entries=json.loads(Path('/homeassistant/.storage/core.config_entries').read_text())['data']['entries']
 entry=next(e for e in entries if e['entry_id']==p['entry'])
 assert options.get('local_reasoning_enabled') is True
 print(json.dumps({'options':options,'entry_data':entry['data'],'entry_options':entry['options']}))
elif p['mode']=='options':
 r=call('http://supervisor/addons/85a88fc0_jarvis/options','POST',{'options':p['options']})
 assert r['result']=='ok';print('{}')
elif p['mode']=='flow':
 r=call('http://supervisor/core/api/config/config_entries/flow','POST',
        {'handler':'jarvis_conversation','show_advanced_options':False,'entry_id':p['entry']})
 assert r['type']=='form' and r['step_id']=='reconfigure'
 r=call('http://supervisor/core/api/config/config_entries/flow/'+r['flow_id'],'POST',{'api_key':p['key']})
 assert r['type']=='abort' and r['reason']=='reconfigure_successful'
 print('{}')
elif p['mode']=='verify':
 opts=json.loads(Path('/data/options.json').read_text())
 entries=json.loads(Path('/homeassistant/.storage/core.config_entries').read_text())['data']['entries']
 entry=next(e for e in entries if e['entry_id']==p['entry'])
 assert entry['data']=={**p['entry_data'],'api_key':p['key']}
 assert entry['options']==p['entry_options']
 assert opts==p['options'] and not opts['openai_api_key'] and not opts['openai_fallback_enabled']
 for key,expected in [(p['key'],200),(p['old'],401)]:
  req=urllib.request.Request('http://127.0.0.1:8099/v1/household',headers={'Authorization':'Bearer '+key})
  try:
   with urllib.request.urlopen(req,timeout=10) as r:status=r.status
  except urllib.error.HTTPError as e:status=e.code
  assert status==expected
 print('{}')
'''

def inner(payload):
    result=subprocess.run(['sudo','-n','docker','exec','-i',APP,'python3','-c',REMOTE],
        input=json.dumps(payload),capture_output=True,text=True,timeout=55)
    if result.returncode:raise RuntimeError('Credential operation failed; secret-bearing subprocess details suppressed')
    return json.loads(result.stdout)

def restart():
    r=subprocess.run(['sudo','-n','-i','ha','apps','restart','85a88fc0_jarvis'],
        capture_output=True,text=True,timeout=100)
    if r.returncode:raise RuntimeError('Jarvis restart failed')

def main():
    assert os.environ.get('SUPERVISOR_TOKEN'), 'Use the existing authorised SSH admin login environment'
    before=inner({'mode':'read','entry':ENTRY})
    old=before['entry_data']['api_key']
    resuming=old!=before['options']['bridge_api_key']
    if resuming:
        assert not before['options']['openai_api_key'] and not before['options']['openai_fallback_enabled']
    new=before['options']['bridge_api_key'] if resuming else secrets.token_urlsafe(48)
    options={**before['options'],'bridge_api_key':new,'openai_api_key':'','openai_fallback_enabled':False}
    # The ordinary Jarvis app is correctly forbidden from changing Supervisor
    # options. Use the already-authorised admin SSH environment, not a wider
    # permission grant to Jarvis or an edit of Supervisor storage.
    if not resuming:
        request=urllib.request.Request('http://supervisor/addons/85a88fc0_jarvis/options',
            data=json.dumps({'options':options}).encode(),
            headers={'Authorization':'Bearer '+os.environ['SUPERVISOR_TOKEN'],'Content-Type':'application/json'})
        with urllib.request.urlopen(request,timeout=30) as response:
            assert json.load(response)['result']=='ok'
    # No automatic rollback to the exposed credential after it has been revoked.
    # On a flow failure the new key remains in Supervisor options for recovery.
    if not resuming:restart()
    deadline=time.monotonic()+120
    while True:
        try:
            inner({'mode':'flow','entry':ENTRY,'key':new});break
        except Exception:
            if time.monotonic()>deadline:raise RuntimeError('Credential flow incomplete; recover from current Supervisor options, not exposed old key')
            time.sleep(3)
    deadline=time.monotonic()+30
    while True:
        try:
            # HA saves config entries asynchronously; wait for supported-flow
            # persistence before checking the on-disk representation.
            inner({'mode':'verify','entry':ENTRY,'key':new,'old':old,'options':options,
                   'entry_data':before['entry_data'],'entry_options':before['entry_options']})
            break
        except Exception:
            if time.monotonic()>deadline:raise RuntimeError('Credential read-back incomplete; do not restore exposed keys')
            time.sleep(2)
    print(json.dumps({'bridge_rotated':True,'old_bridge_rejected':True,'new_bridge_authenticated':True,
        'entry_reconfigured_supported_api':True,'voice_options_unchanged':True,
        'openai_key_removed_from_active_jarvis':True,'cloud_fallback_disabled':True,
        'openai_account_revocation':'pending_owner_access','secrets_printed':False}))

if __name__=='__main__':main()

"""Authenticated shared planner proxy; browser never receives bridge credentials."""
import asyncio
from aiohttp import ClientError,ClientTimeout
import voluptuous as vol
from homeassistant.components import websocket_api
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.auth.permissions.const import POLICY_CONTROL,POLICY_READ

@websocket_api.websocket_command({vol.Required('type'):'jarvis_conversation/planner',
    vol.Required('action'):vol.In(('agenda','review','confirm','assign_review')),vol.Required('payload'):dict})
@websocket_api.async_response
async def planner(hass,connection,msg):
    action=msg['action']
    if not connection.user.permissions.check_entity('calendar.familiekalender',POLICY_READ if action=='agenda' else POLICY_CONTROL):
        connection.send_error(msg['id'],'forbidden','Access to Familiekalender is required.');return
    # Agenda may include connected work/travel sources. Refuse this projection if
    # HA would otherwise deny the caller those entities; never bypass permissions.
    selected=msg['payload'].get('members',[])
    if (action!='agenda' or not selected or 'benny' in selected) and any(hass.states.get(e) and not connection.user.permissions.check_entity(e,POLICY_READ)
        for e in ('calendar.work_reach','calendar.jarvis_travels')):
        connection.send_error(msg['id'],'forbidden','Access to the connected agenda sources is required.');return
    entries=[e for e in hass.config_entries.async_entries('jarvis_conversation') if e.data.get('bridge_url') and e.data.get('api_key')]
    targets={(e.data['bridge_url'],e.data['api_key']) for e in entries}
    if len(targets)!=1:connection.send_error(msg['id'],'unavailable','A single Jarvis bridge is required.');return
    url,key=next(iter(targets))
    try:
        import json
        if len(json.dumps(msg['payload']))>6000:raise ValueError('Request too large')
        body={'action':action,'payload':msg['payload'],'owner':str(connection.user.id)+':'+str(id(connection))}
        async with async_get_clientsession(hass).post(url.rstrip('/')+'/v1/planner',json=body,
            headers={'Authorization':'Bearer '+key},timeout=ClientTimeout(total=34)) as response:
            response.raise_for_status();data=await response.json()
        if data.get('schema_version')!=1 or type(data.get('ok')) is not bool:raise ValueError('Invalid planner response')
        if data['ok']:connection.send_result(msg['id'],data['result'])
        else:connection.send_error(msg['id'],'invalid_request',data.get('error','Please review the appointment again.'))
    except (ClientError,asyncio.TimeoutError,ValueError):
        connection.send_error(msg['id'],'unavailable','Planner unavailable. If saving, refresh and check before retrying.')

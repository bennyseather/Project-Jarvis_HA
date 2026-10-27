"""Authenticated HA websocket proxy. Bridge credentials never reach the browser."""
import asyncio
import voluptuous as vol
from aiohttp import ClientError, ClientTimeout
from homeassistant.components import websocket_api
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from .today import add_period, period_bounds, PERIODS, ZONE
from datetime import datetime

@websocket_api.websocket_command({vol.Required('type'):'jarvis_conversation/household',vol.Optional('period',default='today'):vol.In(PERIODS),
    vol.Optional('start_date'):str,vol.Optional('end_date'):str})
@websocket_api.async_response
async def household(hass, connection, msg):
    entries=[entry for entry in hass.config_entries.async_entries('jarvis_conversation')
             if entry.data.get('bridge_url') and entry.data.get('api_key')]
    targets={(entry.data['bridge_url'],entry.data['api_key']) for entry in entries}
    if len(targets)!=1:
        connection.send_error(msg['id'],'unavailable','A single configured Jarvis bridge is required.')
        return
    url,key=next(iter(targets))
    try:
        # Reject malformed/oversized reads before touching either source.
        period_bounds(msg.get('period','today'),datetime.now(ZONE),msg.get('start_date'),msg.get('end_date'))
        async with async_get_clientsession(hass).get(url.rstrip('/')+'/v1/household',
                headers={'Authorization':'Bearer '+key}, timeout=ClientTimeout(total=10)) as response:
            response.raise_for_status()
            data=await response.json()
        if data.get('schema_version')!=1 or data.get('read_only') is not True:
            raise ValueError('Unsupported response')
        data=await asyncio.wait_for(add_period(hass,data,msg.get('period','today'),start_date=msg.get('start_date'),end_date=msg.get('end_date')),10)
        connection.send_result(msg['id'],data)
    except (ClientError, asyncio.TimeoutError, ValueError):
        connection.send_error(msg['id'],'unavailable','Household information is temporarily unavailable.')

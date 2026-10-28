"""Fixed-calendar, version-checked Google edits using the existing HA OAuth session.

No OAuth credentials leave Core. No invitation-bearing events or series-wide
edits. The standard Google integration has no UPDATE_EVENT implementation.
"""
import asyncio,dataclasses,json,re
from datetime import date,datetime,timedelta
from pathlib import Path
from urllib.parse import quote
from zoneinfo import ZoneInfo
from aiohttp import ClientTimeout
import voluptuous as vol
from homeassistant.auth.permissions.const import POLICY_CONTROL
from homeassistant.components import websocket_api
from homeassistant.components.calendar import DATA_COMPONENT,CalendarEntityFeature
from .calendar_mutations import MutationStore,VersionConflict
from .planner_membership import identity
CALENDAR='calendar.familiekalender';ZONE=ZoneInfo('Europe/Oslo')

class GoogleSource:
    def __init__(self,hass):self.hass=hass
    def entity(self):
        entity=self.hass.data[DATA_COMPONENT].get_entity(CALENDAR)
        if (entity is None or entity.__class__.__module__!='homeassistant.components.google.calendar'
                or entity.entity_description.read_only or not entity.supported_features&CalendarEntityFeature.DELETE_EVENT):
            raise ValueError('The writable household Google calendar is unavailable')
        if not hasattr(entity.coordinator,'sync'):raise ValueError('This calendar connection needs the phone editor')
        return entity
    async def resolve(self,selection):
        if not isinstance(selection,dict) or set(selection)!={'key','start','end'} or not re.fullmatch(r'[0-9a-f]{64}',selection['key']):raise ValueError('Invalid appointment selection')
        a=date.fromisoformat(selection['start']);b=date.fromisoformat(selection['end'])
        if not 1<=(b-a).days<=14:raise ValueError('Choose an appointment within fourteen days')
        entity=self.entity();events=await entity.async_get_events(self.hass,datetime.combine(a,datetime.min.time(),ZONE),datetime.combine(b,datetime.min.time(),ZONE))
        matches=[]
        for event in events:
            fields={'summary':event.summary,'start':event.start.isoformat(),'end':event.end.isoformat()}
            if identity(fields)==selection['key']:matches.append(event)
        if len(matches)!=1:raise ValueError('The appointment changed or is ambiguous; refresh and select it again')
        event=matches[0];master=await entity.coordinator.sync.store_service._lookup_ical_uuid(event.uid)
        if not master or not master.id:raise ValueError('The Google event could not be identified')
        if master.recurrence and not event.recurrence_id:raise ValueError('Choose one occurrence of the repeating appointment')
        ref={'id':event.recurrence_id or master.id,'calendar':entity.calendar_id}
        raw=await self.get(ref)
        if not raw or raw.get('iCalUID')!=event.uid or raw.get('id')!=ref['id']:raise ValueError('The source calendar entry changed')
        if bool(event.recurrence_id)!=bool(raw.get('recurringEventId')):raise ValueError('The recurrence selection needs to be checked in your phone calendar')
        if identity({'summary':raw.get('summary',''),'start':raw['start'],'end':raw['end']})!=selection['key']:raise ValueError('The appointment changed on your phone; refresh before editing')
        return ref,raw
    async def request(self,ref,method,patch=None,version=None):
        entity=self.entity()
        if not isinstance(ref,dict) or set(ref)!={'id','calendar'} or ref['calendar']!=entity.calendar_id or not isinstance(ref['id'],str) or not 1<=len(ref['id'])<=512:raise ValueError('Wrong calendar reference')
        auth=entity.coordinator.sync.api._auth
        token=await auth.async_get_access_token()
        headers={'Authorization':'Bearer '+token}
        if version:headers['If-Match']=version
        url='https://www.googleapis.com/calendar/v3/calendars/'+quote(ref['calendar'],safe='')+'/events/'+quote(ref['id'],safe='')
        kwargs={'headers':headers,'timeout':ClientTimeout(total=10)}
        if method!='get':kwargs['params']={'sendUpdates':'none'}
        if patch is not None:kwargs['json']=patch
        async with auth._websession.request(method,url,**kwargs) as response:
            if response.status==412:raise VersionConflict('Newer calendar version')
            if method=='get' and response.status in (404,410):return None
            if response.status>=400:raise ValueError('Google calendar request could not be completed')
            if response.status==204:return None
            raw=await response.read()
            if len(raw)>1500000:raise ValueError('Calendar response too large')
            return json.loads(raw) if raw else None
    async def get(self,ref):return await self.request(ref,'get')
    async def write(self,ref,operation,patch,version):
        # PATCH cancellation preserves a recurring occurrence's parent series.
        return await self.request(ref,'patch',{'status':'cancelled'} if operation=='cancel' else patch,version)
    async def refresh(self):await self.entity().coordinator.async_refresh()

@websocket_api.websocket_command({vol.Required('type'):'jarvis_conversation/calendar_manage',
    vol.Required('action'):vol.In(('inspect','prepare','commit')),vol.Required('payload'):dict})
@websocket_api.async_response
async def calendar_manage(hass,connection,msg):
    if not connection.user.permissions.check_entity(CALENDAR,POLICY_CONTROL):
        connection.send_error(msg['id'],'forbidden','Calendar control permission is required.');return
    payload=msg['payload']
    try:
        if len(json.dumps(payload))>6500:raise ValueError('Calendar request too large')
        domain=hass.data.setdefault('jarvis_conversation',{})
        store=domain.get('calendar_mutations')
        if store is None:
            store=MutationStore(GoogleSource(hass),Path(hass.config.path('.jarvis-calendar-mutations.sqlite3')))
            domain['calendar_mutations']=store
        async with asyncio.timeout(25):
            if msg['action']=='inspect' and set(payload)=={'selection'}:result=await store.inspect(payload['selection'])
            elif msg['action']=='prepare' and set(payload)=={'selection','operation','patch','version'}:
                result=await store.prepare(str(connection.user.id),**payload)
            elif msg['action']=='commit' and set(payload)=={'token'}:result=await store.commit(str(connection.user.id),payload['token'])
            else:raise ValueError('Invalid calendar request')
        connection.send_result(msg['id'],result)
    except ValueError as error:connection.send_error(msg['id'],'review_required',str(error))
    except Exception:connection.send_error(msg['id'],'unavailable','Calendar operation not confirmed. Check the calendar before retrying.')

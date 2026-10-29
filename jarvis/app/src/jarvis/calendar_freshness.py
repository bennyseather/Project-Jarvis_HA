"""Calendar refresh receipts from HA helpers; never infer success from a UI read.

Receipts describe the last completed Jarvis-requested source refresh. A provider
may publish changes later. No calendar URLs, content, credentials or actions.
"""
import asyncio,json
from datetime import datetime,timezone
SOURCES={'family':('calendar.familiekalender','input_text.jarvis_calendar_sync_family','Household'),
         'work':('calendar.work_reach','input_text.jarvis_calendar_sync_work','Work Reach'),
         'travel':('calendar.jarvis_travels','input_text.jarvis_calendar_sync_travel','Jarvis Travels')}

def receipt(raw,now):
 def unknown():return {'status':'unknown','last_success':None,'last_attempt':None,'last_failure':None,'basis':'Jarvis-requested source refresh'}
 try:
  d=json.loads(raw)
  if not isinstance(d,dict) or set(d)!={'v','attempt','success','failure','status'} or type(d['v']) is not int or d['v']!=1 or d['status'] not in ('unknown','refreshing','ok','failed'):return unknown()
  stamp=now.timestamp()
  for key in ('attempt','success','failure'):
   value=d[key]
   if value is not None and (type(value) is not int or not 0<value<=stamp+60):return unknown()
  attempt,success,failure=(d[k] for k in ('attempt','success','failure'))
  if d['status']=='unknown':return unknown()
  if attempt is None or any(v is not None and v>attempt for v in (success,failure)):return unknown()
  if d['status']=='ok' and success!=attempt:return unknown()
  if d['status']=='failed' and failure!=attempt:return unknown()
  status={'ok':'fresh','failed':'failed','refreshing':'refreshing'}[d['status']]
  if status=='refreshing' and stamp-attempt>90:status='incomplete'
  if status=='fresh' and stamp-success>2100:status='stale'
  iso=lambda value:datetime.fromtimestamp(value,timezone.utc).isoformat() if value is not None else None
  return {'status':status,'last_success':iso(success),'last_attempt':iso(attempt),'last_failure':iso(failure),'basis':'Jarvis-requested source refresh'}
 except (ValueError,TypeError,OverflowError,OSError):return unknown()

async def collect(client,names,now):
 method=getattr(client,'get_calendar_health',None)
 if method is None:return {} # Older read clients have no sync telemetry; never fabricate a timestamp.
 try:raw=await asyncio.wait_for(method([SOURCES[n][1] for n in names]),5)
 except Exception:raw={}
 rows={}
 for n in names:
  value=raw.get(SOURCES[n][1]) if isinstance(raw,dict) else None
  row={'entity_id':SOURCES[n][0],'name':SOURCES[n][2],**receipt(value.get('receipt') if isinstance(value,dict) else value,now)}
  if isinstance(value,dict):
   if value.get('monitoring_enabled') is False:row['status']='not_configured'
   if value.get('source_state')=='unavailable':row['status']='unavailable'
   elif value.get('source_state') not in ('on','off'):row['status']='unknown'
  rows[n]=row
 return rows

def current_health(records,now):
 from copy import deepcopy
 rows=deepcopy(records)
 for row in rows.values():
  try:
   if row['status']=='fresh' and (now-datetime.fromisoformat(row['last_success'])).total_seconds()>2100:row['status']='stale'
   if row['status']=='refreshing' and (now-datetime.fromisoformat(row['last_attempt'])).total_seconds()>90:row['status']='incomplete'
  except (ValueError,TypeError,KeyError):row['status']='unknown'
 return rows

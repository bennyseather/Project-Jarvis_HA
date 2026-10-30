"""Explicit dated preparation reports in the existing assistant state store.

Reports are household statements, never attendance or verified location. A new
calendar version never inherits old readiness. No source calendar is stored here.
"""
import json
from copy import deepcopy
from jarvis.companion_store import bounded,secret,instruction_attempt,stamp
from jarvis.household_activities import safe
PREFIX='planning_report:'
class PlanningReports:
 def __init__(self,store):self.store=store
 @property
 def revision(self):
  row=self.store.db.execute("SELECT value FROM assistant_state WHERE key='planning_revision'").fetchone()
  return int(row[0]) if row else 0
 def touch(self):
  self.store.db.execute("INSERT INTO assistant_state VALUES ('planning_revision',?) ON CONFLICT(key) DO UPDATE SET value=excluded.value",(str(self.revision+1),))
 def present(self):return self.store.db.execute("SELECT 1 FROM assistant_state WHERE key LIKE 'planning_report:%' LIMIT 1").fetchone() is not None
 def key(self,item):return PREFIX+item['id']+':'+item['version']
 def get(self,item):
  row=self.store.db.execute('SELECT value FROM assistant_state WHERE key=?',(self.key(item),)).fetchone()
  if not row:return None
  try:
   data=json.loads(row[0]);assert data['schema_version']==1 and data['event_id']==item['id'] and data['event_version']==item['version']
   return deepcopy(data)
  except (ValueError,KeyError,TypeError,AssertionError):return None
 def save(self,item,details,checked,quote,actor):
  quote=bounded(quote,700)
  if not quote or secret(quote) or instruction_attempt(quote):raise ValueError('Use a direct preparation report without credentials or instructions.')
  if not isinstance(details,dict) or set(details)-{'venue','equipment','preparation','journey_minutes','journey_quote'}:raise ValueError('Unsupported dated detail')
  for field,maximum in (('venue',180),('preparation',240),('journey_quote',160)):
   if field in details and not safe(details[field],maximum):raise ValueError('Invalid dated detail text')
  if 'equipment' in details and (not isinstance(details['equipment'],list) or len(details['equipment'])>12 or any(not safe(v,100) for v in details['equipment'])):raise ValueError('Invalid dated equipment')
  if 'journey_minutes' in details and (type(details['journey_minutes']) not in (int,float) or not 0<details['journey_minutes']<=1440 or not details.get('journey_quote')):raise ValueError('Invalid reported journey')
  if not isinstance(checked,list) or len(checked)>20 or any(not isinstance(v,str) or len(v)>40 for v in checked):raise ValueError('Invalid preparation checklist')
  value={'schema_version':1,'event_id':item['id'],'event_version':item['version'],'person':item['person'],'source':item['source'],'date':item['date'],'title':item['title'],'details':deepcopy(details),'checked':list(dict.fromkeys(checked)),'quote':quote,'recorded_at':stamp(self.store.now()),'actor':actor,'basis':'Household-reported preparation; not attendance or verified location'}
  if len(json.dumps(value))>6000:raise ValueError('Preparation report is too large')
  with self.store.db:
   self.store.db.execute('INSERT INTO assistant_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(self.key(item),json.dumps(value,ensure_ascii=False)));self.touch()
  return value
 def clear(self,item):
  with self.store.db:
   deleted=self.store.db.execute('DELETE FROM assistant_state WHERE key=?',(self.key(item),)).rowcount
   if deleted:self.touch()

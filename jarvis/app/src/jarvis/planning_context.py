"""Current-source, person-bound reported planning context. No source writes."""
from copy import deepcopy
from datetime import datetime
from jarvis.companion_store import digest
from jarvis.household_activities import safe,title_key
ENTITIES={'family':'calendar.familiekalender','work':'calendar.work_reach','travel':'calendar.jarvis_travels'}
def revision(profile):
 owner=getattr(profile,'_companion',None)
 return owner.followups.reports.revision if owner and getattr(owner,'followups',None) else 0

def source_context(profile,raw,source,meta,now):
 """Build the SAME normalized signature as the shared planner, from fresh raw data."""
 owner=getattr(profile,'_companion',None);followups=getattr(owner,'followups',None)
 if not followups or not followups.enabled() or not followups.reports.present():return None
 from jarvis.household_briefing import interval
 from jarvis.calendar_membership import identity
 parsed=interval(raw,event_context=True)
 if parsed['end']<=now:return None
 entity=ENTITIES[source]
 if entity not in owner.container.proactive_allowed_entities:return None
 row={'key':identity(raw),'title':parsed['title'],'start':parsed['start'].isoformat(),'end':parsed['end'].isoformat(),'all_day':parsed['all_day'],
      'location':parsed.get('location','') or meta.get('extracted_location',''),'notes':meta['notes'][:1200],'members':meta['members'],'category':meta['category'],'source':entity}
 records=[]
 for person in meta['members']:
  item=followups.build(row,person);report=followups.reports.get(item)
  if not report:continue
  details=report['details']
  records.append({'person':person,'version':item['version'],'recorded_at':report['recorded_at'],'details':deepcopy(details),'checklist':deepcopy(item['checklist']),
                  'basis':'Confirmed household report for this occurrence; not attendance or location tracking'})
 if not records:return None
 venues={title_key(v['details']['venue']):v['details']['venue'] for v in records if v['details'].get('venue')}
 venue=next(iter(venues.values())) if len(venues)==1 else ''
 current=row['location']
 if current and not safe(current,180):return None
 conflict=bool(len(venues)>1 or current and venue and title_key(current)!=title_key(venue))
 return {'records':records,'reported_venue':venue,'venue_conflict':conflict,'source_venue':current,'revision':revision(profile)}

def scoped(context,owners):
 if not context:return None
 value=deepcopy(context);value['records']=[r for r in value['records'] if r['person'] in owners]
 if not value['records']:return None
 venues={title_key(r['details']['venue']):r['details']['venue'] for r in value['records'] if r['details'].get('venue')}
 value['reported_venue']=next(iter(venues.values())) if len(venues)==1 else ''
 value['venue_conflict']=bool(len(venues)>1 or value['source_venue'] and value['reported_venue'] and title_key(value['source_venue'])!=title_key(value['reported_venue']))
 return value

def project(event):
 return scoped(event.get('planning_context'),event['owners'])

def route_context(event):
 context=project(event)
 if not context:return None
 if context['venue_conflict']:return {'conflict':True}
 venue=event.get('location') or context['reported_venue']
 estimates={r['details']['journey_minutes'] for r in context['records'] if r['details'].get('journey_minutes') and
            (r['details'].get('venue') or venue) and (not r['details'].get('venue') or title_key(r['details']['venue'])==title_key(venue))}
 return {'conflict':False,'venue':venue,'reported_venue':not bool(event.get('location')) and bool(context['reported_venue']),
         'journey_minutes':next(iter(estimates)) if len(estimates)==1 else None}

def fingerprint(evidence):
 return digest([{k:f.get(k) for k in ('id','kind','owners','text','start','end','location','description','planning_context')} for f in evidence['facts']])

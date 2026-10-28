"""Reviewed existing-event edits on the same planner journal and calendar."""
from datetime import datetime,timedelta,timezone
import hashlib,json
from jarvis.household_planner import ZONE,local_time
from jarvis.calendar_membership import description,identity,uid_identity,content_fingerprint

def form(event,meta):
    all_day=event['all_day'];a=datetime.fromisoformat(event['start']);b=datetime.fromisoformat(event['end'])
    if not all_day:a=a.astimezone(ZONE);b=b.astimezone(ZONE)
    return {'title':event['summary'],'members':meta['members'],'category':meta['category'],
        'start':a.date().isoformat() if all_day else a.strftime('%Y-%m-%dT%H:%M'),
        'end':(b.date()-timedelta(days=1)).isoformat() if all_day else b.strftime('%Y-%m-%dT%H:%M'),
        'all_day':all_day,'location':event['location'],'notes':meta['notes']}

async def inspect(planner,selection):
    planner.guard(write=True)
    result=await planner.client.manage_household_appointment('inspect',{'selection':selection})
    event=result['event'];return result,form(event,planner.assign(event))

async def review(planner,selection,operation,changes,owner):
    if not isinstance(changes,dict) or set(changes)-{'title','members','category','location','date','time','duration','end_time','all_day','venue_known'}:raise ValueError('Unsupported appointment details')
    revision=planner.profile._data['revision'];source,draft=await inspect(planner,selection)
    before=source['event'];original=dict(draft);old=ds=local_time(draft['start'],draft['all_day']);end=local_time(draft['end'],draft['all_day'])
    if draft['all_day']:end+=timedelta(days=1)
    if operation=='update':
        if changes.get('all_day') is not None and changes['all_day']!=draft['all_day']:raise ValueError('Please change timed/all-day format in your phone calendar')
        for key in ('title','members','category','location'):
            if key in changes:draft[key]=changes[key]
        day=changes.get('date',ds.date().isoformat());clock=changes.get('time',ds.strftime('%H:%M'))
        if 'date' in changes or 'time' in changes:
            start=local_time(day,draft['all_day']) if draft['all_day'] else local_time(day+'T'+clock)
            end=start+timedelta(days=(end.date()-old.date()).days) if draft['all_day'] else (start.astimezone(timezone.utc)+(end.astimezone(timezone.utc)-old.astimezone(timezone.utc))).astimezone(ZONE)
        else:start=ds
        if changes.get('duration'):
            if draft['all_day']:raise ValueError('Use the phone calendar to change an all-day duration')
            end=(start.astimezone(timezone.utc)+timedelta(minutes=changes['duration'])).astimezone(ZONE)
        elif changes.get('end_time'):
            if draft['all_day']:raise ValueError('Use the phone calendar to change an all-day duration')
            end=local_time(start.date().isoformat()+'T'+changes['end_time'])
        draft['start']=start.date().isoformat() if draft['all_day'] else start.strftime('%Y-%m-%dT%H:%M')
        draft['end']=(end.date()-timedelta(days=1)).isoformat() if draft['all_day'] else end.strftime('%Y-%m-%dT%H:%M')
        if draft==original:return {'state':'unchanged','message':'That appointment already has those details.'}
        after=planner.draft({**draft,'notes':''});after['notes']=draft['notes']
        if not draft['all_day'] and datetime.fromisoformat(after['start'])<=planner.now():raise ValueError('That start time has already passed')
        old_meta=planner.assign(before)
        marker=old_meta.get('planner_id') or hashlib.sha256((before['uid']+str(before.get('recurrence_id') or '')).encode()).hexdigest()[:32]
        patch={'summary':after['title'],'location':after['location']}
        if old_meta.get('planner_id') and (after['members']!=old_meta['members'] or after['category']!=old_meta['category']):
            if len(after['notes'])>3000:raise ValueError('Please change this long-note appointment assignment in your phone calendar')
            patch['description']=description(after['members'],after['category'],marker,after['notes'])
        if draft['all_day']:patch.update(start={'date':after['start']},end={'date':after['end']})
        else:patch.update(start={'dateTime':after['start'],'timeZone':'Europe/Oslo'},end={'dateTime':after['end'],'timeZone':'Europe/Oslo'})
        a=datetime.fromisoformat(after['start']);b=datetime.fromisoformat(after['end'])
        if draft['all_day']:a=a.replace(tzinfo=ZONE);b=b.replace(tzinfo=ZONE)
        rows=await planner.read(a,b)
        rows=[e for e in rows if not (e.get('uid')==before['uid'] and e.get('recurrence_id')==before.get('recurrence_id'))]
        duplicates,overlaps=planner.compare(after,rows)
        if duplicates:return {'state':'duplicate','message':'Another appointment already has those details. Nothing was changed.'}
        other,failures=await planner.other_overlaps(after);overlaps+=other
    elif operation=='cancel':patch={};after=None;overlaps=[];failures=[]
    else:raise ValueError('Unsupported appointment operation')
    if revision!=planner.profile._data['revision']:raise ValueError('Household details changed; review again')
    native=await planner.client.manage_household_appointment('prepare',{'selection':selection,'operation':operation,'patch':patch,'version':source['version']})
    if native['state']=='unchanged':
        # A person/category-only correction belongs to the household catalogue.
        if operation=='update' and (after['members']!=planner.assign(before)['members'] or after['category']!=planner.assign(before)['category']):
            native={'state':'catalogue','token':None,'before':before,'after':before,'recurring':bool(before.get('recurrence_id'))}
        else:return native
    token=__import__('secrets').token_hex(20)
    envelope={'action':'calendar_change','revision':revision,'selection':selection,'native_token':native['token'],
        'operation':operation,'draft':after,'before':before,'source_version':source['version'],
        'catalogue_only':native.get('state')=='catalogue','overlaps':overlaps,'source_failures':failures}
    with planner.db:planner.db.execute('INSERT INTO intents VALUES (?,?,?,?,?,?)',(token,owner,planner.clock()+300,token,json.dumps(envelope),'prepared'))
    return {'state':'review_change','token':token,'before':before,'after':native['after'],'members':after['members'] if after else [],'category':after['category'] if after else '',
            'operation':operation,'recurring':native['recurring'],'overlaps':overlaps,'source_failures':failures}

async def confirm(planner,token,envelope):
    if envelope['operation']=='update':
        draft=envelope['draft'];a=datetime.fromisoformat(draft['start']);b=datetime.fromisoformat(draft['end'])
        if draft['all_day']:a=a.replace(tzinfo=ZONE);b=b.replace(tzinfo=ZONE)
        rows=await planner.read(a,b);before=envelope['before']
        rows=[e for e in rows if not (e.get('uid')==before['uid'] and e.get('recurrence_id')==before.get('recurrence_id'))]
        duplicates,overlaps=planner.compare(draft,rows);other,failures=await planner.other_overlaps(draft);overlaps+=other
        if duplicates or overlaps!=envelope['overlaps'] or failures!=envelope['source_failures']:raise ValueError('Calendar conflicts changed; review the appointment again')
    planner.guard(write=True)
    if envelope['revision']!=planner.profile._data['revision']:raise ValueError('Household details changed; review again')
    with planner.db:planner.db.execute("UPDATE intents SET state='sending' WHERE token=?",(token,))
    try:
        if envelope.get('catalogue_only'):
            fresh=await planner.client.manage_household_appointment('inspect',{'selection':envelope['selection']})
            if fresh['version']!=envelope['source_version']:raise ValueError('The source changed; review again')
            result={'state':'confirmed','operation':'update','event':fresh['event'],'message':'Updated the household member/category assignment. The phone calendar entry is unchanged.'}
        else:result=await planner.client.manage_household_appointment('commit',{'token':envelope['native_token']})
    except Exception:result={'state':'uncertain','message':'The calendar outcome is uncertain. Check it before retrying; no automatic retry will occur.'}
    state='confirmed' if result['state']=='confirmed' else 'uncertain'
    with planner.db:
        if state=='confirmed' and envelope['operation']=='update':
            event=result['event'];record={'members':envelope['draft']['members'],'category':envelope['draft']['category'],'_content':content_fingerprint(event)}
            for key in (uid_identity(event) or identity(event),):
                if key:planner.db.execute('INSERT INTO assignments VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',(key,json.dumps(record)))
        planner.db.execute('UPDATE intents SET state=? WHERE token=?',(state,token))
    return result

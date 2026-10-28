"""Version-checked, journalled edits to one calendar event or occurrence.

Shared with the HA adapter. Source implements resolve/get/write/refresh; models
never receive this object or a receipt token. Failed writes are not retried.
"""
import asyncio
from datetime import date,datetime,timedelta,timezone
import hashlib,json,secrets,sqlite3,time
from pathlib import Path
from zoneinfo import ZoneInfo
ZONE=ZoneInfo('Europe/Oslo')
class VersionConflict(ValueError):
    """The provider rejected a stale If-Match without changing the event."""

def moment(value):
    if not isinstance(value,dict) or set(value)-{'date','dateTime','timeZone'}:raise ValueError('Invalid calendar time')
    if bool(value.get('date'))==bool(value.get('dateTime')):raise ValueError('Choose a date or a timed event')
    if value.get('date'):return date.fromisoformat(value['date'])
    parsed=datetime.fromisoformat(value['dateTime'].replace('Z','+00:00'))
    if parsed.tzinfo is None:raise ValueError('A calendar time needs its timezone')
    if value.get('timeZone'):ZoneInfo(value['timeZone'])
    return parsed.astimezone(timezone.utc)

def snapshot(raw):
    a,b=moment(raw['start']),moment(raw['end'])
    return {'summary':raw.get('summary') or '','start':a.isoformat(),'end':b.isoformat(),
        'all_day':not isinstance(a,datetime),'description':raw.get('description') or '',
        'location':raw.get('location') or '','uid':raw.get('iCalUID',''),
        'recurrence_id':raw['id'] if raw.get('recurringEventId') else None,
        'status':raw.get('status','confirmed')}

def clean_patch(patch,before,now):
    if not isinstance(patch,dict) or not patch or set(patch)-{'summary','location','description','start','end'}:raise ValueError('Unsupported appointment changes')
    for field,limit in (('summary',160),('location',180),('description',4000)):
        if field in patch and (not isinstance(patch[field],str) or len(patch[field])>limit or any(ord(c)<32 and c not in '\n\t' for c in patch[field])):raise ValueError('Invalid appointment text')
    if 'summary' in patch and not patch['summary'].strip():raise ValueError('The appointment needs a title')
    if ('start' in patch)!=('end' in patch):raise ValueError('Review both start and end together')
    after={**before,**patch};a,b=moment(after['start']),moment(after['end'])
    if isinstance(a,datetime)!=isinstance(b,datetime):raise ValueError('Start and end must use the same date type')
    if b<=a:raise ValueError('The end must be after the start')
    day=a.astimezone(ZONE).date() if isinstance(a,datetime) else a
    if not now.astimezone(ZONE).date()<=day<=now.astimezone(ZONE).date()+timedelta(days=366):raise ValueError('Choose a future date within one year')
    if isinstance(a,datetime) and a<=now.astimezone(timezone.utc):raise ValueError('That start time has already passed')
    if (b-a).total_seconds()>14*86400:raise ValueError('Choose an appointment within fourteen days')
    same_times=moment(after['start'])==moment(before['start']) and moment(after['end'])==moment(before['end'])
    return {k:v for k,v in patch.items() if v!=before.get(k,'') and not (same_times and k in ('start','end'))}

class MutationStore:
    def __init__(self,source,path=None,*,clock=time.time,now=None):
        self.source,self.clock=source,clock;self.now=now or (lambda:datetime.now(ZONE));self.lock=asyncio.Lock()
        self.db=sqlite3.connect(str(path) if path else ':memory:')
        if path:Path(path).chmod(0o600)
        self.db.execute('CREATE TABLE IF NOT EXISTS receipts (token TEXT PRIMARY KEY,owner TEXT NOT NULL,expires REAL NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL,result TEXT)')
        # A process crash after dispatch is not evidence the write failed.
        self.db.execute("UPDATE receipts SET state='uncertain' WHERE state='sending'");self.db.commit()

    async def inspect(self,selection):
        ref,raw=await self.source.resolve(selection)
        if not raw.get('id') or raw.get('id')!=ref['id'] or not raw.get('etag'):raise ValueError('Calendar event has no stable version')
        if raw.get('status')=='cancelled':raise ValueError('That calendar entry has already been removed')
        return {'event':snapshot(raw),'version':raw['etag'],'reference':ref,
                'recurring':bool(raw.get('recurringEventId'))}

    async def prepare(self,owner,selection,operation,patch,version):
        if operation not in ('update','cancel'):raise ValueError('Unsupported calendar operation')
        ref,raw=await self.source.resolve(selection)
        if not raw.get('etag') or raw['etag']!=version:raise ValueError('The appointment changed on the calendar. Please review it again.')
        if raw.get('attendees'):raise ValueError('This appointment has invited guests. Please change it in your phone calendar so invitations can be handled there.')
        if raw.get('eventType','default')!='default' or raw.get('locked'):raise ValueError('This calendar entry needs to be edited in the phone calendar')
        if raw.get('recurrence') and not raw.get('recurringEventId'):raise ValueError('Select one occurrence; the whole repeating series will not be changed here')
        if raw.get('status')=='cancelled':raise ValueError('That calendar entry has already been removed')
        changes=clean_patch(patch,raw,self.now()) if operation=='update' else {}
        if operation=='cancel' and patch:raise ValueError('Cancellation cannot contain other changes')
        if operation=='update' and not changes:return {'state':'unchanged','message':'That appointment already has those details.'}
        # Source dates are checked for cancellation too; no past-event cleanup.
        if operation=='cancel':clean_patch({'summary':raw.get('summary','Appointment')},raw,self.now())
        token=secrets.token_hex(20)
        payload={'selection':selection,'reference':ref,'operation':operation,'patch':changes,
            'version':version,'before':snapshot(raw),'after':snapshot({**raw,**changes}),
            'recurring':bool(raw.get('recurringEventId'))}
        with self.db:
            self.db.execute("DELETE FROM receipts WHERE expires<? AND state IN ('prepared','confirmed','cancelled')",(self.clock()-30*86400,))
            if self.db.execute("SELECT count(*) FROM receipts WHERE state='prepared' AND expires>?",(self.clock(),)).fetchone()[0]>=500:raise ValueError('Too many open calendar reviews')
            self.db.execute('INSERT INTO receipts VALUES (?,?,?,?,?,NULL)',(token,owner,self.clock()+300,'prepared',json.dumps(payload)))
        return {'state':'review','token':token,**{k:payload[k] for k in ('before','after','recurring','operation')}}

    async def commit(self,owner,token):
        async with self.lock:
            row=self.db.execute('SELECT owner,expires,state,payload,result FROM receipts WHERE token=?',(token,)).fetchone()
            if not row or row[0]!=owner:raise ValueError('This calendar review belongs to another caller')
            if row[2]=='confirmed':return json.loads(row[4])
            if row[2]!='prepared':return {'state':'uncertain','message':'That calendar operation may already have been sent. Check the calendar; it will not be retried.'}
            if row[1]<self.clock():raise ValueError('This calendar review expired')
            data=json.loads(row[3]);ref,raw=await self.source.resolve(data['selection'])
            if ref!=data['reference'] or raw.get('etag')!=data['version'] or snapshot(raw)!=data['before']:
                raise ValueError('The appointment changed since review. Please review it again.')
            if raw.get('attendees'):raise ValueError('Invitations changed; use the phone calendar')
            with self.db:self.db.execute("UPDATE receipts SET state='sending' WHERE token=?",(token,))
            try:
                # The source must use If-Match on the exact reviewed Google event.
                await self.source.write(ref,data['operation'],data['patch'],data['version'])
                actual=await self.source.get(ref)
                verified=(actual is None or actual.get('status')=='cancelled') if data['operation']=='cancel' else actual is not None and snapshot(actual)==data['after']
                if not verified:raise ValueError('Calendar result is not confirmed')
            except VersionConflict:
                with self.db:self.db.execute("UPDATE receipts SET state='conflict' WHERE token=?",(token,))
                return {'state':'review_required','message':'A newer calendar edit was detected. Nothing was overwritten; please review the appointment again.'}
            except Exception:
                with self.db:self.db.execute("UPDATE receipts SET state='uncertain' WHERE token=?",(token,))
                return {'state':'uncertain','message':'The calendar outcome is uncertain. Check it before doing anything further; no automatic retry will occur.'}
            try:await self.source.refresh();refresh=True
            except Exception:refresh=False
            result={'state':'confirmed','operation':data['operation'],'event':data['after'],
                'recurring':data['recurring'],'ha_refreshed':refresh,
                'message':'Removed that calendar entry.' if data['operation']=='cancel' else 'Updated that calendar appointment.'}
            with self.db:self.db.execute("UPDATE receipts SET state='confirmed',result=? WHERE token=?",(json.dumps(result),token))
            return result

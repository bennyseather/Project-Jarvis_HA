"""Manchester United public facts and explicitly enabled silent written updates.

Fixed public endpoints only. Provider results are data, never tool instructions.
No match or notification is inferred from model output. Durable IDs deduplicate
restarts and uncertain deliveries; polling and source gaps are shown honestly.
"""
import asyncio,json,re,urllib.request,xml.etree.ElementTree as ET
from datetime import datetime,timedelta,timezone
from email.utils import parsedate_to_datetime
from pathlib import Path
from zoneinfo import ZoneInfo
from jarvis.companion_store import bounded,instruction_attempt,secret
ZONE=ZoneInfo('Europe/Oslo')
TEAM='360'
ROOT='https://site.api.espn.com/apis/site/v2/sports/soccer/eng.1/teams/360/schedule'
URLS={'fixtures':ROOT+'?fixture=true&league=all','results':ROOT+'?league=all',
      'standings':'https://site.api.espn.com/apis/v2/sports/soccer/eng.1/standings',
      'news':'https://feeds.bbci.co.uk/sport/football/teams/manchester-united/rss.xml'}
PUBLIC={'fixtures':'https://www.espn.com/soccer/team/fixtures/_/id/360/manchester-united',
        'results':'https://www.espn.com/soccer/team/results/_/id/360/manchester-united',
        'standings':'https://www.espn.com/soccer/table/_/league/eng.1',
        'news':'https://www.bbc.com/sport/football/teams/manchester-united'}
FINAL={'STATUS_FULL_TIME','STATUS_FINAL','STATUS_FINAL_AET','STATUS_FINAL_PEN','STATUS_FULL_TIME_AET','STATUS_FULL_TIME_PEN'}
def moment(value):
 d=datetime.fromisoformat(value.replace('Z','+00:00'))
 if d.tzinfo is None:raise ValueError('Source time has no timezone')
 return d

def clean(value,limit=220):
 if not isinstance(value,str) or not value or len(value)>limit or '<' in value or secret(value) or instruction_attempt(value):raise ValueError('Unsafe public source text')
 return value

class NoRedirect(urllib.request.HTTPRedirectHandler):
 def redirect_request(self,*args,**kwargs):raise ValueError('Unexpected public-feed redirect')
def fetch(kind):
 req=urllib.request.Request(URLS[kind],headers={'User-Agent':'Jarvis-household/1.0','Accept':'application/json, application/rss+xml'})
 with urllib.request.build_opener(NoRedirect).open(req,timeout=12) as r:
  data=r.read(2000001)
  if len(data)>2000000:raise ValueError('Unbounded public feed')
 return ET.fromstring(data) if kind=='news' else json.loads(data)

def matches(data,now):
 if data.get('status')!='success' or data.get('team',{}).get('id')!=TEAM or data['team'].get('displayName')!='Manchester United':raise ValueError('Wrong football team')
 season=now.year if now.month>=7 else now.year-1
 if data.get('season',{}).get('year')!=season:raise ValueError('Wrong football season')
 out=[]
 for e in data.get('events',[])[:150]:
  c=e.get('competitions',[])
  if len(c)!=1:continue
  c=c[0];sides=c.get('competitors',[])
  if len(sides)!=2 or sum(v.get('team',{}).get('id')==TEAM for v in sides)!=1:continue
  a=next((v for v in sides if v.get('homeAway')=='home'),None);b=next((v for v in sides if v.get('homeAway')=='away'),None)
  if not a or not b:continue
  day=moment(e['date']);status=c.get('status',{}).get('type',{});name=status.get('name','')
  if not re.fullmatch(r'\d{1,15}',str(e.get('id',''))):continue
  score=[]
  for v in (a,b):
   raw=v.get('score',{});n=raw.get('displayValue') if isinstance(raw,dict) else str(raw) if raw is not None else ''
   score.append(n if re.fullmatch(r'\d{1,2}',n or '') else None)
  final=bool(status.get('completed') is True and status.get('state')=='post' and name in FINAL and all(v is not None for v in score) and day<=now)
  out.append({'id':str(e['id']),'date':day.isoformat(),'home':clean(a['team']['displayName'],100),'away':clean(b['team']['displayName'],100),
   'competition':clean(e.get('league',{}).get('name','Competition unspecified'),100),'state':status.get('state','unknown'),'status':clean(status.get('description','Status unknown'),100),
   'final':final,'score':score if final else None,'time_confirmed':e.get('timeValid') is True and c.get('timeValid') is True,
   'url':'https://www.espn.com/soccer/match/_/gameId/'+str(e['id'])})
 return sorted(out,key=lambda e:e['date'])

def table(data,now):
 season=now.year if now.month>=7 else now.year-1
 rows=[]
 for child in data.get('children',[]):
  tab=child.get('standings',{})
  if tab.get('season')!=season:continue
  for e in tab.get('entries',[]):
   stats={s['name']:s.get('displayValue') for s in e.get('stats',[])}
   if all(re.fullmatch(r'[+-]?\d{1,3}',stats.get(f) or '') for f in ('rank','points','gamesPlayed','wins','ties','losses','pointDifferential')):
    rows.append({'team':clean(e['team']['displayName'],100),'id':str(e['team']['id']),**{f:int(stats[f]) for f in ('rank','points','gamesPlayed','wins','ties','losses','pointDifferential')}})
 if len(rows)!=20 or len({r['id'] for r in rows})!=20 or not any(r['id']==TEAM for r in rows):raise ValueError('Incomplete or wrong league table')
 return sorted(rows,key=lambda r:r['rank'])

def headlines(root,now):
 rows=[]
 for i in root.findall('.//item')[:100]:
  try:
   title=clean(i.findtext('title'));url=i.findtext('link') or '';date=parsedate_to_datetime(i.findtext('pubDate'))
   if not re.search(r'\b(?:manchester united|man[ .-]*utd|man[ .-]+united|red devils)\b',title,re.I):continue
   if re.search(r'\bwomen|\bu-?\d{2}\b|\byouth\b',title,re.I):continue
   if not url.startswith(('https://www.bbc.co.uk/','https://www.bbc.com/')) or not now-timedelta(days=7)<=date<=now+timedelta(minutes=5):continue
   rows.append({'title':title,'url':url.split('?')[0],'date':date.isoformat(),'basis':'BBC headline; article not independently verified'})
  except (ValueError,TypeError):continue
 return rows[:5]

class FootballUpdates:
 def __init__(self,owner,*,fetcher=fetch):
  self.owner=owner;self.fetcher=fetcher;self.task=None;self.lock=asyncio.Lock();self.last_poll=-10000.;self.cache={};self.errors=[]
  self.path=owner.profile._source_path.with_name('football_updates.json') if getattr(owner.profile,'_source_path',None) else None
  self.config={}
  if self.path and self.path.exists():
   d=json.loads(self.path.read_text(encoding='utf-8'))
   fields={'schema_version','enabled','person','team','daily_time','timezone','final_scores','delivery','activated_at','approval_source'}
   if set(d)!=fields or d['schema_version']!=1 or type(d['enabled']) is not bool or type(d['final_scores']) is not bool or d['person']!='benny' or d['team']!=TEAM or d['daily_time']!='08:00' or d['timezone']!='Europe/Oslo' or d['delivery']!='ha_written' or not d['approval_source']:raise ValueError('Invalid football update approval')
   moment(d['activated_at']);self.config=d
 def enabled(self):return bool(self.config.get('enabled') and self.owner.policy.data['enabled'])
 def state(self):
  row=self.owner.store.db.execute('SELECT value FROM assistant_state WHERE key=?',('football_updates_v1',)).fetchone()
  return json.loads(row[0]) if row else {'seen':{},'daily':None,'briefs':[]}
 def save(self,value):
  with self.owner.store.db:self.owner.store.db.execute('INSERT INTO assistant_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('football_updates_v1',json.dumps(value,ensure_ascii=False)))
 def start(self):
  if self.task is None:self.task=asyncio.create_task(self.run())
 async def close(self):
  if self.task:self.task.cancel();await asyncio.gather(self.task,return_exceptions=True)
 async def run(self):
  while True:
   await asyncio.sleep(30)
   if not self.enabled() or self.owner.foreground:continue
   try:await self.tick()
   except asyncio.CancelledError:raise
   except Exception:self.errors=['Written football updates need another check.']
 async def refresh(self,*,force=False):
  async with self.lock:
   if not force and self.owner.clock()-self.last_poll<120:return
   self.last_poll=self.owner.clock();now=self.owner.now();errors=[]
   async def one(kind):
    try:
     data=await asyncio.wait_for(asyncio.to_thread(self.fetcher,kind),15)
     value=matches(data,now) if kind in ('fixtures','results') else table(data,now) if kind=='standings' else headlines(data,now)
     self.cache[kind]={'checked_at':now.isoformat(),'data':value}
    except asyncio.CancelledError:raise
    except Exception:errors.append(kind+' source unavailable; previous data is withheld.')
   await asyncio.gather(*(one(k) for k in URLS));self.errors=errors
 def current(self,kind):
  row=self.cache.get(kind)
  return row['data'] if row and (self.owner.now()-moment(row['checked_at'])).total_seconds()<=600 and not any(e.startswith(kind+' ') for e in self.errors) else None
 def brief(self,topic='brief'):
  now=self.owner.now();lines=[];sources=[]
  fixtures=self.current('fixtures');results=self.current('results');rank=self.current('standings');news=self.current('news')
  if topic in ('brief','fixtures') and fixtures is not None:
   upcoming=[e for e in fixtures if moment(e['date'])>=now-timedelta(hours=4) and not e['final']]
   if not upcoming:lines.append('No upcoming match was returned by the fixture source; this is not proof that no match is scheduled.')
   for e in upcoming[:3]:
    at=moment(e['date']).astimezone(ZONE);timing=at.strftime('%A %d %B at %H:%M %Z') if e['time_confirmed'] else at.strftime('%A %d %B')+' (kick-off time unconfirmed)'
    lines.append(e['home']+' host '+e['away']+' on '+timing+' in the '+e['competition']+'. Status: '+e['status']+'.')
   sources.append({'title':'ESPN fixtures','url':PUBLIC['fixtures']})
  if topic in ('brief','results') and results is not None:
   done=[e for e in results if e['final']]
   for e in done[-(1 if topic=='brief' else 3):][::-1]:
    lines.append('Final: '+e['home']+' '+e['score'][0]+'–'+e['score'][1]+' '+e['away']+' ('+moment(e['date']).astimezone(ZONE).strftime('%d %B')+', '+e['competition']+').')
   sources.append({'title':'ESPN results','url':PUBLIC['results']})
  if topic in ('brief','standings') and rank is not None:
   united=next(r for r in rank if r['id']==TEAM);lines.append('United are '+str(united['rank'])+' in the Premier League with '+str(united['points'])+' points from '+str(united['gamesPlayed'])+' matches ('+str(united['wins'])+' wins, '+str(united['ties'])+' draws, '+str(united['losses'])+' losses).')
   if topic=='standings':lines.extend(str(r['rank'])+'. '+r['team']+' — '+str(r['points'])+' pts' for r in rank)
   sources.append({'title':'ESPN league table','url':PUBLIC['standings']})
  if topic in ('brief','news') and news is not None:
   if news:lines.append('BBC headlines: '+'; '.join('“'+n['title']+'”' for n in news[:3])+'. These are attributed headlines, including any speculation.')
   else:lines.append('No recent relevant men’s first-team headline was returned.')
   sources.extend({'title':n['title'],'url':n['url']} for n in news[:3])
  lines.extend(self.errors)
  return {'title':'Manchester United · '+now.astimezone(ZONE).strftime('%d %B'),'lines':lines or ['I could not verify current football information.'],'sources':sources,'checked_at':now.isoformat()}
 async def notify(self,key,title,message):
  client=self.owner.container.home_assistant
  task=await asyncio.wait_for(client.dispatch_service('persistent_notification','create',{'notification_id':key,'title':title,'message':message}),10)
  await asyncio.wait_for(task,15)
 async def tick(self):
  if not self.enabled():return
  # Two-minute polling on match days; fifteen minutes otherwise. Sources are
  # fetched only on the home server, never through the development computer.
  today=self.owner.now().astimezone(ZONE).date().isoformat();known=self.cache.get('fixtures',{}).get('data',[])
  matchday=any(moment(e['date']).astimezone(ZONE).date().isoformat()==today for e in known)
  interval=120 if matchday else 900
  daily_due=self.owner.now().astimezone(ZONE).hour>=8 and self.state()['daily']!=today
  if self.owner.clock()-self.last_poll<interval and not daily_due:return
  await self.refresh(force=daily_due);s=self.state();now=self.owner.now();today=now.astimezone(ZONE).date().isoformat();activated=moment(self.config['activated_at']);changed=False
  finals=[e for e in self.current('results') or [] if e['final']]
  for e in finals:
   fingerprint=':'.join(e['score']);old=s['seen'].get(e['id']);started=moment(e['date'])
   if old==fingerprint:continue
   # Do not replay historical matches on first enable/restart after an outage.
   if s.get('seeded') and self.config['final_scores'] and started>=activated-timedelta(hours=4) and now-started<timedelta(hours=12):
    title='Manchester United · '+('corrected final score' if old else 'final score')
    message=e['home']+' '+e['score'][0]+'–'+e['score'][1]+' '+e['away']+' · '+e['competition']+'. [ESPN match report]('+e['url']+')'
    await self.notify('jarvis_mu_final_'+e['id'],title,message)
    s['briefs']=[{'title':title,'lines':[message],'sources':[{'title':'ESPN match','url':e['url']}],'checked_at':now.isoformat()}]+s['briefs'][:9]
   s['seen'][e['id']]=fingerprint;changed=True
   if len(s['seen'])>300:s['seen'].pop(next(iter(s['seen'])))
   self.save(s) # keep successful deliveries if a later one fails
  if self.current('results') is not None and not s.get('seeded'):s['seeded']=True;changed=True
  if now.astimezone(ZONE).hour>=8 and s['daily']!=today:
   b=self.brief();message='\n\n'.join(b['lines'])+'\n\n'+' · '.join('['+v['title']+']('+v['url']+')' for v in b['sources'])
   await self.notify('jarvis_mu_daily',b['title'],message)
   s['daily']=today;s['briefs']=[b]+s['briefs'][:9];changed=True
  if changed:self.save(s)
 async def read(self,text):
  from jarvis.companion_memory import local_json
  schema={'type':'object','properties':{'topic':{'type':'string','enum':['brief','fixtures','results','standings','news']}},'required':['topic'],'additionalProperties':False}
  data=await local_json(self.owner.provider,'Select the topic of this Manchester United men first-team question: fixtures for upcoming matches,results for scores,standings for league table,news for news,brief for overall update. JSON only; no facts or actions.',{'latest':bounded(text,700)},schema,tokens=40)
  if data.get('topic') not in schema['properties']['topic']['enum']:raise ValueError('Unknown football topic')
  await self.refresh();b=self.brief(data['topic']);return {'provider':'companion','status':'success' if b['sources'] else 'unavailable','message':' '.join(b['lines']),'sources':b['sources'],'cacheable':False,'football_checked_at':b['checked_at']}
 def project(self):
  s=self.state();return {'enabled':self.enabled(),'team':'Manchester United men’s first team','daily_time':'08:00 Europe/Oslo','delivery':'Written HA notifications and Assistant page; no spoken alerts','final_scores':bool(self.config.get('final_scores')),'polling':'About two minutes on known match days; fifteen minutes otherwise, while services and sources are available.','issues':list(self.errors),'briefs':s['briefs'][:10]}

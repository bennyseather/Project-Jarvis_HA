"""Durable, source-attributed assistant learning and read-only preparation work.

Adds isolated tables to Jarvis's existing SQLite file. No automatic memory expiry
or eviction; validity and retrieval are separate from retention. No transcripts,
credentials, executable instructions or model-granted permissions are stored.
"""
from datetime import datetime,timezone
import hashlib,json,re,secrets,sqlite3
from pathlib import Path

SECRET=re.compile(r'(?i)(?:\b(?:password|passcode|api[ _-]?key|access[ _-]?token|secret[ _-]?key)\s*(?:is|=|:)\s*\S+|sk-[a-zA-Z0-9_-]{16,}|-----BEGIN [A-Z ]*PRIVATE KEY-----|https?://[^/\s]+:[^/\s]+@)')
def secret(text):return bool(SECRET.search(str(text)) or re.search(r'\b(?:password|passcode|api[ _-]?key|access[ _-]?token|private[ _-]?key|login credentials|pin code)\b',str(text),re.I))
def instruction_attempt(text):return bool(re.search(r'\b(?:ignore|bypass|override|disable)\b.{0,60}\b(?:instructions|permissions|rules|confirmation|safety|security)\b|\bsystem prompt\b',str(text),re.I))
def stamp(value=None):return (value or datetime.now(timezone.utc)).astimezone(timezone.utc).isoformat()
def digest(value):return hashlib.sha256(json.dumps(value,sort_keys=True,ensure_ascii=False).encode()).hexdigest()
def bounded(value,n):
    if not isinstance(value,str) or len(value)>n or any(ord(c)<32 and c not in '\n\t' for c in value):raise ValueError('Invalid assistant text')
    return value.strip()

class CompanionStore:
    def __init__(self,path=None,*,now=None):
        self.now=now or (lambda:datetime.now(timezone.utc));self.path=Path(path) if path else None
        self.db=sqlite3.connect(str(path) if path else ':memory:')
        if self.path:self.path.chmod(0o600)
        self.db.executescript("""
        CREATE TABLE IF NOT EXISTS assistant_state (key TEXT PRIMARY KEY,value TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_memories (id TEXT PRIMARY KEY,fingerprint TEXT UNIQUE NOT NULL,created_at TEXT NOT NULL,updated_at TEXT NOT NULL,status TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_capture_jobs (id TEXT PRIMARY KEY,created_at TEXT NOT NULL,state TEXT NOT NULL,generation INTEGER NOT NULL,attempts INTEGER NOT NULL,next_at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_processed (id TEXT PRIMARY KEY,created_at TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_briefs (id TEXT PRIMARY KEY,input_hash TEXT NOT NULL,status TEXT NOT NULL,updated_at TEXT NOT NULL,payload TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS assistant_improvements (id TEXT PRIMARY KEY,updated_at TEXT NOT NULL,state TEXT NOT NULL,payload TEXT NOT NULL);
        INSERT OR IGNORE INTO assistant_state VALUES ('generation','0');
        UPDATE assistant_capture_jobs SET state='queued' WHERE state='processing';
        """);self.db.commit()
    def close(self):self.db.close()
    @property
    def generation(self):return int(self.db.execute("SELECT value FROM assistant_state WHERE key='generation'").fetchone()[0])
    def enqueue(self,text,context):
        text=bounded(text,1200)
        if not text or secret(text) or instruction_attempt(text):return None
        if not isinstance(context,dict) or len(json.dumps(context))>3500:raise ValueError('Invalid learning context')
        source={**context,'text':text};key=digest([text,context.get('conversation'),context.get('actor'),context.get('anchor'),context.get('correct_memory'),context.get('clarified_subjects'),context.get('preference_subjects'),self.generation])
        if self.db.execute('SELECT 1 FROM assistant_processed WHERE id=?',(key,)).fetchone():return None
        if self.db.execute("SELECT count(*) FROM assistant_capture_jobs").fetchone()[0]>=500:raise ValueError('The learning queue needs attention')
        now=stamp(self.now())
        with self.db:self.db.execute('INSERT OR IGNORE INTO assistant_capture_jobs VALUES (?,?,?,?,?,?,?)',(key,now,'queued',self.generation,0,now,json.dumps(source,ensure_ascii=False)))
        return key
    def next_job(self,key=None):
        row=self.db.execute("SELECT id,generation,attempts,payload FROM assistant_capture_jobs WHERE state='queued' AND next_at<=? AND (? IS NULL OR id=?) ORDER BY created_at LIMIT 1",(stamp(self.now()),key,key)).fetchone()
        if row is None:return None
        key,generation,attempts,payload=row
        with self.db:self.db.execute("UPDATE assistant_capture_jobs SET state='processing',attempts=attempts+1 WHERE id=?",(key,))
        return {'id':key,'generation':generation,'attempts':attempts+1,'source':json.loads(payload)}
    def retry(self,job,delay_seconds=30):
        from datetime import timedelta
        state='failed' if job['attempts']>=3 else 'queued'
        with self.db:self.db.execute("UPDATE assistant_capture_jobs SET state=?,next_at=? WHERE id=? AND generation=?",(state,stamp(self.now()+timedelta(seconds=delay_seconds)),job['id'],job['generation']))
    def finish(self,job,records):
        current=self.db.execute('SELECT generation,state FROM assistant_capture_jobs WHERE id=?',(job['id'],)).fetchone()
        if current is None or current!=(job['generation'],'processing') or self.generation!=job['generation']:return []
        if not isinstance(records,list) or len(records)>3:raise ValueError('Unbounded learned records')
        result=[];source=job['source'];now=stamp(self.now())
        with self.db:
            for record in records:
                quote=bounded(record.get('quote'),600)
                if not quote or quote not in source['text'] or secret(quote) or instruction_attempt(quote):raise ValueError('Learning must quote the user')
                if record.get('kind') not in ('fact','preference','plan','hint','improvement'):raise ValueError('Invalid learned kind')
                if record['kind']=='improvement':
                    key='D'+digest([quote])[:10]
                    self.db.execute('INSERT INTO assistant_improvements VALUES (?,?,?,?) ON CONFLICT(id) DO UPDATE SET updated_at=excluded.updated_at',(key,now,'proposed',json.dumps({'quote':quote,'proposal':bounded(record.get('interpretation',''),900),'source':'Conversation observation; no code has been executed','autonomous_execution':False},ensure_ascii=False)))
                    continue
                if self.db.execute('SELECT count(*) FROM assistant_memories').fetchone()[0]>=5000:raise ValueError('The retained-memory index needs review; nothing was evicted')
                payload={**record,'quote':quote,'source':{'kind':'direct_user_statement','conversation':source.get('conversation'),'actor':source.get('actor'),'speaker':source.get('speaker'),'anchor':source.get('anchor'),'recorded_at':now,'clarified_subjects':source.get('clarified_subjects',[]),'clarification_quote':source.get('clarification_quote','')}}
                key=digest([record['kind'],record.get('subjects',[]),quote,source.get('anchor') if record['kind']=='plan' else ''])
                prior=self.db.execute('SELECT id FROM assistant_memories WHERE fingerprint=?',(key,)).fetchone()
                identifier=prior[0] if prior else 'M'+secrets.token_hex(4)
                correction=source.get('correct_memory')
                if correction:
                    if len(records)!=1 or not self.db.execute('SELECT 1 FROM assistant_memories WHERE id=?',(correction,)).fetchone():raise ValueError('Memory correction no longer matches')
                    if prior and prior[0]!=correction:raise ValueError('That correction already exists as another memory')
                    identifier=correction
                    self.db.execute('UPDATE assistant_memories SET fingerprint=?,updated_at=?,status=?,payload=? WHERE id=?',(key,now,'reported',json.dumps(payload,ensure_ascii=False),identifier))
                else:
                    old_id=record.get('supersedes')
                    if old_id:
                        old=next((m for m in self.memories() if m['id']==old_id),None)
                        if not source.get('explicit_correction') or old is None or old['subjects']!=record.get('subjects',[]) or old['kind']!=record['kind'] or record['kind']=='hint':raise ValueError('Unsupported memory supersession')
                        self.db.execute("UPDATE assistant_memories SET status='superseded' WHERE id=?",(old_id,))
                    self.db.execute('INSERT INTO assistant_memories VALUES (?,?,?,?,?,?) ON CONFLICT(fingerprint) DO UPDATE SET updated_at=excluded.updated_at',(identifier,key,now,now,'inferred' if record['kind']=='hint' else 'reported',json.dumps(payload,ensure_ascii=False)))
                result.append(identifier)
            self.db.execute('INSERT OR IGNORE INTO assistant_processed VALUES (?,?)',(job['id'],now))
            self.db.execute('DELETE FROM assistant_capture_jobs WHERE id=?',(job['id'],))
        return result
    def memories(self,*,include_historical=False):
        rows=self.db.execute('SELECT id,created_at,updated_at,status,payload FROM assistant_memories ORDER BY updated_at DESC,id').fetchall();out=[];now=self.now()
        for key,created,updated,status,raw in rows:
            item=json.loads(raw);valid_until=item.get('valid_until');valid_from=item.get('valid_from')
            current=status not in ('superseded','retracted') and not item.get('date_unresolved',False)
            if valid_until and datetime.fromisoformat(valid_until)<=now:current=False
            timing='upcoming' if current and valid_from and datetime.fromisoformat(valid_from)>now else 'current' if current else 'historical_or_unresolved'
            if include_historical or current:out.append({**item,'id':key,'created_at':created,'updated_at':updated,'status':status,'currently_applicable':current,'temporal_state':timing})
        return out
    def relevant(self,text,subjects=(),maximum=8):
        terms={w for w in re.findall(r'\w+',text.casefold()) if len(w)>2}-{'what','when','where','about','remember','please','that','this','does','have','with','from','would','should'}
        ranked=[]
        for index,item in enumerate(self.memories()):
            owners=set(item.get('subjects',[]))
            if subjects and owners and not owners.intersection(subjects):continue
            if subjects and not owners and re.search(r'\b(i|my|mine|me)\b',item['quote'],re.I):continue
            tokens=set(re.findall(r'\w+',(' '.join(item.get('tags',[]))+' '+item['quote']+' '+item.get('interpretation','')).casefold()))
            score=len(terms.intersection(tokens))+(5 if owners.intersection(subjects) else 0)
            if score:ranked.append((score,-index,item))
        ranked.sort(key=lambda row:(row[0],row[1]),reverse=True)
        return [row[2] for row in ranked[:maximum]]
    def forget(self,ids=None):
        records=self.memories(include_historical=True);selected=[m for m in records if ids is None or m['id'] in ids]
        if not selected and ids is not None:return 0
        quotes=[m['quote'] for m in selected]
        with self.db:
            for row in selected:self.db.execute('DELETE FROM assistant_memories WHERE id=?',(row['id'],))
            generation=self.generation+1;self.db.execute("UPDATE assistant_state SET value=? WHERE key='generation'",(str(generation),))
            for key,raw in self.db.execute('SELECT id,payload FROM assistant_capture_jobs').fetchall():
                source=json.loads(raw)
                if ids is None or any(q in source['text'] for q in quotes) or source.get('correct_memory') in {m['id'] for m in selected}:
                    self.db.execute('DELETE FROM assistant_capture_jobs WHERE id=?',(key,))
                else:self.db.execute("UPDATE assistant_capture_jobs SET generation=?,state='queued' WHERE id=?",(generation,key))
            if ids is None:self.db.execute('DELETE FROM assistant_processed')
        return len(selected)
    def job_counts(self):return dict(self.db.execute('SELECT state,count(*) FROM assistant_capture_jobs GROUP BY state').fetchall())
    def travel_input(self,key,source_hash):
        row=self.db.execute('SELECT value FROM assistant_state WHERE key=?',('travel_input:'+key,)).fetchone()
        value=json.loads(row[0]) if row else {}
        return value if value.get('source_hash')==source_hash else {}
    def save_travel_input(self,key,source_hash,value):
        payload={**value,'source_hash':source_hash,'recorded_at':stamp(self.now())}
        with self.db:self.db.execute('INSERT INTO assistant_state VALUES (?,?) ON CONFLICT(key) DO UPDATE SET value=excluded.value',('travel_input:'+key,json.dumps(payload,ensure_ascii=False)))
    def save_brief(self,key,input_hash,status,payload):
        if status not in ('ready','needs_input','error','withdrawn'):raise ValueError('Invalid brief state')
        payload={k:v for k,v in payload.items() if k not in ('id','input_hash','status','updated_at')}
        with self.db:self.db.execute('INSERT INTO assistant_briefs VALUES (?,?,?,?,?) ON CONFLICT(id) DO UPDATE SET input_hash=excluded.input_hash,status=excluded.status,updated_at=excluded.updated_at,payload=excluded.payload',(key,input_hash,status,stamp(self.now()),json.dumps(payload,ensure_ascii=False)))
    def briefs(self,include_withdrawn=False):
        return [{'id':key,'input_hash':fingerprint,'status':status,'updated_at':updated,**json.loads(raw)} for key,fingerprint,status,updated,raw in self.db.execute('SELECT * FROM assistant_briefs ORDER BY updated_at DESC').fetchall() if include_withdrawn or status!='withdrawn']
    def improvements(self):
        return [{'id':key,'updated_at':updated,'state':state,**json.loads(raw)} for key,updated,state,raw in self.db.execute('SELECT * FROM assistant_improvements ORDER BY updated_at DESC').fetchall()]

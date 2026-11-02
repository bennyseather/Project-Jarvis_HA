"""Bounded in-memory text processing timings, without prompts or identity data."""
import asyncio,math,time
import re
from collections import deque
from contextlib import asynccontextmanager

class RequestBusy(Exception):pass

def timing_question(text):
    value=' '.join(text.casefold().strip(' .?!').split())
    if re.search(r'\b(?:remember|save|prefer|huske|husk|foretrekker)\b',value):return False
    subject=bool(re.search(r'\b(?:you|your|jarvis|server|din|dine|du)\b',value) or re.fullmatch(r'(?:(?:show|show me|check|vis) )?(?:response times?|reply times?|svartid(?:en|er)?)',value))
    question=bool(re.match(r'^(?:how|what|show|check|hva|hvor|vis|(?:can|could) you)\b',value) or re.fullmatch(r'(?:response times?|reply times?|svartid(?:en|er)?)',value))
    return subject and question and bool(re.search(r'\b(?:response times?|reply times?|processing times?|svartid(?:en|er)?|latency)\b|\bhow (?:fast|long)\b.{0,35}\b(?:respond|reply|replies|requests?)\b',value))

def timing_answer(data):
    if not data['sample_count']:return 'I have not measured a completed text request since this restart yet.'
    n=lambda v:format(v,'.1f')
    return 'Across the last '+str(data['sample_count'])+' measured text requests, the median server processing time was '+n(data['median_seconds'])+' seconds and 95% took '+n(data['p95_seconds'])+' seconds or less. The latest took '+n(data['last_seconds'])+' seconds. These timings exclude microphone, speech generation and playback, and reset when Jarvis restarts.'

@asynccontextmanager
async def session_slot(lock,timeout=2):
    try:await asyncio.wait_for(lock.acquire(),timeout)
    except asyncio.TimeoutError as error:raise RequestBusy() from error
    try:yield
    finally:lock.release()

class RequestTiming:
    def __init__(self,clock=time.monotonic):self.clock=clock;self.samples=deque(maxlen=100)
    def record(self,started,status):
        elapsed=self.clock()-started
        if not math.isfinite(elapsed) or elapsed<0:return None
        seconds=round(min(elapsed,3600),3)
        status=status if status in ('success','unavailable','forbidden','clarification_required','cancelled','error') else 'other'
        self.samples.append((seconds,status));return round(seconds*1000)
    def project(self):
        values=sorted(s for s,_ in self.samples)
        def percentile(p):return values[max(0,math.ceil(len(values)*p)-1)] if values else None
        return {'scope':'Server text processing; excludes microphone, speech and network playback',
                'sample_count':len(values),'last_seconds':self.samples[-1][0] if values else None,
                'median_seconds':percentile(.5),'p95_seconds':percentile(.95),
                'slow_requests':sum(s>=12 for s,_ in self.samples),
                'unavailable_requests':sum(status in ('unavailable','error') for _,status in self.samples),
                'retention':'Last 100 requests in memory; resets when Jarvis restarts'}

"""Request-local HA calendar permissions, independent of speaker relevance."""
from contextlib import contextmanager
from contextvars import ContextVar
from dataclasses import dataclass

@dataclass(frozen=True)
class CalendarAccess:
    actor: str | None = None
    read: bool = False
    write: bool = False

current_calendar_access=ContextVar('ha_calendar_access',default=CalendarAccess())

@contextmanager
def calendar_scope(payload):
    if payload is None:
        yield
        return
    if not isinstance(payload,dict) or set(payload)!={'actor','read','write'}:raise ValueError('Invalid calendar authority')
    if not isinstance(payload['actor'],str) or not 1<=len(payload['actor'])<=100 or type(payload['read']) is not bool or type(payload['write']) is not bool or (payload['write'] and not payload['read']):raise ValueError('Invalid calendar authority')
    token=current_calendar_access.set(CalendarAccess(**payload))
    try:yield
    finally:current_calendar_access.reset(token)

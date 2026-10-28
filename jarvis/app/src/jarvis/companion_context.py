"""Request-local learned observations; no shared mutable prompt context."""
from contextlib import contextmanager
from contextvars import ContextVar
from copy import deepcopy
current_observations=ContextVar('assistant_conversation_observations',default=())
@contextmanager
def observation_scope(records):
 token=current_observations.set(tuple(deepcopy(records)))
 try:yield
 finally:current_observations.reset(token)

"""Deterministic allow-list-only entity reference resolution."""
from __future__ import annotations
class EntityReferenceResolver:
 def __init__(self, allowed_entity_ids, aliases=None, friendly_names=None, areas=None, groups=None): self._ids=frozenset(allowed_entity_ids);self._aliases=aliases or {};self._friendly=friendly_names or {};self._areas=areas or {};self._groups=groups or {}
 def resolve(self, reference):
  n=self._norm(reference); matches=[]
  if n in self._areas:return tuple(sorted(entity for entity in self._areas[n] if entity in self._ids))
  if n in self._groups:return tuple(sorted(entity for entity in self._groups[n] if entity in self._ids))
  for entity in self._ids:
   names={self._norm(entity),self._norm(entity.replace("."," ").replace("_"," "))}
   names|={self._norm(name) for name,target in self._friendly.items() if target==entity}
   names|={self._norm(a) for a,v in self._aliases.items() if v==entity}
   if n in names: matches.append(entity)
  return tuple(sorted(matches))
 def candidates(self, reference):
  n=self._norm(reference)
  return tuple(sorted(entity for entity in self._ids if n in {self._norm(entity), self._norm(entity.replace("."," ").replace("_"," "))} or any(n == self._norm(name) and target == entity for name,target in self._friendly.items())))
 @staticmethod
 def _norm(v): return " ".join(v.casefold().split())

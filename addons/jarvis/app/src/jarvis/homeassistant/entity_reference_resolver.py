"""Deterministic allow-list-only entity reference resolution."""
from __future__ import annotations
class EntityReferenceResolver:
 def __init__(self, allowed_entity_ids, aliases=None): self._ids=frozenset(allowed_entity_ids);self._aliases=aliases or {}
 def resolve(self, reference):
  n=self._norm(reference); matches=[]
  for entity in self._ids:
   names={self._norm(entity),self._norm(entity.replace("."," ").replace("_"," "))}
   names|={self._norm(a) for a,v in self._aliases.items() if v==entity}
   if n in names: matches.append(entity)
  return tuple(sorted(matches))
 @staticmethod
 def _norm(v): return " ".join(v.casefold().split())

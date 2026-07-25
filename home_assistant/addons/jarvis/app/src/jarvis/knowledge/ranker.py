"""Deterministic baseline ranker for curated Knowledge."""
from __future__ import annotations
from typing import Protocol
from jarvis.models.knowledge import KnowledgeRecord
from jarvis.models.knowledge_retrieval import KnowledgeMatch, KnowledgeRetrievalQuery
class KnowledgeRanker(Protocol):
    def rank(self, query: KnowledgeRetrievalQuery, records: tuple[KnowledgeRecord,...]) -> tuple[KnowledgeMatch,...]: ...
class DeterministicKnowledgeRanker:
    def rank(self, query, records):
        q=self._norm(query.query_text); qt=set(q.split()); wanted={self._norm(t) for t in query.requested_tags}
        matches=[]
        for r in records:
            c=self._norm(r.content); t=self._norm(r.title or ""); ct=set(c.split()); tt=set(t.split()); tags={self._norm(x) for x in r.tags}
            breakdown={"exact_content":5.0 if q and q==c else 0.0,"exact_title":3.0 if q and q==t else 0.0,
                "content_token_overlap":(len(qt&ct)/len(qt)*4 if qt else 0.0),"title_token_overlap":(len(qt&tt)/len(qt)*2 if qt else 0.0),"tag_overlap":(len(wanted&tags)/len(wanted)*2 if wanted else 0.0)}
            reasons=tuple(k for k,v in breakdown.items() if v)
            matches.append(KnowledgeMatch(r,sum(breakdown.values()),breakdown,reasons))
        return tuple(sorted(matches,key=lambda m:(-m.total_score,m.record.knowledge_id)))
    @staticmethod
    def _norm(value): return " ".join(value.casefold().split())

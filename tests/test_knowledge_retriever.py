import unittest
from datetime import datetime, timezone
from jarvis.knowledge.in_memory_store import InMemoryKnowledgeStore
from jarvis.knowledge.policy import ExplicitKnowledgePolicy
from jarvis.knowledge.ranker import DeterministicKnowledgeRanker
from jarvis.knowledge.retriever import PolicyControlledKnowledgeRetriever
from jarvis.models.knowledge import KnowledgeRecord, KnowledgeSource, KnowledgeStatus, KnowledgeType
from jarvis.models.knowledge_retrieval import KnowledgeRetrievalQuery
TIME=datetime(2026,7,24,12,0,tzinfo=timezone.utc)
class KnowledgeRetrieverTests(unittest.TestCase):
 def setUp(self): self.store=InMemoryKnowledgeStore();self.r=PolicyControlledKnowledgeRetriever(self.store,ExplicitKnowledgePolicy(),DeterministicKnowledgeRanker())
 def rec(self,id,content,title=None,tags=(),status=KnowledgeStatus.ACTIVE): return KnowledgeRecord(id,KnowledgeType.HOME_REFERENCE,content,KnowledgeSource.USER_PROVIDED,TIME,TIME,title=title,tags=tags,status=status)
 def test_ranks_exact_title_content_tags_and_tie(self):
  self.store.create(self.rec("b","Kitchen boiler",tags=("heating",)));self.store.create(self.rec("a","Kitchen boiler",tags=("heating",)))
  m=self.r.retrieve(KnowledgeRetrievalQuery("kitchen boiler",requested_tags=("HEATING",))).matches
  self.assertEqual([x.record.knowledge_id for x in m],["a","b"]);self.assertEqual(m[0].score_breakdown["exact_content"],5.0)
 def test_title_filters_policy_empty_and_limit(self):
  self.store.create(self.rec("title","Other",title="Boiler manual"));self.store.create(self.rec("bad","No",status=KnowledgeStatus.REJECTED))
  result=self.r.retrieve(KnowledgeRetrievalQuery("boiler manual",maximum_results=1));self.assertEqual(result.matches[0].record.knowledge_id,"title");self.assertEqual(result.records_excluded_by_policy,1)
  self.assertEqual(self.r.retrieve(KnowledgeRetrievalQuery(maximum_results=0)).matches,())
  with self.assertRaises(ValueError): KnowledgeRetrievalQuery(maximum_results=11)

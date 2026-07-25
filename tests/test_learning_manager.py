import unittest
from jarvis.learning.manager import LearningProposalManager
from jarvis.learning.policy import LearningSafetyPolicy
from jarvis.models.learning import LearningDestination,LearningProposal,LearningStatus
class Tests(unittest.TestCase):
 def proposal(self,id,source="explicit_user_review"):return LearningProposal(id,"summary","content",LearningDestination.MEMORY,source)
 def test_review_and_management_are_explicit(self):
  m=LearningProposalManager(LearningSafetyPolicy());p,_=m.submit(self.proposal("a"));self.assertEqual(m.list_pending(),(p,))
  self.assertEqual(m.decide("a",True).status,LearningStatus.APPROVED);self.assertEqual(m.list_pending(),())
  self.assertEqual(m.submit(self.proposal("x","sensitive"))[0].status,LearningStatus.REJECTED)
  m.submit(self.proposal("b"));self.assertEqual(m.cancel("b").status,LearningStatus.CANCELLED)

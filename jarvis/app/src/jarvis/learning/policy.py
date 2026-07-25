"""Deny-by-default safety policy for explicit learning review."""
from jarvis.models.learning import LearningProposal
class LearningSafetyPolicy:
 _FORBIDDEN={"sensitive","security","presence","health","credentials","home_assistant_state","home_assistant_history","inferred_behavior"}
 def evaluate(self,p:LearningProposal):return (False,"forbidden_learning_source") if p.source_category in self._FORBIDDEN else (True,"review_required")

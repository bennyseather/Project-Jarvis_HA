import unittest
from jarvis.household_planning import Plan,resolve_return_dates
from jarvis.event_activity import requirement
class DateReturnTests(unittest.TestCase):
 def setUp(self):self.old=Plan(('mia',),'overview','2026-11-09','2026-11-10')
 def test_matching_bare_weekday_returns_to_selected_date(self):
  for word in ('monday','mandag'):self.assertEqual(resolve_return_dates(word,'2026-11-02',self.old,returning=True),('2026-11-09','2026-11-10'))
 def test_ordinary_weekday_and_explicit_date_are_not_forced_to_old_task(self):
  for phrase,expected in [('monday','2026-11-02'),('this monday','2026-11-02'),('denne mandag','2026-11-02'),('2026-11-02','2026-11-02'),('friday','2026-11-06')]:
   self.assertEqual(resolve_return_dates(phrase,'2026-11-02',self.old,returning=phrase!='monday')[0],expected)
 def test_new_next_qualifier_and_broad_period_keep_regular_resolution(self):
  later=Plan(('mia',),'overview','2026-11-16','2026-11-17');self.assertEqual(resolve_return_dates('next monday','2026-11-02',later,returning=True)[0],'2026-11-09')
  week=Plan(('mia',),'overview','2026-11-09','2026-11-16');self.assertEqual(resolve_return_dates('mandag','2026-11-02',week,returning=True)[0],'2026-11-02')
 def test_date_prepositions_are_not_activity_literals(self):
  for text in ('Mias øving på mandag','Mia rehearsal on Monday'):
   out=requirement(text,['Mia']);self.assertEqual(out,{'groups':['rehearsal'],'literals':[]})
 def test_new_activity_survives_date_grammar(self):
  out=requirement('Mias svømming på mandag',['Mia']);self.assertIn('swimming',out['groups']);self.assertNotIn('på',out['literals'])

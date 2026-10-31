"""Fictional positive-evidence tests; no household, models or network access."""
import unittest

from jarvis.event_activity import requirement,requested,support,generic_candidate


class ActivityEvidenceTests(unittest.TestCase):
    def event(self,title='Training',**extra):return {'text':title,'description_units':[],**extra}
    def scope(self,activity):return requirement('What should Alex bring for '+activity+' tomorrow?',['Alex'])

    def test_broad_person_date_question_needs_no_activity_proof(self):
        for question in ('What should Alex prepare for tomorrow?','Where is it?','And Sunday?','Anything else?',
                         'What should Alex prepare for tomorrow evening?','What should Alex bring for her activities tomorrow?'):
            self.assertFalse(requested(requirement(question,['Alex'])),question)

    def test_contracted_question_openings_are_not_activity_names(self):
        for q in ("whats left before we leave?", "what's left before we leave?", "what’s left before we leave?", "Jarvis, whats left before we leave?", "wheres it?", "whens it?"):
            self.assertFalse(requested(requirement(q,['Mia'])),q)
        self.assertTrue(requested(requirement('What about robotics?',['Mia'])))
        self.assertTrue(support(requirement('whats needed for swimming?',['Mia']),self.event('Swimming lesson')))

    def test_generic_training_does_not_prove_a_specific_sport(self):
        for activity in ('swimming','gymnastics','football','handball','dance','tennis'):
            for title in ('Training','Trening','Fitness session','Treningsøkt'):
                self.assertFalse(support(self.scope(activity),self.event(title)),(activity,title))

    def test_known_english_norwegian_aliases_need_positive_source_words(self):
        for requested_kind,recorded in (('swimming','Svømmetrening'),('svømming','Swimming lesson'),
                ('gymnastics','Gymnastikk'),('football','Fotballtrening'),('chess','Sjakkklubb'),
                ('band rehearsal','Fellesøving Korps'),('music rehearsal','Fellesøving Korps'),
                ('rhythmic gymnastics','Rytmisk gymnastikk')):
            self.assertTrue(support(self.scope(requested_kind),self.event(recorded)),(requested_kind,recorded))

    def test_parent_kind_is_not_proof_of_the_specific_subtype(self):
        for requested_kind,title in (('piano','Music lesson'),('band','Music rehearsal'),
                ('rhythmic gymnastics','Gymnastics'),('choir','Music rehearsal'),('piano','Band rehearsal')):
            self.assertFalse(support(self.scope(requested_kind),self.event(title)),(requested_kind,title))
        self.assertTrue(support(self.scope('music'),self.event('Piano lesson')))

    def test_location_emoji_and_notes_cannot_supply_kind(self):
        event=self.event('Training 🏊',location='Swimming pool',approved_notes=['Alex likes swimming'])
        self.assertFalse(support(self.scope('swimming'),event));self.assertTrue(generic_candidate(event))

    def test_positive_description_can_identify_generic_event(self):
        event=self.event(description_units=['This is swimming training.','Bring a towel.'])
        self.assertTrue(support(self.scope('swimming'),event))

    def test_negative_conditional_cancelled_or_uncertain_is_not_positive_proof(self):
        for clause in ('Not swimming.','No swimming today.','Swimming is cancelled.',
                'If this is swimming, bring a towel.','Maybe swimming.','Ikke svømming.',
                'Hvis det er svømming, ta med håndkle.','Swimming…','Swimming or gymnastics.',
                'Swimming / gymnastics','Swimming tbc','Perhaps swimming.','Swimming?'):
            self.assertFalse(support(self.scope('swimming'),self.event(description_units=[clause])),clause)
        self.assertFalse(support(self.scope('swimming'),self.event('Swimming lesson',description_units=['Swimming is cancelled.'])))

    def test_negative_equipment_rule_does_not_cancel_positive_title(self):
        self.assertTrue(support(self.scope('swimming'),self.event('Swimming lesson',description_units=['Do not bring a packed lunch.'])))

    def test_unrecognised_kind_requires_literal_source_support(self):
        self.assertTrue(support(self.scope('robotics'),self.event('Robotics club')))
        self.assertFalse(support(self.scope('robotics'),self.event('Club meeting')))

    def test_multiple_requested_kinds_are_not_matched_by_one_partial_kind(self):
        self.assertFalse(support(self.scope('piano and swimming'),self.event('Piano lesson')))

    def test_specific_source_is_not_mislabelled_generic(self):
        self.assertFalse(generic_candidate(self.event('Swimming training')))
        self.assertTrue(generic_candidate(self.event('Training 💪')))

    def test_common_session_word_does_not_block_bilingual_activity(self):
        self.assertTrue(support(self.scope('swimming lesson'),self.event('Svømmetrening')))

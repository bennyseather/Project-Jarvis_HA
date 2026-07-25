import unittest
from datetime import datetime, timezone

from jarvis.models.event_timeline import TimelineQuery
from jarvis.timeline.policy import EventTimelinePolicy
from jarvis.timeline.store import InMemoryTimelineStore
from jarvis.timeline.subscriber import HomeAssistantEventSubscriber


class EventTimelineTests(unittest.TestCase):
    def test_policy_is_deny_by_default(self):
        self.assertFalse(EventTimelinePolicy().permits("state_changed", "light.blocks"))
        self.assertTrue(EventTimelinePolicy(True, ("state_changed",), ("light.blocks",)).permits("state_changed", "light.blocks"))

    def test_store_is_bounded_and_newest_first(self):
        store = InMemoryTimelineStore(2)
        now = datetime.now(timezone.utc)
        store.append("state_changed", "light.blocks", now, "off")
        store.append("state_changed", "light.blocks", now, "on")
        store.append("state_changed", "light.blocks", now, "off")
        self.assertEqual([event.state for event in store.retrieve(TimelineQuery())], ["off", "on"])

    def test_subscriber_filters_before_recording(self):
        store = InMemoryTimelineStore()
        subscriber = HomeAssistantEventSubscriber(None, EventTimelinePolicy(True, ("state_changed",), ("light.blocks",)), store)
        subscriber.process({"type":"event", "event":{"event_type":"state_changed", "time_fired":"2026-07-25T12:00:00Z", "data":{"entity_id":"light.blocks", "new_state":{"state":"on", "attributes":{"secret":"ignored"}}}}})
        subscriber.process({"type":"event", "event":{"event_type":"state_changed", "data":{"entity_id":"light.other"}}})
        events = store.retrieve(TimelineQuery())
        self.assertEqual(len(events), 1)
        self.assertEqual((events[0].entity_id, events[0].state), ("light.blocks", "on"))

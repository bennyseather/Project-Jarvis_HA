"""Context-matched preparation, bounded recovery and concurrent failure guards."""
import logging,threading,time,unittest
from jarvis.providers.local_first_provider import LocalFirstReasoningProvider,LocalReasoningPolicy
from jarvis.sentence_stream import sentence_sink

class Fixture(LocalFirstReasoningProvider):
    def __init__(self,handler=None,**policy):
        super().__init__(LocalReasoningPolicy(**policy),logging.getLogger('fictional-readiness'),fallback=None)
        self.calls=[];self.handler=handler;self.recovered=threading.Event()
    def _post(self,path,payload,**kwargs):
        self.calls.append((path,payload,kwargs))
        if self.handler:return self.handler(payload)
        return {'done':True,'message':{'content':'Ready'},'done_reason':'stop'}
    def _recover(self):
        try:super()._recover()
        finally:self.recovered.set()
    def ask_local(self,**kwargs):
        return self.reason_local(instructions='Fictional test only.',input_messages=[{'role':'user','content':'Fixture'}],timeout_seconds=4,**kwargs)

class ReadinessTests(unittest.TestCase):
    def test_warm_matches_normal_context_without_user_content_or_streaming(self):
        p=Fixture(context_tokens=8192);spoken=[];token=sentence_sink.set(spoken.append)
        try:self.assertTrue(p.warm()['ready'])
        finally:sentence_sink.reset(token)
        _,warm,options=p.calls[0]
        self.assertEqual(warm['options'],{'num_ctx':8192});self.assertEqual(warm['messages'],[])
        self.assertFalse(warm['stream']);self.assertFalse(warm['think']);self.assertEqual(warm['keep_alive'],-1)
        self.assertEqual(options['timeout_seconds'],30);self.assertEqual(spoken,[])
        self.assertEqual(p.ask_local()['status'],'success');self.assertEqual(p.calls[-1][1]['options']['num_ctx'],warm['options']['num_ctx'])
    def test_same_model_warms_once_and_both_distinct_models_must_complete(self):
        p=Fixture();self.assertTrue(p.warm()['ready']);self.assertEqual(len(p.calls),1)
        p=Fixture(lambda payload:{'done':payload['model']!='other'},voice_model='other')
        self.assertFalse(p.warm()['ready']);self.assertEqual(len(p.calls),2)
    def test_incomplete_or_malformed_warm_is_not_readiness_and_does_not_clear_failure(self):
        for value in ({},{'done':False},{'done':'true'}):
            p=Fixture(lambda payload:value);p._local_unavailable_until=time.monotonic()+30
            self.assertFalse(p.warm()['ready']);self.assertGreater(p._local_unavailable_until,time.monotonic())
    def test_timeout_warms_once_in_background_and_recovery_ends_cooldown_early(self):
        entered=threading.Event();release=threading.Event();users=[]
        def handle(payload):
            if not payload['messages']:
                entered.set();self.assertTrue(release.wait(3));return {'done':True}
            users.append(payload['messages'])
            if len(users)==1:raise TimeoutError('fictional timeout')
            return {'message':{'content':'Ready'}}
        p=Fixture(handle)
        try:
            self.assertEqual(p.ask_local()['status'],'unavailable');self.assertTrue(entered.wait(3))
            self.assertGreater(p._local_unavailable_until,time.monotonic())
            self.assertEqual(p.ask_local()['status'],'unavailable');self.assertEqual(len(users),1)
        finally:release.set()
        self.assertTrue(p.recovered.wait(3));self.assertEqual(p._local_unavailable_until,0)
        self.assertEqual(p.ask_local()['status'],'success');self.assertEqual(len(users),2)
        self.assertEqual(sum(not call[1]['messages'] for call in p.calls),1)
    def test_real_outage_keeps_cooldown_and_does_not_start_a_probe_storm(self):
        def offline(payload):raise ConnectionError('fictional offline')
        p=Fixture(offline);self.assertEqual(p.ask_local()['status'],'unavailable');self.assertTrue(p.recovered.wait(3))
        until=p._local_unavailable_until
        for _ in range(20):self.assertEqual(p.ask_local()['status'],'unavailable')
        self.assertEqual(len(p.calls),2);self.assertEqual(until,p._local_unavailable_until)
        self.assertFalse(p._recovery_scheduled)
    def test_failed_probe_is_throttled_even_if_foreground_gate_is_reopened(self):
        def offline(payload):raise ConnectionError('fictional offline')
        p=Fixture(offline);p.ask_local();self.assertTrue(p.recovered.wait(3));p._local_unavailable_until=0
        p.ask_local();self.assertEqual(len(p.calls),3)
        self.assertEqual(sum(not call[1]['messages'] for call in p.calls),1)
    def test_successful_warm_clears_an_older_failure(self):
        p=Fixture();p._local_unavailable_until=time.monotonic()+30;p._failure_generation=2
        self.assertTrue(p.warm()['ready']);self.assertEqual(p._local_unavailable_until,0)
    def test_stale_warm_does_not_clear_a_newer_failure(self):
        p=Fixture()
        def handle(payload):
            with p._state_lock:p._failure_generation+=1;p._local_unavailable_until=time.monotonic()+30
            return {'done':True}
        p.handler=handle;self.assertTrue(p.warm()['ready']);self.assertGreater(p._local_unavailable_until,time.monotonic())
    def test_recovery_during_startup_waits_for_warm_then_verifies_again(self):
        entered=threading.Event();release=threading.Event();warms=[]
        def handle(payload):
            if payload['messages']:raise TimeoutError('fictional load in progress')
            warms.append(1)
            if len(warms)==1:entered.set();self.assertTrue(release.wait(3))
            return {'done':True}
        p=Fixture(handle);startup=threading.Thread(target=p.warm,daemon=True);startup.start()
        try:
            self.assertTrue(entered.wait(3));self.assertEqual(p.ask_local()['status'],'unavailable')
        finally:release.set()
        startup.join(3);self.assertFalse(startup.is_alive());self.assertTrue(p.recovered.wait(3))
        self.assertEqual(len(warms),2);self.assertEqual(p._local_unavailable_until,0)
    def test_invalid_request_contract_never_starts_recovery_or_network(self):
        p=Fixture();self.assertEqual(p.ask_local(temperature=9)['status'],'unavailable')
        self.assertEqual(p.calls,[]);self.assertFalse(p._recovery_scheduled);self.assertEqual(p._failure_generation,0)
    def test_stale_foreground_success_does_not_erase_a_newer_failure(self):
        p=Fixture()
        def handle(payload):
            with p._state_lock:p._failure_generation+=1;p._local_unavailable_until=time.monotonic()+30
            return {'message':{'content':'Ready'}}
        p.handler=handle;self.assertEqual(p.ask_local()['status'],'success');self.assertGreater(p._local_unavailable_until,time.monotonic())

if __name__=='__main__':unittest.main()

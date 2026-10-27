"""Authenticated planner HTTP contract with fake calendar storage only."""
import asyncio,json,unittest
from types import SimpleNamespace
from urllib.request import Request,urlopen
from urllib.error import HTTPError
from jarvis.homeassistant.bridge_server import ConversationBridgeServer
from jarvis.household_planner import get_planner,CALENDAR,ZONE
from test_household_planner import Client
from test_planning_preparation_bundle import profile
from datetime import datetime

class PlannerBridgeTests(unittest.IsolatedAsyncioTestCase):
    async def asyncSetUp(self):
        self.p=profile();self.c=Client()
        self.container=SimpleNamespace(household_profile=self.p,home_assistant=self.c,proactive_allowed_entities=[CALENDAR])
        self.route=get_planner(self.container);self.route.now=lambda:datetime(2026,10,27,12,tzinfo=ZONE);self.route.bootstrap([])
        self.server=ConversationBridgeServer(SimpleNamespace(_application=SimpleNamespace(container=self.container)),'fictional-only',asyncio.get_running_loop())
        self.server.start('127.0.0.1',0);self.url='http://127.0.0.1:'+str(self.server._server.server_port)
    async def asyncTearDown(self):
        await asyncio.to_thread(self.server.stop);self.server._server.server_close();self.route.db.close()
    async def post(self,action,payload,*,key='fictional-only',owner='fictional-session'):
        def call():
            req=Request(self.url+'/v1/planner',headers={'Authorization':'Bearer '+key},data=json.dumps({'action':action,'payload':payload,'owner':owner}).encode())
            with urlopen(req,timeout=8) as response:
                assert response.headers['Cache-Control']=='no-store'
                return json.load(response)
        return await asyncio.to_thread(call)
    async def test_unauthenticated_call_cannot_read_or_write(self):
        with self.assertRaises(HTTPError) as e:await self.post('agenda',{},key='wrong')
        self.assertEqual(e.exception.code,401);self.assertFalse(self.c.writes)
    async def test_review_and_explicit_confirm_roundtrip(self):
        payload={'title':'Fictional club','members':['linda'],'category':'sport','start':'2026-11-05T17:00','end':'2026-11-05T18:00','all_day':False,'location':'','notes':''}
        out=await self.post('review',payload);self.assertTrue(out['ok']);self.assertFalse(self.c.writes)
        token=out['result']['token'];result=await self.post('confirm',{'token':token})
        self.assertEqual(result['result']['state'],'confirmed');self.assertEqual(len(self.c.writes),1)
        result=await self.post('confirm',{'token':token});self.assertEqual(len(self.c.writes),1)
    async def test_unknown_operation_and_cross_session_confirm_are_rejected(self):
        self.assertFalse((await self.post('delete',{}))['ok'])
        payload={'title':'Fictional club','members':['mia'],'category':'other','start':'2026-11-05T17:00','end':'2026-11-05T18:00','all_day':False,'location':'','notes':''}
        review=await self.post('review',payload)
        self.assertFalse((await self.post('confirm',{'token':review['result']['token']},owner='other-session'))['ok']);self.assertFalse(self.c.writes)
    async def test_shared_overview_exposes_only_catalogue_metadata_not_write_receipts(self):
        def call():
            with urlopen(Request(self.url+'/v1/household',headers={'Authorization':'Bearer fictional-only'}),timeout=8) as response:return json.load(response)
        data=await asyncio.to_thread(call)
        self.assertTrue(data['read_only']);self.assertTrue(data['planner']['ready'])
        self.assertNotIn('intents',str(data));self.assertNotIn('fictional-only',str(data))

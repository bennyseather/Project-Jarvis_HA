"""AST-isolated reconfigure flow contract; no HA config or real secrets."""
import ast
import asyncio
from pathlib import Path
from types import SimpleNamespace
import unittest


class FlowTests(unittest.IsolatedAsyncioTestCase):
    def flow(self, status=200, failure=None):
        path=Path('home_assistant/custom_components/jarvis_conversation/config_flow.py')
        if not path.exists():path=Path('custom_components/jarvis_conversation/config_flow.py')
        cls=next(n for n in ast.parse(path.read_text()).body if isinstance(n,ast.ClassDef) and n.name=='ConfigFlow')
        method=next(n for n in cls.body if isinstance(n,ast.AsyncFunctionDef) and n.name=='async_step_reconfigure')
        calls=[]
        class Response:
            async def __aenter__(self):
                if failure:raise failure
                return SimpleNamespace(status=status)
            async def __aexit__(self,*args):pass
        def get(url,**kwargs):calls.append((url,kwargs));return Response()
        fakevol=SimpleNamespace(Schema=lambda x:x,Required=lambda x:x)
        selector=SimpleNamespace(TextSelector=lambda x:x,TextSelectorConfig=lambda **x:x,
                                 TextSelectorType=SimpleNamespace(PASSWORD='password'))
        env={'async_get_clientsession':lambda hass:SimpleNamespace(get=get),'aiohttp':SimpleNamespace(
            ClientTimeout=lambda **x:x,ClientError=OSError),'vol':fakevol,'selector':selector}
        exec(compile(ast.Module(body=[method],type_ignores=[]),str(path),'exec'),env)
        entry=SimpleNamespace(data={'bridge_url':'http://fixture:8099','api_key':'old-fixture'},options={'keep':True})
        flow=SimpleNamespace(hass=object(),_get_reconfigure_entry=lambda:entry,
            async_update_reload_and_abort=lambda e,**kwargs:{'type':'abort','updates':kwargs},
            async_show_form=lambda **kwargs:{'type':'form',**kwargs})
        return lambda data:env['async_step_reconfigure'](flow,data),calls,entry

    async def test_only_credential_updated_after_validation(self):
        ask,calls,entry=self.flow();key='synthetic-fixture-'+'x'*32
        r=await ask({'api_key':key,'bridge_url':'http://untrusted'})
        self.assertEqual(r['updates'],{'data_updates':{'api_key':key}})
        self.assertEqual(calls[0][0],'http://fixture:8099/v1/household')
        self.assertFalse(calls[0][1]['allow_redirects'])
        self.assertEqual(entry.options,{'keep':True})

    async def test_bad_keys_and_connection_errors_do_not_update_or_echo(self):
        for status,failure in [(401,None),(500,None),(200,OSError('private-detail')),(200,TimeoutError())]:
            ask,_,_=self.flow(status,failure);key='synthetic-fixture-'+'x'*32
            r=await ask({'api_key':key});self.assertEqual(r['type'],'form')
            self.assertNotIn(key,str(r));self.assertNotIn('private-detail',str(r))
        for value in ['', 'short', 'x '*32, 'x'*513]:
            ask,calls,_=self.flow();r=await ask({'api_key':value})
            self.assertEqual(r['type'],'form');self.assertEqual(calls,[])

    async def test_initial_form_never_contains_old_credential(self):
        ask,calls,_=self.flow();r=await ask(None)
        self.assertNotIn('old-fixture',str(r));self.assertEqual(calls,[])


if __name__=='__main__':unittest.main()

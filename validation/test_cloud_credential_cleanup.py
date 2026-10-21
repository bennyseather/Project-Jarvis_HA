"""No external API calls. Empty keys fail closed and errors cannot echo secrets."""
import logging
import unittest
from unittest.mock import patch
from jarvis.providers.openai_provider import OpenAIProvider


class DisabledCloudTests(unittest.TestCase):
    def test_empty_key_never_initializes_sdk_or_uses_environment(self):
        with patch('jarvis.providers.openai_provider.OpenAI') as sdk:
            p=OpenAIProvider('',logging.getLogger('credential-test'))
            self.assertIn('disabled',p.ask('fixture'))
            self.assertEqual(p.reason(instructions='',input_messages=[],model='fixture',timeout_seconds=1)['status'],'unavailable')
            r=p.research(instructions='',input_messages=[],force_search=True,search_context_size='low')
            self.assertFalse(r['researched']);sdk.assert_not_called()

    def test_exception_body_is_not_logged(self):
        secret='synthetic-secret-do-not-log'
        with patch('jarvis.providers.openai_provider.OpenAI') as sdk:
            sdk.return_value.responses.create.side_effect=RuntimeError(secret)
            p=OpenAIProvider('synthetic-fixture',logging.getLogger('credential-test'))
            with self.assertLogs('credential-test',level='ERROR') as logs:
                p.ask('fixture')
                p.reason(instructions='',input_messages=[],model='fixture',timeout_seconds=1)
                p.research(instructions='',input_messages=[],force_search=True,search_context_size='low')
            self.assertNotIn(secret,str(logs.output))

if __name__=='__main__':unittest.main()

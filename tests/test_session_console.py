import config
import unittest
import pkg.provider.session
import pkg.provider.manager


class TestOpenAISession(unittest.TestCase):
    def test_session_console(self):
        interact = pkg.provider.manager.OpenAIInteract(config.openai_config['api_key'], config.completion_api_params)

        session = pkg.provider.session.Session('test')
        print(session.append('你好'))
        print("#{}#".format(session.prompt))

        print(session.append('你叫什么名字'))
        print("#{}#".format(session.prompt))

# 提供与模型交互的抽象接口
import openai, logging

COMPLETION_MODELS = {
    'text-davinci-003',
    'text-davinci-002',
    'code-davinci-002',
    'code-cushman-001',
    'text-curie-001',
    'text-babbage-001',
    'text-ada-001',
}

CHAT_COMPLETION_MODELS = {
    'gpt-3.5-turbo',
    'gpt-3.5-turbo-0301',
}

EDIT_MODELS = {

}

IMAGE_MODELS = {

}


class ModelRequest():

    can_chat = False

    def __init__(self, model_name, user_name, request_fun):
        self.model_name = model_name
        self.user_name = user_name
        self.request_fun = request_fun

    def request(self, **kwargs):
        ret = self.request_fun(**kwargs)
        self.ret = self.ret_handle(ret)
        self.message = self.ret["choices"][0]["message"]

    def msg_handle(self, msg):
        return msg
    
    def ret_handle(self, ret):
        return ret
    
    def get_total_tokens(self):
        return self.ret['usage']['total_tokens']
    
    def get_message(self):
        return self.message
    
    def get_response(self):
        return self.ret
    

class ChatCompletionModel(ModelRequest):
    """ChatCompletion接口实现"""
    Chat_role = ['system', 'user', 'assistant']
    def __init__(self, model_name, user_name):
        request_fun = openai.ChatCompletion.create
        self.can_chat = True
        super().__init__(model_name, user_name, request_fun)

    def request(self, messages, **kwargs):
        ret = self.request_fun(messages = self.msg_handle(messages), **kwargs, user=self.user_name)
        self.ret = self.ret_handle(ret)
        self.message = self.ret["choices"][0]["message"]['content']

    def msg_handle(self, msgs):
        temp_msgs = []
        for msg in msgs:
            if msg['role'] not in self.Chat_role:
                msg['role'] = 'user'
            temp_msgs.append(msg)
        return temp_msgs

    def get_content(self):
        return self.message
    

class CompletionModel(ModelRequest):
    """Completion接口实现"""
    def __init__(self, model_name, user_name):
        request_fun = openai.Completion.create
        super().__init__(model_name, user_name, request_fun)

    def request(self, prompt, **kwargs):
        ret = self.request_fun(prompt = self.msg_handle(prompt), **kwargs)
        self.ret = self.ret_handle(ret)
        self.message = self.ret["choices"][0]["text"]

    def msg_handle(self, msgs):
        prompt = ''
        for msg in msgs:
            if msg['role'] == '':
                prompt = prompt + "{}\n".format(msg['content'])
            else:
                prompt = prompt + "{}:{}\n".format(msg['role'] if msg['role']!='system' else '你的回答要遵守此规则', msg['content'])
        return prompt
    
    def get_text(self):
        return self.message
    

def create_openai_model_request(model_name: str, user_name: str = 'user') -> ModelRequest:
    """使用给定的模型名称创建模型请求对象"""
    if model_name in CHAT_COMPLETION_MODELS:
        model = ChatCompletionModel(model_name, user_name)
    elif model_name in COMPLETION_MODELS:
        model = CompletionModel(model_name, user_name)
    else :
        log = "找不到模型[{}]，请检查配置文件".format(model_name)
        logging.error(log)
        raise IndexError(log)
    logging.debug("使用接口[{}]创建模型请求[{}]".format(model.__class__.__name__, model_name))
    return model

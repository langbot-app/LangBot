# 提供与模型交互的抽象接口
import openai, logging, threading, asyncio

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
    """GPT父类"""
    can_chat = False
    runtime:threading.Thread = None
    ret = ""
    proxy:str = None

    def __init__(self, model_name, user_name, request_fun, http_proxy:str = None):
        self.model_name = model_name
        self.user_name = user_name
        self.request_fun = request_fun
        if http_proxy != None:
            self.proxy = http_proxy
            openai.proxy = self.proxy

    async def __a_request__(self, **kwargs):
        self.ret = await self.request_fun(**kwargs)

    def request(self, **kwargs):
        if self.proxy != None: #异步请求
            self.runtime = threading.Thread(
                target=asyncio.run,
                args=(self.__a_request__(**kwargs),)
            )
            self.runtime.start()
        else: #同步请求
            self.ret = self.request_fun(**kwargs)

    def __msg_handle__(self, msg):
        """将prompt dict转换成接口需要的格式"""
        return msg
    
    def ret_handle(self):
        '''
        API消息返回处理函数
        若重写该方法，应检查异步线程状态，或在需要检查处super该方法
        '''
        if self.runtime != None and isinstance(self.runtime, threading.Thread):
            self.runtime.join()
        return

    def get_total_tokens(self):
        try:
            return self.ret['usage']['total_tokens']
        except Exception:
            return 0

    def get_message(self):
        return self.message

    def get_response(self):
        return self.ret

class ChatCompletionModel(ModelRequest):
    """ChatCompletion类模型"""
    Chat_role = ['system', 'user', 'assistant']
    def __init__(self, model_name, user_name, http_proxy:str = None, **kwargs):
        if http_proxy == None:
            request_fun = openai.ChatCompletion.create
        else:
            request_fun = openai.ChatCompletion.acreate
        self.can_chat = True
        super().__init__(model_name, user_name, request_fun, http_proxy, **kwargs)

    def request(self, prompts, **kwargs):
        prompts = self.__msg_handle__(prompts)
        kwargs['messages'] = prompts
        super().request(**kwargs)
        self.ret_handle()

    def __msg_handle__(self, msgs):
        temp_msgs = []
        # 把msgs拷贝进temp_msgs
        for msg in msgs:
            temp_msgs.append(msg.copy())
        return temp_msgs

    def get_message(self):
        return self.ret["choices"][0]["message"]['content'] #需要时直接加载加快请求速度，降低内存消耗


class CompletionModel(ModelRequest):
    """Completion类模型"""
    def __init__(self, model_name, user_name, http_proxy:str = None, **kwargs):
        if http_proxy == None:
            request_fun = openai.Completion.create
        else:
            request_fun = openai.Completion.acreate
        super().__init__(model_name, user_name, request_fun, http_proxy, **kwargs)

    def request(self, prompts, **kwargs):
        prompts = self.__msg_handle__(prompts)
        kwargs['prompt'] = prompts
        super().request(**kwargs)
        self.ret_handle()

    def __msg_handle__(self, msgs):
        prompt = ''
        for msg in msgs:
            prompt = prompt + "{}: {}\n".format(msg['role'], msg['content'])
        # for msg in msgs:
        #     if msg['role'] == 'assistant':
        #         prompt = prompt + "{}\n".format(msg['content'])
        #     else:
        #         prompt = prompt + "{}:{}\n".format(msg['role'] , msg['content'])
        prompt = prompt + "assistant: "
        return prompt

    def get_message(self):
        return self.ret["choices"][0]["text"]


def create_openai_model_request(model_name: str, user_name: str = 'user', http_proxy:str = None) -> ModelRequest:
    """使用给定的模型名称创建模型请求对象"""
    if model_name in CHAT_COMPLETION_MODELS:
        model = ChatCompletionModel(model_name, user_name, http_proxy)
    elif model_name in COMPLETION_MODELS:
        model = CompletionModel(model_name, user_name, http_proxy)
    else :
        log = "找不到模型[{}]，请检查配置文件".format(model_name)
        logging.error(log)
        raise IndexError(log)
    logging.debug("使用接口[{}]创建模型请求[{}]".format(model.__class__.__name__, model_name))
    return model

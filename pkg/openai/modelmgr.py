"""OpenAI 接口底层封装

目前使用的对话接口有：
ChatCompletion - gpt-3.5-turbo 等模型
Completion - text-davinci-003 等模型
此模块封装此两个接口的请求实现，为上层提供统一的调用方式
"""
import openai, logging, threading, asyncio
import openai.error as aiE

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
    'gpt-4',
    'gpt-4-0314',
    'gpt-4-32k',
    'gpt-4-32k-0314'
}

EDIT_MODELS = {

}

IMAGE_MODELS = {

}


class ModelRequest:
    """模型接口请求父类"""

    can_chat = False
    runtime: threading.Thread = None
    ret = {}
    proxy: str = None
    request_ready = True
    error_info: str = "若在没有任何错误的情况下看到这句话，请带着配置文件上报Issues"

    def __init__(self, model_name, user_name, request_fun, http_proxy:str = None, time_out = None):
        self.model_name = model_name
        self.user_name = user_name
        self.request_fun = request_fun
        self.time_out = time_out
        if http_proxy != None:
            self.proxy = http_proxy
            openai.proxy = self.proxy
            self.request_ready = False

    async def __a_request__(self, **kwargs):
        """异步请求"""

        try:
            self.ret: dict = await self.request_fun(**kwargs)
            self.request_ready = True
        except aiE.APIConnectionError as e:
            self.error_info = "{}\n请检查网络连接或代理是否正常".format(e)
            raise ConnectionError(self.error_info)
        except ValueError as e:
            self.error_info = "{}\n该错误可能是由于http_proxy格式设置错误引起的"
        except Exception as e:
            self.error_info = "{}\n由于请求异常产生的未知错误，请查看日志".format(e)
            raise type(e)(self.error_info)

    def request(self, **kwargs):
        """向接口发起请求"""

        if self.proxy != None: #异步请求
            self.request_ready = False
            loop = asyncio.new_event_loop()
            self.runtime = threading.Thread(
                target=loop.run_until_complete,
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
            self.runtime.join(self.time_out)
        if self.request_ready:
            return
        raise Exception(self.error_info)

    def get_total_tokens(self):
        try:
            return self.ret['usage']['total_tokens']
        except:
            return 0

    def get_message(self):
        return self.message

    def get_response(self):
        return self.ret


class ChatCompletionModel(ModelRequest):
    """ChatCompletion接口的请求实现"""

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
    """Completion接口的请求实现"""

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

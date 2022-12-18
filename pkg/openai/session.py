import logging
import threading
import time

import config
import pkg.openai.manager
import pkg.database.manager

# 运行时保存的所有session
sessions = {}


class SessionOfflineStatus:
    ON_GOING = 'on_going'
    EXPLICITLY_CLOSED = 'explicitly_closed'


# 从数据加载session
def load_sessions():
    global sessions

    db_inst = pkg.database.manager.get_inst()

    session_data = db_inst.load_valid_sessions()

    for session_name in session_data:
        logging.info('加载session: {}'.format(session_name))

        temp_session = Session(session_name)
        temp_session.name = session_name
        temp_session.create_timestamp = session_data[session_name]['create_timestamp']
        temp_session.last_interact_timestamp = session_data[session_name]['last_interact_timestamp']
        temp_session.prompt = session_data[session_name]['prompt']

        sessions[session_name] = temp_session


# 获取指定名称的session，如果不存在则创建一个新的
def get_session(session_name: str):
    global sessions
    if session_name not in sessions:
        sessions[session_name] = Session(session_name)
    return sessions[session_name]


def dump_session(session_name: str):
    global sessions
    if session_name in sessions:
        assert isinstance(sessions[session_name], Session)
        sessions[session_name].persistence()
        del sessions[session_name]


# 从配置文件获取会话预设信息
def get_default_prompt():
    return "You:{}\nBot:好的\n".format(config.default_prompt) if hasattr(config, 'default_prompt') and \
                                                                 config.default_prompt != "" else ''


# def blocked_func(lock: threading.Lock):
#
#     def decorator(func):
#         def wrapper(*args, **kwargs):
#             print('lock acquire,{}'.format(lock))
#             lock.acquire()
#             try:
#                 return func(*args, **kwargs)
#             finally:
#                 lock.release()
#
#         return wrapper
#
#     return decorator


# 通用的OpenAI API交互session
# session内部保留了对话的上下文，
# 收到用户消息后，将上下文提交给OpenAI API生成回复
class Session:
    name = ''

    prompt = get_default_prompt()

    user_name = 'You'
    bot_name = 'Bot'

    create_timestamp = 0

    last_interact_timestamp = 0

    just_switched_to_exist_session = False

    response_lock = None

    # 加锁
    def acquire_response_lock(self):
        logging.debug('{},lock acquire,{}'.format(self.name, self.response_lock))
        self.response_lock.acquire()
        logging.debug('{},lock acquire successfully,{}'.format(self.name, self.response_lock))

    # 释放锁
    def release_response_lock(self):
        if self.response_lock.locked():
            logging.debug('{},lock release,{}'.format(self.name, self.response_lock))
            self.response_lock.release()
            logging.debug('{},lock release successfully,{}'.format(self.name, self.response_lock))

    def __init__(self, name: str):
        self.name = name
        self.create_timestamp = int(time.time())
        self.last_interact_timestamp = int(time.time())
        self.schedule()

        self.response_lock = threading.Lock()

    # 设定检查session最后一次对话是否超过过期时间的计时器
    def schedule(self):
        threading.Thread(target=self.expire_check_timer_loop, args=(self.create_timestamp,)).start()

    # 检查session是否已经过期
    def expire_check_timer_loop(self, create_timestamp: int):
        global sessions
        while True:
            time.sleep(60)

            # 不是此session已更换，退出
            if self.create_timestamp != create_timestamp or self not in sessions.values():
                return
            if int(time.time()) - self.last_interact_timestamp > config.session_expire_time:
                logging.info('session {} 已过期'.format(self.name))
                self.reset(expired=True, schedule_new=False)

                # 删除此session
                del sessions[self.name]
                return

    # 请求回复
    # 这个函数是阻塞的
    def append(self, text: str) -> str:
        self.last_interact_timestamp = int(time.time())

        max_rounds = config.prompt_submit_round_amount if hasattr(config, 'prompt_submit_round_amount') else 7
        max_length = config.prompt_submit_length if hasattr(config, "prompt_submit_length") else 1024

        # 向API请求补全
        response = pkg.openai.manager.get_inst().request_completion(self.cut_out(self.prompt + self.user_name + ':' +
                                                                                 text + '\n' + self.bot_name + ':',
                                                                                 max_rounds, max_length),
                                                                    self.user_name + ':')

        self.prompt += self.user_name + ':' + text + '\n' + self.bot_name + ':'
        # print(response)
        # 处理回复
        res_test = response["choices"][0]["text"]
        res_ans = res_test

        # 去除开头可能的提示
        res_ans_spt = res_test.split("\n\n")
        if len(res_ans_spt) > 1:
            del (res_ans_spt[0])
            res_ans = '\n\n'.join(res_ans_spt)

        self.prompt += "{}".format(res_ans) + '\n'

        if self.just_switched_to_exist_session:
            self.just_switched_to_exist_session = False
            self.set_ongoing()

        return res_ans

    # 从尾部截取prompt里不多于max_rounds个回合，长度不大于max_tokens的字符串
    # 保证都是完整的对话
    def cut_out(self, prompt: str, max_rounds: int, max_tokens: int) -> str:
        # 分隔出每个回合
        rounds_spt_by_user_name = prompt.split(self.user_name + ':')

        result = ''

        checked_rounds = 0
        # 从后往前遍历，加到result前面，检查result是否符合要求
        for i in range(len(rounds_spt_by_user_name) - 1, 0, -1):
            result_temp = self.user_name + ':' + rounds_spt_by_user_name[i] + result
            checked_rounds += 1

            if checked_rounds > max_rounds:
                break

            if int((len(result_temp.encode('utf-8')) - len(result_temp)) / 2 + len(result_temp)) > max_tokens:
                break

            result = result_temp

        logging.debug('cut_out: {}'.format(result))
        return result

    # 持久化session
    def persistence(self):
        if self.prompt == get_default_prompt():
            return

        db_inst = pkg.database.manager.get_inst()

        name_spt = self.name.split('_')

        subject_type = name_spt[0]
        subject_number = int(name_spt[1])

        db_inst.persistence_session(subject_type, subject_number, self.create_timestamp, self.last_interact_timestamp,
                                    self.prompt)

    # 重置session
    def reset(self, explicit: bool = False, expired: bool = False, schedule_new: bool = True):
        if self.prompt != get_default_prompt():
            self.persistence()
            if explicit:
                pkg.database.manager.get_inst().explicit_close_session(self.name, self.create_timestamp)

            if expired:
                pkg.database.manager.get_inst().set_session_expired(self.name, self.create_timestamp)
        self.prompt = get_default_prompt()
        self.create_timestamp = int(time.time())
        self.last_interact_timestamp = int(time.time())
        self.just_switched_to_exist_session = False

        # self.response_lock = threading.Lock()

        if schedule_new:
            self.schedule()

    # 将本session的数据库状态设置为on_going
    def set_ongoing(self):
        pkg.database.manager.get_inst().set_session_ongoing(self.name, self.create_timestamp)

    # 切换到上一个session
    def last_session(self):
        last_one = pkg.database.manager.get_inst().last_session(self.name, self.last_interact_timestamp)
        if last_one is None:
            return None
        else:
            self.persistence()

            self.create_timestamp = last_one['create_timestamp']
            self.last_interact_timestamp = last_one['last_interact_timestamp']
            self.prompt = last_one['prompt']

            self.just_switched_to_exist_session = True
            return self

    # 切换到下一个session
    def next_session(self):
        next_one = pkg.database.manager.get_inst().next_session(self.name, self.last_interact_timestamp)
        if next_one is None:
            return None
        else:
            self.persistence()

            self.create_timestamp = next_one['create_timestamp']
            self.last_interact_timestamp = next_one['last_interact_timestamp']
            self.prompt = next_one['prompt']

            self.just_switched_to_exist_session = True
            return self

    def list_history(self, capacity: int = 10, page: int = 0):
        return pkg.database.manager.get_inst().list_history(self.name, capacity, page,
                                                            (self.user_name + ":" + get_default_prompt() + "\n" +
                                                             self.bot_name + ":") if get_default_prompt() != "" else "")

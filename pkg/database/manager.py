import logging
import time
from sqlite3 import Cursor

from pymysql.converters import escape_string

import sqlite3

import config

inst = None

# 数据库管理
# 为其他模块提供数据库操作接口
class DatabaseManager:
    conn = None
    cursor = None

    def __init__(self):

        self.reconnect()

        global inst
        inst = self

    # 连接到数据库文件
    def reconnect(self):
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        # self.conn.isolation_level = None
        self.cursor = self.conn.cursor()

    def execute(self, sql: str) -> Cursor:
        c = self.cursor.execute(sql)
        logging.debug('SQL: {}'.format(sql))
        self.conn.commit()
        return c

    # 初始化数据库的函数
    def initialize_database(self):
        self.execute("""
        create table if not exists `sessions` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `name` varchar(255) not null,
            `type` varchar(255) not null,
            `number` bigint not null,
            `create_timestamp` bigint not null,
            `last_interact_timestamp` bigint not null,
            `status` varchar(255) not null default 'on_going',
            `prompt` text not null
        )
        """)
        print('Database initialized.')

    # session持久化
    def persistence_session(self, subject_type: str, subject_number: int, create_timestamp: int,
                            last_interact_timestamp: int, prompt: str):
        # 检查是否已经有了此name和create_timestamp的session
        # 如果有，就更新prompt和last_interact_timestamp
        # 如果没有，就插入一条新的记录
        self.execute("""
        select count(*) from `sessions` where `type` = '{}' and `number` = {} and `create_timestamp` = {}
        """.format(subject_type, subject_number, create_timestamp))
        count = self.cursor.fetchone()[0]
        if count == 0:
            self.execute("""
            insert into `sessions` (`name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`) 
            values ('{}', '{}', {}, {}, {}, '{}')
            """.format("{}_{}".format(subject_type, subject_number), subject_type, subject_number, create_timestamp,
                       last_interact_timestamp, escape_string(prompt)))
        else:
            self.execute("""
            update `sessions` set `last_interact_timestamp` = {}, `prompt` = '{}' 
            where `type` = '{}' and `number` = {} and `create_timestamp` = {}
            """.format(last_interact_timestamp, escape_string(prompt), subject_type,
                       subject_number, create_timestamp))

    # 显式关闭一个session
    def explicit_close_session(self, session_name: str, create_timestamp: int):
        self.execute("""
        update `sessions` set `status` = 'explicitly_closed' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    def set_session_ongoing(self, session_name: str, create_timestamp: int):
        self.execute("""
        update `sessions` set `status` = 'on_going' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    # 设置session为过期
    def set_session_expired(self, session_name: str, create_timestamp: int):
        self.execute("""
        update `sessions` set `status` = 'expired' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    # 从数据库加载还没过期的session数据
    def load_valid_sessions(self) -> dict:
        # 从数据库中加载所有还没过期的session
        self.execute("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`
        from `sessions` where `last_interact_timestamp` > {}
        """.format(int(time.time()) - config.session_expire_time))
        results = self.cursor.fetchall()
        sessions = {}
        for result in results:
            session_name = result[0]
            subject_type = result[1]
            subject_number = result[2]
            create_timestamp = result[3]
            last_interact_timestamp = result[4]
            prompt = result[5]
            status = result[6]

            # 当且仅当最后一个该对象的会话是on_going状态时，才会被加载
            if status == 'on_going':
                sessions[session_name] = {
                    'subject_type': subject_type,
                    'subject_number': subject_number,
                    'create_timestamp': create_timestamp,
                    'last_interact_timestamp': last_interact_timestamp,
                    'prompt': prompt
                }
            else:
                if session_name in sessions:
                    del sessions[session_name]

        return sessions

    # 获取此session_name前一个session的数据
    def last_session(self, session_name: str, cursor_timestamp: int):

        self.execute("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`
        from `sessions` where `name` = '{}' and `last_interact_timestamp` < {} order by `last_interact_timestamp` desc
        limit 1
        """.format(session_name, cursor_timestamp))
        results = self.cursor.fetchall()
        if len(results) == 0:
            return None
        result = results[0]

        session_name = result[0]
        subject_type = result[1]
        subject_number = result[2]
        create_timestamp = result[3]
        last_interact_timestamp = result[4]
        prompt = result[5]
        status = result[6]

        return {
            'subject_type': subject_type,
            'subject_number': subject_number,
            'create_timestamp': create_timestamp,
            'last_interact_timestamp': last_interact_timestamp,
            'prompt': prompt
        }

    # 获取此session_name后一个session的数据
    def next_session(self, session_name: str, cursor_timestamp: int):

        self.execute("""
            select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`
            from `sessions` where `name` = '{}' and `last_interact_timestamp` > {} order by `last_interact_timestamp` asc
            limit 1
            """.format(session_name, cursor_timestamp))
        results = self.cursor.fetchall()
        if len(results) == 0:
            return None
        result = results[0]

        session_name = result[0]
        subject_type = result[1]
        subject_number = result[2]
        create_timestamp = result[3]
        last_interact_timestamp = result[4]
        prompt = result[5]
        status = result[6]

        return {
            'subject_type': subject_type,
            'subject_number': subject_number,
            'create_timestamp': create_timestamp,
            'last_interact_timestamp': last_interact_timestamp,
            'prompt': prompt
        }

    # 列出与某个对象的所有对话session
    def list_history(self, session_name: str, capacity: int, page: int):
        self.execute("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`
        from `sessions` where `name` = '{}' order by `last_interact_timestamp` desc limit {} offset {}
        """.format(session_name, capacity, capacity * page))
        results = self.cursor.fetchall()
        sessions = []
        for result in results:
            session_name = result[0]
            subject_type = result[1]
            subject_number = result[2]
            create_timestamp = result[3]
            last_interact_timestamp = result[4]
            prompt = result[5]
            status = result[6]

            sessions.append({
                'subject_type': subject_type,
                'subject_number': subject_number,
                'create_timestamp': create_timestamp,
                'last_interact_timestamp': last_interact_timestamp,
                'prompt': prompt
            })

        return sessions


def get_inst() -> DatabaseManager:
    global inst
    return inst

import hashlib
import json
import logging
import time
from sqlite3 import Cursor

import sqlite3

import pkg.utils.context


# 数据库管理
# 为其他模块提供数据库操作接口
class DatabaseManager:
    conn = None
    cursor = None

    def __init__(self):

        self.reconnect()

        pkg.utils.context.set_database_manager(self)

    # 连接到数据库文件
    def reconnect(self):
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.close()

    def execute(self, *args, **kwargs) -> Cursor:
        # logging.debug('SQL: {}'.format(sql))
        c = self.cursor.execute(*args, **kwargs)
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

        # self.execute("""
        # create table if not exists `api_key_usage`(
        #     `id` INTEGER PRIMARY KEY AUTOINCREMENT,
        #     `key_md5` varchar(255) not null,
        #     `timestamp` bigint not null,
        #     `usage` bigint not null
        # )
        # """)

        self.execute("""
        create table if not exists `account_fee`(
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `key_md5` varchar(255) not null,
            `timestamp` bigint not null,
            `fee` DECIMAL(12,6) not null
        )
        """)

        self.execute("""
        create table if not exists `account_usage`(
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `json` text not null
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

            sql = """
            insert into `sessions` (`name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`) 
            values (?, ?, ?, ?, ?, ?)
            """

            self.execute(sql,
                         ("{}_{}".format(subject_type, subject_number), subject_type, subject_number, create_timestamp,
                          last_interact_timestamp, prompt))
        else:
            sql = """
            update `sessions` set `last_interact_timestamp` = ?, `prompt` = ? 
            where `type` = ? and `number` = ? and `create_timestamp` = ?
            """

            self.execute(sql, (last_interact_timestamp, prompt, subject_type,
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
        config = pkg.utils.context.get_config()
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
    def list_history(self, session_name: str, capacity: int, page: int, replace: str = ""):
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
                'prompt': prompt if replace == "" else prompt.replace(replace, "")
            })

        return sessions

    # 将apikey的使用量存进数据库
    def dump_api_key_usage(self, api_keys: dict, usage: dict):
        logging.debug('dumping api key usage...')
        logging.debug(api_keys)
        logging.debug(usage)
        for api_key in api_keys:
            # 计算key的md5值
            key_md5 = hashlib.md5(api_keys[api_key].encode('utf-8')).hexdigest()
            # 获取使用量
            usage_count = 0
            if key_md5 in usage:
                usage_count = usage[key_md5]
            # 将使用量存进数据库
            # 先检查是否已存在
            self.execute("""
            select count(*) from `api_key_usage` where `key_md5` = '{}'""".format(key_md5))
            result = self.cursor.fetchone()
            if result[0] == 0:
                # 不存在则插入
                self.execute("""
                insert into `api_key_usage` (`key_md5`, `usage`,`timestamp`) values ('{}', {}, {})
                """.format(key_md5, usage_count, int(time.time())))
            else:
                # 存在则更新，timestamp设置为当前
                self.execute("""
                update `api_key_usage` set `usage` = {}, `timestamp` = {} where `key_md5` = '{}'
                """.format(usage_count, int(time.time()), key_md5))

    def load_api_key_usage(self):
        self.execute("""
        select `key_md5`, `usage` from `api_key_usage`
        """)
        results = self.cursor.fetchall()
        usage = {}
        for result in results:
            key_md5 = result[0]
            usage_count = result[1]
            usage[key_md5] = usage_count
        return usage

    def dump_api_key_fee(self, api_keys: dict, fee: dict):
        logging.debug("dumping api key fee...")
        logging.debug(api_keys)
        logging.debug(fee)
        for api_key in api_keys:
            # 计算key的md5值
            key_md5 = hashlib.md5(api_keys[api_key].encode('utf-8')).hexdigest()
            # 获取使用量
            fee_count = 0
            if key_md5 in fee:
                fee_count = fee[key_md5]
            # 将使用量存进数据库
            # 先检查是否已存在
            self.execute("""
            select count(*) from `account_fee` where `key_md5` = '{}'""".format(key_md5))
            result = self.cursor.fetchone()
            if result[0] == 0:
                # 不存在则插入
                self.execute("""
                insert into `account_fee` (`key_md5`, `fee`,`timestamp`) values ('{}', {}, {})
                """.format(key_md5, fee_count, int(time.time())))
            else:
                # 存在则更新，timestamp设置为当前
                self.execute("""
                update `account_fee` set `fee` = {}, `timestamp` = {} where `key_md5` = '{}'
                """.format(fee_count, int(time.time()), key_md5))

    def load_api_key_fee(self):
        self.execute("""
        select `key_md5`, `fee` from `account_fee`
        """)
        results = self.cursor.fetchall()
        fee = {}
        for result in results:
            key_md5 = result[0]
            fee_count = result[1]
            fee[key_md5] = fee_count
        return fee

    def dump_usage_json(self, usage: dict):
        json_str = json.dumps(usage)
        self.execute("""
        select count(*) from `account_usage`""")
        result = self.cursor.fetchone()
        if result[0] == 0:
            # 不存在则插入
            self.execute("""
            insert into `account_usage` (`json`) values ('{}')
            """.format(json_str))
        else:
            # 存在则更新
            self.execute("""
            update `account_usage` set `json` = '{}' where `id` = 1
            """.format(json_str))

    def load_usage_json(self):
        self.execute("""
        select `json` from `account_usage` order by id desc limit 1
        """)
        result = self.cursor.fetchone()
        if result is None:
            return None
        else:
            return result[0]

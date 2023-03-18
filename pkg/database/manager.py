"""
数据库管理模块
"""
import hashlib
import json
import logging
import time
from sqlite3 import Cursor

import sqlite3

import pkg.utils.context


class DatabaseManager:
    """封装数据库底层操作，并提供方法给上层使用"""

    conn = None
    cursor = None

    def __init__(self):

        self.reconnect()

        pkg.utils.context.set_database_manager(self)

    # 连接到数据库文件
    def reconnect(self):
        """连接到数据库"""
        self.conn = sqlite3.connect('database.db', check_same_thread=False)
        self.cursor = self.conn.cursor()

    def close(self):
        self.conn.close()

    def __execute__(self, *args, **kwargs) -> Cursor:
        # logging.debug('SQL: {}'.format(sql))
        logging.debug('SQL: {}'.format(args))
        c = self.cursor.execute(*args, **kwargs)
        self.conn.commit()
        return c

    # 初始化数据库的函数
    def initialize_database(self):
        """创建数据表"""

        self.__execute__("""
        create table if not exists `sessions` (
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `name` varchar(255) not null,
            `type` varchar(255) not null,
            `number` bigint not null,
            `create_timestamp` bigint not null,
            `last_interact_timestamp` bigint not null,
            `status` varchar(255) not null default 'on_going',
            `default_prompt` text not null default '',
            `prompt` text not null,
            `token_counts` text not null default '[]'
        )
        """)

        # 检查sessions表是否存在`default_prompt`字段, 检查是否存在`token_counts`字段
        self.__execute__("PRAGMA table_info('sessions')")
        columns = self.cursor.fetchall()
        has_default_prompt = False
        has_token_counts = False
        for field in columns:
            if field[1] == 'default_prompt':
                has_default_prompt = True
            if field[1] == 'token_counts':
                has_token_counts = True
            if has_default_prompt and has_token_counts:
                break
        if not has_default_prompt:
            self.__execute__("alter table `sessions` add column `default_prompt` text not null default ''")
        if not has_token_counts:
            self.__execute__("alter table `sessions` add column `token_counts` text not null default '[]'")


        self.__execute__("""
        create table if not exists `account_fee`(
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `key_md5` varchar(255) not null,
            `timestamp` bigint not null,
            `fee` DECIMAL(12,6) not null
        )
        """)

        self.__execute__("""
        create table if not exists `account_usage`(
            `id` INTEGER PRIMARY KEY AUTOINCREMENT,
            `json` text not null
        )
        """)
        print('Database initialized.')

    # session持久化
    def persistence_session(self, subject_type: str, subject_number: int, create_timestamp: int,
                            last_interact_timestamp: int, prompt: str, default_prompt: str = '', token_counts: str = ''):
        """持久化指定session"""

        # 检查是否已经有了此name和create_timestamp的session
        # 如果有，就更新prompt和last_interact_timestamp
        # 如果没有，就插入一条新的记录
        self.__execute__("""
        select count(*) from `sessions` where `type` = '{}' and `number` = {} and `create_timestamp` = {}
        """.format(subject_type, subject_number, create_timestamp))
        count = self.cursor.fetchone()[0]
        if count == 0:

            sql = """
            insert into `sessions` (`name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `default_prompt`, `token_counts`) 
            values (?, ?, ?, ?, ?, ?, ?, ?)
            """

            self.__execute__(sql,
                             ("{}_{}".format(subject_type, subject_number), subject_type, subject_number, create_timestamp,
                          last_interact_timestamp, prompt, default_prompt, token_counts))
        else:
            sql = """
            update `sessions` set `last_interact_timestamp` = ?, `prompt` = ?, `token_counts` = ?
            where `type` = ? and `number` = ? and `create_timestamp` = ?
            """

            self.__execute__(sql, (last_interact_timestamp, prompt, token_counts, subject_type,
                                   subject_number, create_timestamp))

    # 显式关闭一个session
    def explicit_close_session(self, session_name: str, create_timestamp: int):
        self.__execute__("""
        update `sessions` set `status` = 'explicitly_closed' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    def set_session_ongoing(self, session_name: str, create_timestamp: int):
        self.__execute__("""
        update `sessions` set `status` = 'on_going' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    # 设置session为过期
    def set_session_expired(self, session_name: str, create_timestamp: int):
        self.__execute__("""
        update `sessions` set `status` = 'expired' where `name` = '{}' and `create_timestamp` = {}
        """.format(session_name, create_timestamp))

    # 从数据库加载还没过期的session数据
    def load_valid_sessions(self) -> dict:
        # 从数据库中加载所有还没过期的session
        config = pkg.utils.context.get_config()
        self.__execute__("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`, `default_prompt`, `token_counts`
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
            default_prompt = result[7]
            token_counts = result[8]

            # 当且仅当最后一个该对象的会话是on_going状态时，才会被加载
            if status == 'on_going':
                sessions[session_name] = {
                    'subject_type': subject_type,
                    'subject_number': subject_number,
                    'create_timestamp': create_timestamp,
                    'last_interact_timestamp': last_interact_timestamp,
                    'prompt': prompt,
                    'default_prompt': default_prompt,
                    'token_counts': token_counts
                }
            else:
                if session_name in sessions:
                    del sessions[session_name]

        return sessions

    # 获取此session_name前一个session的数据
    def last_session(self, session_name: str, cursor_timestamp: int):

        self.__execute__("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`, `default_prompt`, `token_counts`
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
        default_prompt = result[7]
        token_counts = result[8]

        return {
            'subject_type': subject_type,
            'subject_number': subject_number,
            'create_timestamp': create_timestamp,
            'last_interact_timestamp': last_interact_timestamp,
            'prompt': prompt,
            'default_prompt': default_prompt,
            'token_counts': token_counts
        }

    # 获取此session_name后一个session的数据
    def next_session(self, session_name: str, cursor_timestamp: int):

        self.__execute__("""
            select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`, `default_prompt`, `token_counts`
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
        default_prompt = result[7]
        token_counts = result[8]

        return {
            'subject_type': subject_type,
            'subject_number': subject_number,
            'create_timestamp': create_timestamp,
            'last_interact_timestamp': last_interact_timestamp,
            'prompt': prompt,
            'default_prompt': default_prompt,
            'token_counts': token_counts
        }

    # 列出与某个对象的所有对话session
    def list_history(self, session_name: str, capacity: int, page: int):
        self.__execute__("""
        select `name`, `type`, `number`, `create_timestamp`, `last_interact_timestamp`, `prompt`, `status`, `default_prompt`, `token_counts`
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
            default_prompt = result[7]
            token_counts = result[8]

            sessions.append({
                'subject_type': subject_type,
                'subject_number': subject_number,
                'create_timestamp': create_timestamp,
                'last_interact_timestamp': last_interact_timestamp,
                'prompt': prompt,
                'default_prompt': default_prompt,
                'token_counts': token_counts
            })

        return sessions

    def delete_history(self, session_name: str, index: int) -> bool:
        # 删除倒序第index个session
        # 查找其id再删除
        self.__execute__("""
        delete from `sessions` where `id` in (select `id` from `sessions` where `name` = '{}' order by `last_interact_timestamp` desc limit 1 offset {})
        """.format(session_name, index))

        return self.cursor.rowcount == 1

    def delete_all_history(self, session_name: str) -> bool:
        self.__execute__("""
        delete from `sessions` where `name` = '{}'
        """.format(session_name))
        return self.cursor.rowcount > 0

    def delete_all_session_history(self) -> bool:
        self.__execute__("""
        delete from `sessions`
        """)
        return self.cursor.rowcount > 0

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
            self.__execute__("""
            select count(*) from `api_key_usage` where `key_md5` = '{}'""".format(key_md5))
            result = self.cursor.fetchone()
            if result[0] == 0:
                # 不存在则插入
                self.__execute__("""
                insert into `api_key_usage` (`key_md5`, `usage`,`timestamp`) values ('{}', {}, {})
                """.format(key_md5, usage_count, int(time.time())))
            else:
                # 存在则更新，timestamp设置为当前
                self.__execute__("""
                update `api_key_usage` set `usage` = {}, `timestamp` = {} where `key_md5` = '{}'
                """.format(usage_count, int(time.time()), key_md5))

    def load_api_key_usage(self):
        self.__execute__("""
        select `key_md5`, `usage` from `api_key_usage`
        """)
        results = self.cursor.fetchall()
        usage = {}
        for result in results:
            key_md5 = result[0]
            usage_count = result[1]
            usage[key_md5] = usage_count
        return usage

    def dump_usage_json(self, usage: dict):

        json_str = json.dumps(usage)
        self.__execute__("""
        select count(*) from `account_usage`""")
        result = self.cursor.fetchone()
        if result[0] == 0:
            # 不存在则插入
            self.__execute__("""
            insert into `account_usage` (`json`) values ('{}')
            """.format(json_str))
        else:
            # 存在则更新
            self.__execute__("""
            update `account_usage` set `json` = '{}' where `id` = 1
            """.format(json_str))

    def load_usage_json(self):
        self.__execute__("""
        select `json` from `account_usage` order by id desc limit 1
        """)
        result = self.cursor.fetchone()
        if result is None:
            return None
        else:
            return result[0]

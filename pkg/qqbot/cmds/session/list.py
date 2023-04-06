from ..aamgr import AbstractCommandNode, Context
import datetime
import json


@AbstractCommandNode.register(
    parent=None,
    name='list',
    description='列出当前会话的所有历史记录',
    usage='!list\n!list [页数]',
    aliases=[],
    privilege=1
)
class ListCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import pkg.openai.session
        session_name = ctx.session_name
        params = ctx.params
        reply = []

        pkg.openai.session.get_session(session_name).persistence()
        page = 0

        if len(params) > 0:
            try:
                page = int(params[0])
            except ValueError:
                pass

        results = pkg.openai.session.get_session(session_name).list_history(page=page)
        if len(results) == 0:
            reply = ["[bot]第{}页没有历史会话".format(page)]
        else:
            reply_str = "[bot]历史会话 第{}页：\n".format(page)
            current = -1
            for i in range(len(results)):
                # 时间(使用create_timestamp转换) 序号 部分内容
                datetime_obj = datetime.datetime.fromtimestamp(results[i]['create_timestamp'])
                msg = ""
                try:
                    msg = json.loads(results[i]['prompt'])
                except json.decoder.JSONDecodeError:
                    msg = pkg.openai.session.reset_session_prompt(session_name, results[i]['prompt'])
                    # 持久化
                    pkg.openai.session.get_session(session_name).persistence()
                if len(msg) >= 2:
                    reply_str += "#{} 创建:{} {}\n".format(i + page * 10,
                                                        datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                        msg[0]['content'])
                else:
                    reply_str += "#{} 创建:{} {}\n".format(i + page * 10,
                                                        datetime_obj.strftime("%Y-%m-%d %H:%M:%S"),
                                                        "无内容")
                if results[i]['create_timestamp'] == pkg.openai.session.get_session(
                        session_name).create_timestamp:
                    current = i + page * 10

            reply_str += "\n以上信息倒序排列"
            if current != -1:
                reply_str += ",当前会话是 #{}\n".format(current)
            else:
                reply_str += ",当前处于全新会话或不在此页"

        reply = [reply_str]

        return True, reply
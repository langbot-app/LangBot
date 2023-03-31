from ..mgr import AbstractCommandNode, Context
import logging


@AbstractCommandNode.register(
    parent=None,
    name="usage",
    description="获取使用情况",
    usage="!usage",
    aliases=[],
    privilege=1
)
class UsageCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        import config
        import pkg.utils.credit as credit
        import pkg.utils.context

        reply = []

        reply_str = "[bot]各api-key使用情况:\n\n"

        api_keys = pkg.utils.context.get_openai_manager().key_mgr.api_key
        for key_name in api_keys:
            text_length = pkg.utils.context.get_openai_manager().audit_mgr \
                .get_text_length_of_key(api_keys[key_name])
            image_count = pkg.utils.context.get_openai_manager().audit_mgr \
                .get_image_count_of_key(api_keys[key_name])
            reply_str += "{}:\n - 文本长度:{}\n - 图片数量:{}\n".format(key_name, int(text_length),
                                                                        int(image_count))
            # 获取此key的额度
            try:
                http_proxy = config.openai_config["http_proxy"] if "http_proxy" in config.openai_config else None
                credit_data = credit.fetch_credit_data(api_keys[key_name], http_proxy)
                reply_str += " - 使用额度:{:.2f}/{:.2f}\n".format(credit_data['total_used'],credit_data['total_granted'])
            except Exception as e:
                logging.warning("获取额度失败:{}".format(e))

        reply = [reply_str]

        return True, reply
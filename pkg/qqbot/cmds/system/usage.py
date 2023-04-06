from ..aamgr import AbstractCommandNode, Context
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

        reply = [reply_str]

        return True, reply
from .. import aamgr
from ....utils import context


@aamgr.AbstractCommandNode.register(
    parent=None,
    name="default",
    description="操作情景预设",
    usage="!default\n!default set [指定情景预设为默认]",
    aliases=[],
    privilege=1
)
class DefaultCommand(aamgr.AbstractCommandNode):
    @classmethod
    def process(cls, ctx: aamgr.Context) -> tuple[bool, list]:
        import pkg.openai.session
        session_name = ctx.session_name
        params = ctx.params
        reply = []

        config = context.get_config_manager().data

        if len(params) == 0:
            # 输出目前所有情景预设
            import pkg.openai.dprompt as dprompt
            reply_str = "[bot]当前所有情景预设({}模式):\n\n".format(config['preset_mode'])

            prompts = dprompt.mode_inst().list()

            for key in prompts:
                pro = prompts[key]
                reply_str += "名称: {}".format(key)

                for r in pro:
                    reply_str += "\n   - [{}]: {}".format(r['role'], r['content'])

                reply_str += "\n\n"

            reply_str += "\n当前默认情景预设:{}\n".format(dprompt.mode_inst().get_using_name())
            reply_str += "请使用 !default set <情景预设名称> 来设置默认情景预设"
            reply = [reply_str]
        else:
            return False, []

        return True, reply


@aamgr.AbstractCommandNode.register(
    parent=DefaultCommand,
    name="set",
    description="设置默认情景预设",
    usage="!default set <情景预设名称>",
    aliases=[],
    privilege=2
)
class DefaultSetCommand(aamgr.AbstractCommandNode):
    @classmethod
    def process(cls, ctx: aamgr.Context) -> tuple[bool, list]:
        reply = []

        if len(ctx.crt_params) == 0:
            reply = ["[bot]err: 请指定情景预设名称"]
        elif len(ctx.crt_params) > 0:
            import pkg.openai.dprompt as dprompt
            try:
                full_name = dprompt.mode_inst().set_using_name(ctx.crt_params[0])
                reply = ["[bot]已设置默认情景预设为:{}".format(full_name)]
            except Exception as e:
                reply = ["[bot]err: {}".format(e)]

        return True, reply

from ..aamgr import AbstractCommandNode, Context
import json


def config_operation(cmd, params):
    reply = []
    import pkg.utils.context
    config = pkg.utils.context.get_config()
    reply_str = ""
    if len(params) == 0:
        reply = ["[bot]err:请输入配置项"]
    else:
        cfg_name = params[0]
        if cfg_name == 'all':
            reply_str = "[bot]所有配置项:\n\n"
            for cfg in dir(config):
                if not cfg.startswith('__') and not cfg == 'logging':
                    # 根据配置项类型进行格式化，如果是字典则转换为json并格式化
                    if isinstance(getattr(config, cfg), str):
                        reply_str += "{}: \"{}\"\n".format(cfg, getattr(config, cfg))
                    elif isinstance(getattr(config, cfg), dict):
                        # 不进行unicode转义，并格式化
                        reply_str += "{}: {}\n".format(cfg,
                                                       json.dumps(getattr(config, cfg),
                                                                  ensure_ascii=False, indent=4))
                    else:
                        reply_str += "{}: {}\n".format(cfg, getattr(config, cfg))
            reply = [reply_str]
        elif cfg_name in dir(config):
            if len(params) == 1:
                # 按照配置项类型进行格式化
                if isinstance(getattr(config, cfg_name), str):
                    reply_str = "[bot]配置项{}: \"{}\"\n".format(cfg_name, getattr(config, cfg_name))
                elif isinstance(getattr(config, cfg_name), dict):
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name,
                                                             json.dumps(getattr(config, cfg_name),
                                                                        ensure_ascii=False, indent=4))
                else:
                    reply_str = "[bot]配置项{}: {}\n".format(cfg_name, getattr(config, cfg_name))
                reply = [reply_str]
            else:
                cfg_value = " ".join(params[1:])
                # 类型转换，如果是json则转换为字典
                if cfg_value == 'true':
                    cfg_value = True
                elif cfg_value == 'false':
                    cfg_value = False
                elif cfg_value.isdigit():
                    cfg_value = int(cfg_value)
                elif cfg_value.startswith('{') and cfg_value.endswith('}'):
                    cfg_value = json.loads(cfg_value)
                else:
                    try:
                        cfg_value = float(cfg_value)
                    except ValueError:
                        pass

                # 检查类型是否匹配
                if isinstance(getattr(config, cfg_name), type(cfg_value)):
                    setattr(config, cfg_name, cfg_value)
                    pkg.utils.context.set_config(config)
                    reply = ["[bot]配置项{}修改成功".format(cfg_name)]
                else:
                    reply = ["[bot]err:配置项{}类型不匹配".format(cfg_name)]

        else:
            reply = ["[bot]err:未找到配置项 {}".format(cfg_name)]

    return reply


@AbstractCommandNode.register(
    parent=None,
    name="cfg",
    description="配置项管理",
    usage="!cfg <配置项> [配置值]\n!cfg all",
    aliases=[],
    privilege=2
)
class CfgCommand(AbstractCommandNode):
    @classmethod
    def process(cls, ctx: Context) -> tuple[bool, list]:
        return True, config_operation(ctx.command, ctx.params)

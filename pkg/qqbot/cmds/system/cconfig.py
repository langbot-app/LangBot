import json

from .. import aamgr


def config_operation(cmd, params):
    reply = []
    import pkg.utils.context
    # config = pkg.utils.context.get_config()
    cfg_mgr = pkg.utils.context.get_config_manager()

    false = False
    true = True

    reply_str = ""
    if len(params) == 0:
        reply = ["[bot]err:请输入!cmd cfg查看使用方法"]
    else:
        cfg_name = params[0]
        if cfg_name == 'all':
            reply_str = "[bot]所有配置项:\n\n"
            for cfg in cfg_mgr.data.keys():
                if not cfg.startswith('__') and not cfg == 'logging':
                    # 根据配置项类型进行格式化，如果是字典则转换为json并格式化
                    if isinstance(cfg_mgr.data[cfg], str):
                        reply_str += "{}: \"{}\"\n".format(cfg, cfg_mgr.data[cfg])
                    elif isinstance(cfg_mgr.data[cfg], dict):
                        # 不进行unicode转义，并格式化
                        reply_str += "{}: {}\n".format(cfg,
                                                       json.dumps(cfg_mgr.data[cfg],
                                                                  ensure_ascii=False, indent=4))
                    else:
                        reply_str += "{}: {}\n".format(cfg, cfg_mgr.data[cfg])
            reply = [reply_str]
        else:
            cfg_entry_path = cfg_name.split('.')

            try:
                if len(params) == 1:  # 未指定配置值，返回配置项值
                    cfg_entry = cfg_mgr.data[cfg_entry_path[0]]
                    if len(cfg_entry_path) > 1:
                        for i in range(1, len(cfg_entry_path)):
                            cfg_entry = cfg_entry[cfg_entry_path[i]]

                    if isinstance(cfg_entry, str):
                        reply_str = "[bot]配置项{}: \"{}\"\n".format(cfg_name, cfg_entry)
                    elif isinstance(cfg_entry, dict):
                        reply_str = "[bot]配置项{}: {}\n".format(cfg_name,
                                                                 json.dumps(cfg_entry,
                                                                            ensure_ascii=False, indent=4))
                    else:
                        reply_str = "[bot]配置项{}: {}\n".format(cfg_name, cfg_entry)
                    reply = [reply_str]
                else:
                    cfg_value = " ".join(params[1:])

                    cfg_value = eval(cfg_value)

                    cfg_entry = cfg_mgr.data[cfg_entry_path[0]]
                    if len(cfg_entry_path) > 1:
                        for i in range(1, len(cfg_entry_path) - 1):
                            cfg_entry = cfg_entry[cfg_entry_path[i]]
                        if isinstance(cfg_entry[cfg_entry_path[-1]], type(cfg_value)):
                            cfg_entry[cfg_entry_path[-1]] = cfg_value
                            reply = ["[bot]配置项{}修改成功".format(cfg_name)]
                        else:
                            reply = ["[bot]err:配置项{}类型不匹配".format(cfg_name)]
                    else:
                        cfg_mgr.data[cfg_entry_path[0]] = cfg_value
                        reply = ["[bot]配置项{}修改成功".format(cfg_name)]
            except KeyError:
                reply = ["[bot]err:未找到配置项 {}".format(cfg_name)]
            except NameError:
                reply = ["[bot]err:配置项{}值不合法（字符串需要使用双引号包裹）".format(cfg_name)]
            except ValueError:
                reply = ["[bot]err:未找到配置项 {}".format(cfg_name)]

    return reply


@aamgr.AbstractCommandNode.register(
    parent=None,
    name="cfg",
    description="配置项管理",
    usage="!cfg <配置项> [配置值]\n!cfg all",
    aliases=[],
    privilege=2
)
class CfgCommand(aamgr.AbstractCommandNode):
    @classmethod
    def process(cls, ctx: aamgr.Context) -> tuple[bool, list]:
        return True, config_operation(ctx.command, ctx.params)
    
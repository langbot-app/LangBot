import pkg.qqbot.cmds.aamgr as cmdsmgr
import json

# 执行命令模块的注册
cmdsmgr.register_all()

# 生成限权文件模板
template: dict[str, int] = {
    "comment": "以下为命令权限，请设置到cmdpriv.json中。关于此功能的说明，请查看：https://github.com/RockChinQ/QChatGPT/wiki/%E5%8A%9F%E8%83%BD%E4%BD%BF%E7%94%A8#%E5%91%BD%E4%BB%A4%E6%9D%83%E9%99%90%E6%8E%A7%E5%88%B6",
}

for key in cmdsmgr.__command_list__:
    template[key] = cmdsmgr.__command_list__[key]['privilege']

# 写入cmdpriv-template.json
with open('res/templates/cmdpriv-template.json', 'w') as f:
    f.write(json.dumps(template, indent=4, ensure_ascii=False))
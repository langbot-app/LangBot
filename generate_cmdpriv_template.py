import pkg.qqbot.cmds.mgr as cmdsmgr
import json

# 执行命令模块的注册
cmdsmgr.register_all()

# 生成限权文件模板
template: dict[str, int] = {
    "comment": "以下为命令权限，请设置到cmdpriv.json中: 1为所有用户可用，2为仅管理员可用。",
}

for key in cmdsmgr.__command_list__:
    template[key] = cmdsmgr.__command_list__[key]['privilege']

# 写入cmdpriv-template.json
with open('cmdpriv-template.json', 'w') as f:
    f.write(json.dumps(template, indent=4, ensure_ascii=False))
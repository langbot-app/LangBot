欢迎查看QChatGPT的Wiki页。

## 简介

调用OpenAI官方提供的API接口，结合mirai和YiriMirai框架，将QQ消息与语言模型连接，实现更加智能的对话机器人

## 技术栈

- [Mirai](https://github.com/mamoe/mirai) 高效率 QQ 机器人支持库
- [YiriMirai](https://github.com/YiriMiraiProject/YiriMirai) 一个轻量级、低耦合的基于 mirai-api-http 的 Python SDK。
- [go-cqhttp](https://github.com/Mrs4s/go-cqhttp) cqhttp的golang实现，轻量、原生跨平台.
- [nakuru-project](https://github.com/Lxns-Network/nakuru-project) - 一款为 go-cqhttp 的正向 WebSocket 设计的 Python SDK，支持纯 CQ 码与消息链的转换处理
- [nakuru-project-idk](https://github.com/idoknow/nakuru-project-idk) - 由idoknow维护的nakuru-project分支
- [dulwich](https://github.com/jelmer/dulwich) Pure-Python Git implementation
- [OpenAI API](https://openai.com/api/) OpenAI API

## 代码结构

- `pkg.database` 数据库操作相关
  - 数据库用于存放会话的历史记录，确保在程序重启后能记住对话内容
- `pkg.openai` OpenAI API相关
  - 用于调用OpenAI的API生成回复内容
- `pkg.qqbot` QQ机器人相关
  - 处理QQ收到的消息，调用API并进行回复
- `pkg.utils` 常用功能包
- `pkg.audit` 审计模块
- `pkg.plugin` 插件管理相关功能

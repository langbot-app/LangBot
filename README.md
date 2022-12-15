# QChatGPT

- 交流、答疑群: 204785790 
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
- QQ频道机器人见[QQChannelChatGPT](https://github.com/Soulter/QQChannelChatGPT)

通过调用OpenAI GPT-3模型提供的Completion API来实现一个更加智能的QQ机器人  

## 功能

以下是功能特色，点击展开查看具体使用方法

<details>
<summary>✅回复符合上下文</summary>

  - 程序向模型发送近几次对话内容，模型根据上下文生成回复
  - 您可在`config.py`中修改`prompt_submit_round_amount`及`process_message_timeout`自定义联系上下文的范围

</details>

<details>
<summary>✅支持敏感词过滤，避免账号风险</summary>

  - 难以监测机器人与用户对话时的内容，故引入此功能以减少机器人风险
  - 编辑`sensitive.json`，并在`config.py`中修改`sensitive_word_filter`的值以开启此功能
</details>

<details>
<summary>✅使用官方api，不需要网络代理，稳定快捷</summary>

  - 不使用ChatGPT逆向接口，而使用官方的Completion API，稳定性高
  - 您可以在`config.py`中自定义`completion_api_params`字段，设置向官方API提交的参数以自定义机器人的风格

</details>

<details>
<summary>✅完善的多api-key管理，超额自动切换</summary>

  - 支持配置多个`api-key`，内部统计使用量并在超额时自动切换
  - 请在`config.py`中修改`openai_config`的值以设置`api-key`
  - 可以在`config.py`中修改`api_key_usage_threshold`来自定义切换阈值
  - 运行期间向机器人说`!usage`以查看当前使用情况
</details>

<details>
<summary>✅组件少，部署方便，提供一键安装器</summary>

  - 手动部署步骤少
  - 提供自动安装器，详见以下安装步骤
</details>

<details>
<summary>✅支持预设指令文字</summary>

  - 支持以自然语言预设文字，自定义机器人人格等信息
  - 详见`config.py`中的`default_prompt`部分
</details>

<details>
<summary>✅完善的会话管理，重启不丢失</summary>

  - 使用SQLite进行会话内容持久化
  - 最后一次对话一定时间后自动保存，请到`config.py`中修改`session_expire_time`的值以自定义时间
  - 运行期间可使用`!reset` `!list` `!last` `!next` `!prompt`等指令管理会话
</details>

## 技术栈

- [Mirai](https://github.com/mamoe/mirai) 高效率 QQ 机器人支持库
- [YiriMirai](https://github.com/YiriMiraiProject/YiriMirai) 一个轻量级、低耦合的基于 mirai-api-http 的 Python SDK。
- [OpenAI API](https://openai.com/api/) OpenAI API

## 项目结构

- `pkg.database` 数据库操作相关
  - 数据库用于存放会话的历史记录，确保在程序重启后能记住对话内容
- `pkg.openai` OpenAI API相关
  - 用于调用OpenAI的API生成回复内容
- `pkg.qqbot` QQ机器人相关
  - 处理QQ收到的消息，调用API并进行回复

## 部署

**部署过程中遇到任何问题，请先在[QChatGPT](https://github.com/RockChinQ/QChatGPT/issues)或[qcg-installer](https://github.com/RockChinQ/qcg-installer/issues)的issue里进行搜索**

### 注册OpenAI账号

参考以下文章

> [只需 1 元搞定 ChatGPT 注册](https://zhuanlan.zhihu.com/p/589470082)  
> [手把手教你如何注册ChatGPT，超级详细](https://guxiaobei.com/51461)

注册成功后请前往[个人中心查看](https://beta.openai.com/account/api-keys)api_key  
完成注册后，使用以下自动化或手动部署步骤

### 自动化部署

使用[此安装器](https://github.com/RockChinQ/qcg-installer)（若无法访问请到[Gitee](https://gitee.com/RockChin/qcg-installer)）进行部署

- 此安装器目前仅支持部分平台，请到仓库文档查看，其他平台请手动部署

### 手动部署
<details>
<summary>手动部署适用于所有平台</summary>

- 请使用Python 3.9.x以上版本  
- 请注意OpenAI账号额度消耗  
  - 每个账户仅有18美元免费额度，如未绑定银行卡，则会在超出时报错  
  - OpenAI收费标准：默认使用的`text-davinci-003`模型 0.02美元/千字  

#### 配置Mirai

按照[此教程](https://yiri-mirai.wybxc.cc/tutorials/01/configuration)配置Mirai及YiriMirai  
启动mirai-console后，使用`login`命令登录QQ账号，保持mirai-console运行状态

#### 配置主程序

1. 克隆此项目

```bash
git clone https://github.com/RockChinQ/QChatGPT
cd QChatGPT
```

2. 安装依赖

```bash
pip3 install pymysql yiri-mirai openai colorlog func_timeout
```

3. 运行一次主程序，生成配置文件

```bash
python3 main.py
```

4. 编辑配置文件`config.py`

按照文件内注释填写配置信息

5. 运行主程序

```bash
python3 main.py
```

- 如提示安装`uvicorn`或`hypercorn`请*不要*安装，这两个不是必需的，目前存在未知原因bug
- 如报错`TypeError: As of 3.10, the *loop* parameter was removed from Lock() since it is no longer necessary`, 请参考 [此处](https://github.com/RockChinQ/QChatGPT/issues/5)

无报错信息即为运行成功

</details>

## 使用

### 私聊使用

1. 添加机器人QQ为好友
2. 发送消息给机器人，机器人即会自动回复
3. 可以通过`!help`查看帮助信息

<img alt="私聊示例" src="res/屏幕截图%202022-12-08%20150949.png" width="550" height="279"/>

### 群聊使用

1. 将机器人拉进群
2. at机器人并发送消息，机器人即会自动回复
3. at机器人并发送`!help`查看帮助信息

<img alt="群聊示例" src="res/屏幕截图%202022-12-08%20150511.png" width="671" height="522"/>

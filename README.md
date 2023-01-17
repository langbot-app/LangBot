# QChatGPT🤖

- 到[项目Wiki](https://github.com/RockChinQ/QChatGPT/wiki)可了解项目详细信息
- 由bilibili TheLazy制作的[视频教程](https://www.bilibili.com/video/BV15v4y1X7aP)
- 测试号: 2196084348
- 交流、答疑群: 204785790 
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
  - **进群提问前请您`确保`已经找遍文档和issue均无法解决**  
- QQ频道机器人见[QQChannelChatGPT](https://github.com/Soulter/QQChannelChatGPT)

通过调用OpenAI GPT-3模型提供的Completion API来实现一个更加智能的QQ机器人  

## ✅功能

查看[Wiki功能使用页](https://github.com/RockChinQ/QChatGPT/wiki/%E5%8A%9F%E8%83%BD%E4%BD%BF%E7%94%A8#%E5%8A%9F%E8%83%BD%E7%82%B9%E5%88%97%E4%B8%BE)

## 🔩部署

**部署过程中遇到任何问题，请先在[QChatGPT](https://github.com/RockChinQ/QChatGPT/issues)或[qcg-installer](https://github.com/RockChinQ/qcg-installer/issues)的issue里进行搜索**

### - 注册OpenAI账号

参考以下文章

> [只需 1 元搞定 ChatGPT 注册](https://zhuanlan.zhihu.com/p/589470082)  
> [手把手教你如何注册ChatGPT，超级详细](https://guxiaobei.com/51461)

注册成功后请前往[个人中心查看](https://beta.openai.com/account/api-keys)api_key  
完成注册后，使用以下自动化或手动部署步骤

### - 自动化部署

<details>
<summary>展开查看，以下方式二选一，Linux首选Docker，Windows首选安装器</summary>

#### Docker方式

请查看此仓库[mikumifa/QChatGPT-Docker-Installer](https://github.com/mikumifa/QChatGPT-Docker-Installer)

#### 安装器方式
使用[此安装器](https://github.com/RockChinQ/qcg-installer)（若无法访问请到[Gitee](https://gitee.com/RockChin/qcg-installer)）进行部署

- 安装器目前仅支持部分平台，请到仓库文档查看，其他平台请手动部署

</details>

### - 手动部署
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
pip3 install yiri-mirai openai colorlog func_timeout
pip3 install dulwich
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

无报错信息即为运行成功

**常见问题**

- mirai登录提示`QQ版本过低`，见[此issue](https://github.com/RockChinQ/QChatGPT/issues/38)
- 如提示安装`uvicorn`或`hypercorn`请*不要*安装，这两个不是必需的，目前存在未知原因bug
- 如报错`TypeError: As of 3.10, the *loop* parameter was removed from Lock() since it is no longer necessary`, 请参考 [此处](https://github.com/RockChinQ/QChatGPT/issues/5)

</details>

## 🚀使用

查看[Wiki功能使用页](https://github.com/RockChinQ/QChatGPT/wiki/%E5%8A%9F%E8%83%BD%E4%BD%BF%E7%94%A8#%E4%BD%BF%E7%94%A8%E6%96%B9%E5%BC%8F)

## 🧩插件生态

现已支持自行开发插件对功能进行扩展或自定义程序行为  
详见[Wiki插件使用页](https://github.com/RockChinQ/QChatGPT/wiki/%E6%8F%92%E4%BB%B6%E4%BD%BF%E7%94%A8)  
开发教程见[Wiki插件开发页](https://github.com/RockChinQ/QChatGPT/wiki/%E6%8F%92%E4%BB%B6%E5%BC%80%E5%8F%91)

### 示例插件

在`tests/plugin_examples`目录下，将其整个目录复制到`plugins`目录下即可使用

- `cmdcn` - 主程序指令中文形式
- `hello_plugin` - 在收到消息`hello`时回复相应消息
- `urlikethisijustsix` - 收到冒犯性消息时回复相应消息

### 更多

欢迎提交新的插件

- [hello_plugin](https://github.com/RockChinQ/hello_plugin) - `hello_plugin` 的储存库形式，插件开发模板

## 👍赞赏

<img alt="赞赏码" src="res/mm_reward_qrcode_1672840549070.png" width="400" height="400"/>
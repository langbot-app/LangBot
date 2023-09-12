# QChatGPT 容器化部署指南

> **Warning**  
> 请您确保您**确实**需要 Docker 部署，您**必须**具有以下能力：  
> - 了解 `Docker` 和 `Docker Compose` 的使用  
> - 了解容器间网络通信配置方式  
> - 了解容器文件挂载机制  
> - 了解容器调试操作
> - 动手能力强、资料查找能力强
>
> 若您不完全具有以上能力，请勿使用 Docker 部署，由于误操作导致的配置不正确，我们将不会解答您的问题并不负任何责任。  
> **非常不建议**您在除 Linux 之外的系统上使用 Docker 进行部署。

## 概览

QChatGPT 主程序需要连接`QQ登录框架`以与QQ通信，您可以选择 [Mirai](https://github.com/mamoe/mirai)（还需要配置mirai-api-http，请查看此仓库README中手动部署部分） 或 [go-cqhttp](https://github.com/Mrs4s/go-cqhttp)，我们仅发布 QChatGPT主程序 的镜像，您需要自行配置QQ登录框架（可以参考[README.md](https://github.com/RockChinQ/QChatGPT#-%E9%85%8D%E7%BD%AEqq%E7%99%BB%E5%BD%95%E6%A1%86%E6%9E%B6)中的教程，或自行寻找其镜像）并在 QChatGPT 的配置文件中设置连接地址。

> **Note**
> 请先确保 Docker 和 Docker Compose 已安装

## 准备文件

> QChatGPT 目前暂不可以在没有配置模板文件的情况下自动生成文件，您需要按照以下步骤手动创建需要挂载的文件。  
> 如无特殊说明，模板文件均在此仓库中。  

> 如果您不想挨个创建，也可以直接clone本仓库到本地，执行`python main.py`后即可自动根据模板生成所需文件。

现在请在一个空目录创建以下文件或目录：

### 📄`config.py`

复制根目录的`config-template.py`所有内容，创建`config.py`并根据其中注释进行修改。

### 📄`banlist.py`

复制`res/templates/banlist-template.py`所有内容，创建`banlist.py`，这是黑名单配置文件，根据需要修改。

### 📄`cmdpriv.json`

复制`res/templates/cmdpriv-template.json`所有内容，创建`cmdpriv.json`，这是各命令的权限配置文件，根据需要修改。

### 📄`sensitive.json`

复制`res/templates/sensitive-template.json`所有内容，创建`sensitive.json`，这是敏感词配置，根据需要修改。

### 📄`tips.py`

复制`tips-custom-template.py`所有内容，创建`tips.py`，这是部分提示语的配置，根据需要修改。

## 运行

已预先准备好`docker-compose.yaml`，您需要根据您的网络配置进行适当修改，使容器内的 QChatGPT 程序可以正常与 Mirai 或 go-cqhttp 通信。

将`docker-compose.yaml`复制到本目录，根据网络环境进行配置，并执行:

```bash
docker compose up
```

若无报错即配置完成，您可以Ctrl+C关闭后使用`docker compose up -d`将其置于后台运行

## 注意

- 安装的插件都会保存在`plugins`(映射到本目录`plugins`)，安装插件时可能会自动安装相应的依赖，此时若`重新创建`容器，已安装的插件将被加载，但所需的增量依赖并未安装，会导致引入问题。您可以删除插件目录后重启，再次安装插件，以便程序可以自动安装插件所需依赖。
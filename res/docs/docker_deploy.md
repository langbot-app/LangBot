
> **Warning**
> 此文档已过时，请查看[QChatGPT 容器化部署指南](docker_deployment.md)

## 操作步骤

### 1.安装docker和docker compose

[各种设备的安装Docker方法](https://yeasy.gitbook.io/docker_practice/install)

[安装Compose方法](https://yeasy.gitbook.io/docker_practice/compose)

> `Docker Desktop for Mac/Windows` 自带 `docker-compose` 二进制文件，安装 Docker 之后可以直接使用。
>
> 可以选择很多下载方法,反正只要安装了就可以了

### 2. 登录qq(下面所有步骤建议在项目文件夹下操作)

#### 2.1 输入指令

```
docker run -d -it --name mcl --network host -v ${PWD}/qq/plugins:/app/plugins -v ${PWD}/qq/config:/app/config -v   ${PWD}/qq/data:/app/data -v ${PWD}/qq/bots:/app/bots --restart unless-stopped kagurazakanyaa/mcl:latest
```

这里使用了[KagurazakaNyaa/mirai-console-loader-docker](https://github.com/KagurazakaNyaa/mirai-console-loader-docker)的镜像

#### 2.2 进入容器

```
docker ps
```
在输出中查看容器的ID，例如：
```sh
CONTAINER ID   IMAGE                COMMAND      CREATED          STATUS          PORTS                                       NAMES
bce1e5568f46   kagurazakanyaa/mcl   "./mcl -u"   10 minutes ago   Up 10 minutes   0.0.0.0:8080->8080/tcp, :::8080->8080/tcp   admiring_mendeleev
```
查看`IMAGE`名为`kagurazakanyaa/mcl`的容器的`CONTAINER ID`，在这里是`bce1e5568f46`，于是使用以下命令将其切到前台：
```
docker attach bce1e5568f46
```
如需将其切到后台运行，请使用组合键`Ctrl+P+Q`

#### 2.3 编写配置文件

- 在` /qq/config/net.mamoe.mirai-api-http` 文件夹中找到`setting.yml`，这是`mirai-api-http`的配置文件
  - 将这个文件的内容修改为：

```
adapters:
  - ws
debug: true
enableVerify: true
verifyKey: yirimirai
singleMode: false
cacheSize: 4096
adapterSettings:
  ws:
    host: localhost
    port: 8080
    reservedSyncId: -1
```

`verifyKey`要求与`bot`的`config.py`中的`verifyKey`相同

 `port`: 8080要和2.4 config.py配置里面的端口号相同

#### 2.4 登录

#### 在mirai上登录QQ

```
login <机器人QQ号> <机器人QQ密码>
```

> 具体见[此教程](https://yiri-mirai.wybxc.cc/tutorials/01/configuration#4-登录-qq)

#### 配置自动登录(可选)

当机器人账号登录成功以后，执行

```
autologin add <机器人QQ号> <机器人密码>
autologin setConfig <机器人QQ号> protocol ANDROID_PAD
```

> 出现`无法登录`报错时候[无法登录的临时处理方案](https://mirai.mamoe.net/topic/223/无法登录的临时处理方案)

**完成后, `Ctrl+P+Q`退出(不会关掉容器,容器还会运行)**

### 3. 部署QChatGPT

配置好config.py,保存到当前目录下,运行下面的

```
 docker run  -it -d --name QChatGPT   --network host   -v ${PWD}/config.py:/QChatGPT/config.py  -v ${PWD}/banlist.py:/QChatGPT/banlist.py  -v ${PWD}/sensitive.json:/QChatGPT/sensitive.json  mikumifa/qchatgpt-docker
```


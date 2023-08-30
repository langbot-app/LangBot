# 配置go-cqhttp用于登录QQ

> 若您是从旧版本升级到此版本以使用go-cqhttp的用户，请您按照`config-template.py`的内容修改`config.py`，添加`msg_source_adapter`配置项并将其设为`nakuru`，同时添加`nakuru_config`字段按照说明配置。

## 步骤

1. 从[go-cqhttp的Release](https://github.com/Mrs4s/go-cqhttp/releases/latest)下载最新的go-cqhttp可执行文件（建议直接下载可执行文件压缩包，而不是安装器）
2. 解压并运行，首次运行会询问需要开放的网络协议，**请填入`02`并回车，必须输入`02`❗❗❗❗❗❗❗**

<h1> 你这里必须得输入`02`，你懂么，`0`必须得输入，看好了，看好下面输入什么了吗？别他妈的搁那就输个`2`完了启动连不上还跑群里问，问一个我踢一个。 </h1>

```
C:\Softwares\go-cqhttp.old> .\go-cqhttp.exe
未找到配置文件，正在为您生成配置文件中！
请选择你需要的通信方式:
> 0: HTTP通信
> 1: 云函数服务
> 2: 正向 Websocket 通信
> 3: 反向 Websocket 通信
请输入你需要的编号(0-9)，可输入多个，同一编号也可输入多个(如: 233)
您的选择是:02
```
    
提示已生成`config.yml`文件，关闭go-cqhttp。

3. 打开go-cqhttp同目录的`config.yml`

    1. 编辑账号登录信息

        只需要修改下方`uin`和`password`为你要登录的机器人账号的QQ号和密码即可。  
        **若您不填写，将会在启动时请求扫码登录。**

        ```yaml
        account: # 账号相关
            uin: 1233456 # QQ账号
            password: '' # 密码为空时使用扫码登录
            encrypt: false  # 是否开启密码加密
            status: 0      # 在线状态 请参考 https://docs.go-cqhttp.org/guide/config.html#在线状态
            relogin: # 重连设置
                delay: 3   # 首次重连延迟, 单位秒
                interval: 3   # 重连间隔
                max-times: 0  # 最大重连次数, 0为无限制
        ```

    2. 修改websocket端口

        在`config.yml`下方找到以下内容

        ```yaml
          - ws:
            # 正向WS服务器监听地址
            address: 0.0.0.0:8080
            middlewares:
                <<: *default # 引用默认中间件
        ```

        **将`0.0.0.0:8080`改为`0.0.0.0:6700`**，保存并关闭`config.yml`。

    3. 若您的服务器位于公网，强烈建议您填写`access-token` (可选)

        ```yaml
        # 默认中间件锚点
        default-middlewares: &default
            # 访问密钥, 强烈推荐在公网的服务器设置
            access-token: ''
        ```

4. 配置完成，重新启动go-cqhttp

> 若启动后登录不成功，请尝试根据[此文档](https://docs.go-cqhttp.org/guide/config.html#%E8%AE%BE%E5%A4%87%E4%BF%A1%E6%81%AF)修改`device.json`的协议编号。

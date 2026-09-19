# Beta 适配器诊断开发说明

此诊断用于 4.11 适配器事件与 API 的 Beta 验收。仅受支持的 Beta 版本启用；稳定版、Alpha、RC、开发／本地标记版本以及关闭遥测或 Beta 诊断的实例不采集、不上传。

## 采集位置

- `pkg/platform/botmgr.py`：完成适配器事件监听器注册后产生能力快照。`listener_registered` 表示注册完成，不代表网络连接可用。
- 各适配器的 `_dispatch_eba_event`：调用 `diagnostics.adapter_event_received(self, event)`，记录一次事件已收到。必须位于调用监听器之前，避免路由、插件或模型失败改变接收事实。
- `pkg/telemetry/adapter_diagnostics.py`：识别适配器 API 最外层调用、平台专用 API 名、聊天与媒体类型。通过内部上下文标记抑制嵌套 API 重复计数。
- 转换失败无法可靠确定事件种类时，保留未知事件失败；转换成功本身不重复计算事件接收。

新增适配器或原生事件入口时，应检查事件是否经过统一分发入口。只在转换器上添加埋点不足以覆盖直接构造事件及交互回调。

## 数据约束

`adapter_evidence` 标记可用于验收的边界记录；`listener_registered` 标记注册事实；`chat_type`、`content_type` 仅允许有限类别。消息正文、API 参数、用户／群 ID、异常正文、媒体地址不进入这些字段。内部嵌套调用标记不得序列化。

平台专用动作优先匹配清单，名称为 `platform_api.<动作名>`；标准交互 API 保持其标准名称。未知动作不能借通用 `call_platform_api` 包装方法被计为已验收功能。清单读取显式使用 UTF-8，兼容 Windows 默认编码环境。

## 联动 Space

适配器清单或诊断操作变更后，同步生成 Space 的 `internal/diagnostics/catalog_v1.json`，并运行其目录一致性测试。Space 从清单生成完整矩阵，旧诊断记录不作为新增验收证据。部署时应先更新 Space 接收端与数据库迁移，再更新 Core Beta。

Core 回归命令：

```sh
uv run pytest tests/unit_tests/telemetry -q
```

重点测试在 `test_adapter_acceptance.py`：版本与开关、隐私、嵌套计数、专用／交互 API、分发入口覆盖、监听器失败。Space 仓库的 `docs/beta-adapter-acceptance.md` 说明验收界面、统计口径及联调方式。

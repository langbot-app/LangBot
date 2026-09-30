# Telemetry / 遥测

## 可选遥测

遥测默认开启。可以在实例 `data/config.yaml` 中将 `space.disable_telemetry` 改为 `true`，保留其他配置，然后重启实例。此开关关闭使用统计、实例心跳和功能执行遥测；Cloud 由实例运维方配置，对该实例所有工作区生效。遥测在后台尽力发送，网络故障、超时或服务端错误不会阻断正常操作；失败详情仅记录在 DEBUG 日志中。

## Optional telemetry

Telemetry is enabled by default. To opt out, set `space.disable_telemetry: true` in your instance’s `data/config.yaml`, preserve other settings, and restart the instance. This disables usage, heartbeat and execution telemetry. In Cloud, the instance operator controls this setting for every workspace in the instance. Delivery is best-effort in background tasks; connection failures, timeouts and server errors do not block normal operations. Failure details are logged only at DEBUG level.

## Configuration / 配置示例

```yaml
space:
  disable_telemetry: true
```

修改现有 `space` 节点，保留其他配置；不要创建重复的节点。恢复默认行为时，将此项改回 `false` 并重启实例。

Edit the existing `space` section and preserve other settings; do not create a duplicate section. To restore the default, set this option to `false` and restart the instance.

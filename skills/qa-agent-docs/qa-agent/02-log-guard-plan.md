# 日志守卫规划

## 状态

这是当前活跃设计，已有第一版文件扫描 MVP。实现边界需要和黑盒 E2E 路线保持一致：

- 日志守卫服务于 `lbs test report`。
- 它不替代浏览器/UI 判断。
- 它不发展成独立后端 API 测试框架。
- 第一版默认扫描 `LANGBOT_REPO/data/logs/` 下最新的 `langbot-*.log`，也可扫描 agent
  显式提供的 backend/frontend/console 日志文件。

当前总体路线见：

```text
docs/qa-agent/04-black-box-e2e-roadmap.md
```

## 目标

日志守卫是 `lbs test report` 的一部分，用来在 agent 执行测试期间捕获 UI 断言之外的运行时问题。

当前命令方向已收敛为 `lbs test plan` / `lbs test report`。日志守卫服务于 agent-browser QA，不是独立的后端 API 测试入口。

LangBot 是异步且集成度高的系统，有些问题不会直接表现为页面失败：

- 后台任务异常
- 未等待的协程
- Provider 流式调用失败
- 插件 runtime 超时
- 平台发送失败
- 数据库连接问题
- 敏感信息泄露

日志守卫负责把这些信号结构化地放进测试报告，并关联到 troubleshooting 资产。

## 输入

日志守卫应从环境和运行上下文读取配置：

- `skills/.env` 中的 `LANGBOT_BACKEND_URL`
- `skills/.env` 中的 `LANGBOT_REPO`，用于自动发现 LangBot 后端日志
- `lbs test plan` / report 记录的 case id
- LangBot 后端进程输出
- 前端 dev server 输出
- 浏览器 console/network 错误
- case 声明的 success/failure patterns 和 expected failures

## MVP 范围

- 读取一个或多个日志流或日志文件。
- 检测错误模式。
- 支持按 case id 或 pattern 白名单。
- 输出 JSON/Markdown 摘要。
- 发现非预期错误时让测试报告标记失败；未来如果有自动执行器，再返回非零退出码。

## 错误分类

### 永远非预期

除非 case 明确声明，否则应失败：

- `Traceback`
- `Task exception was never retrieved`
- `RuntimeWarning: coroutine .* was never awaited`
- `Unclosed client session`
- `Unclosed connector`
- `KeyError`
- `TypeError`
- `AttributeError`
- 密钥、token、secret 明文泄露

### Case 预期错误

只有当前 case 声明时允许：

- 无效 provider key
- Provider 认证失败
- 无效 webhook payload
- 插件测试故意抛错
- 超时测试
- 限流测试

### 仅警告

报告但默认不失败：

- 可恢复重试
- 恢复的超时
- 废弃配置
- 慢请求
- 版本检查失败

## 与 Troubleshooting 集成

日志守卫不只输出错误文本，还应尽量匹配已知 troubleshooting id。

例子：

```text
Action list_plugins call timed out
Action list_agent_runners call timed out
Action invoke_llm_stream call timed out
```

可映射到：

```text
plugin-runtime-timeout
```

```text
uppercase proxy points to one host, lowercase proxy points to another
```

可映射到：

```text
proxy-env-mismatch
```

## 未来命令

```bash
bin/lbs test plan pipeline-debug-chat
bin/lbs test start pipeline-debug-chat
bin/lbs test run pipeline-debug-chat --dry-run
bin/lbs test report pipeline-debug-chat
bin/lbs test report --output report.md
bin/lbs test report pipeline-debug-chat --backend-log /path/to/backend.log --console-log /path/to/console.log
bin/lbs test report pipeline-debug-chat --since "2026-05-21T10:30:00+08:00"
bin/lbs test report pipeline-debug-chat --tail-lines 2000
bin/lbs test report pipeline-debug-chat --since "2026-05-21T10:30:00+08:00" --tail-lines 2000
bin/lbs test report pipeline-debug-chat --no-auto-log
```

运行报告应包含：

- case id
- URL 和环境变量摘要，不能包含 secrets
- 浏览器可见结果
- 后端日志摘要
- console/network 错误
- 匹配到的 troubleshooting id
- 通过/失败结论

## MVP 完成标准

- 可以自动扫描最新 LangBot 后端日志，也可以扫描前端日志和 console 日志文件。
- 可以用 `--since` 或 `--tail-lines` 把扫描范围限制到本次测试窗口。
- 可以检测明显 Python/运行时错误和 secret 泄露风险。
- 可以识别 case 声明的 success/failure patterns。
- 可以识别 troubleshooting pattern，包括 `plugin-runtime-timeout` 和 `proxy-env-mismatch`。
- 支持 case 级白名单。
- 输出机器可读摘要。
- 至少一个 `langbot-testing` case 使用它。

当前 MVP 已覆盖自动发现 LangBot 后端日志、文件扫描、`--since`/`--tail-lines` 扫描窗口、
基础错误检测、case success/failure signal、troubleshooting 匹配、secret 脱敏和 `--json`
输出。仍待继续完善的是 live log 采集、更多规则、case 级 expected failure 的资产化和真实
E2E report 样例。

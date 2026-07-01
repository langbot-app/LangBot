# Schemas

这个目录存放 LangBot skills 结构化资产的 JSON Schema。

它们不是测试脚本，也不会执行浏览器动作。它们的作用是定义 agent 和维护者后续新增资产时应该遵守的文件结构。

## 文件说明

- `skills/<skill>/fixtures/fixtures.json`
  不是 JSON Schema，但由 `bin/lbs validate` 校验。
  它登记 deterministic fixture 文件、类型和关联 case，供 `bin/lbs fixture check` 做 readiness 检查。

- `case.schema.json`
  约束 `skills/<skill>/cases/*.yaml` 的格式。
  Case 描述 agent-browser 或 probe QA 路径，包括前置条件、步骤、检查点、诊断手段和关联故障。

- `suite.schema.json`
  约束 `skills/<skill>/suites/*.yaml` 的格式。
  Suite 只组织 case 集合，用于 smoke、regression 或 release gate 等测试入口。

- `troubleshooting.schema.json`
  约束 `skills/<skill>/troubleshooting/*.yaml` 的格式。
  Troubleshooting 条目描述症状、日志/错误模式、可能原因、修复步骤和验证信号。

- `skill-index.schema.json`
  约束生成文件 `skills.index.json` 的格式。
  这个索引用于让 agent 快速发现已有 skills、references、cases、suites 和 troubleshooting。

- `reports/evidence/<run-id>/result.json`
  不是 catalog schema，而是执行期最终裁定产物，由 `bin/lbs test result` 写入。
  `suite report` 读取其中的 `status`、`reason`、起止时间和 `evidence_collected`，
  并用 `evidence_missing` 防止缺证据的 `pass` 被当作完整通过。

- `reports/evidence/<run-id>/automation-result.json`
  不是 catalog schema，而是浏览器自动化脚本的原始运行结论，供 `bin/lbs test report`
  展示和推断日志扫描窗口。

## 为什么需要 schemas

Schemas 是基础设施护栏：

- 防止 case、suite 和 troubleshooting 随着增长变得格式混乱
- 让 `bin/lbs validate` 能发现缺字段和错误结构
- 为未来编辑器提示和 CI 校验留接口
- 帮助 agent 新增资产时知道应该写哪些字段

## 当前校验方式

`bin/lbs validate` 做轻量、schema 对齐的校验，不引入额外依赖。它会检查必填字段、
枚举值、boolean 字段、重复列表项、automation 脚本存在性，以及 case、suite、skill、
troubleshooting 之间的交叉引用。这里的 schema 仍是格式契约；如果未来引入正式 JSON
Schema validator，应继续保持这些本地交叉引用检查。

Case 里的 `env` / `automation_env` 表示所有列出的变量都需要配置。遇到二选一输入时，
使用 `env_any` / `automation_env_any`，每一项写成 `LANGBOT_PIPELINE_URL|LANGBOT_PIPELINE_NAME`
这类 one-of 组合，避免 agent 因为只配置了 URL 或 name 其中之一而误判未就绪。
`setup` 和 `preconditions` 是人工确认项，会让 readiness 进入 `manual_check`；
`setup_automation` 是 `test run` 可以自动执行的准备步骤，配合 `setup_provides_env`
声明它会生成的机器变量。

# WordFSRS — 在 IM 里背单词

基于 [FSRS 间隔重复算法](https://github.com/open-spaced-repetition/py-fsrs)（**墨墨背单词同款记忆模型**）的 LangBot 插件。在任意聊天里用 `!word` 命令建立自己的单词本，按科学的遗忘曲线复习。

[English](../README.md)

## 特性

- **FSRS 调度**：每张卡片用 `py-fsrs` 计算下一次复习时间，告别死板的固定间隔。
- **按会话隔离**：私聊和每个群各自拥有独立词库（key = `{launcher_type}:{launcher_id}`）。
- **每日新词上限**：可配置，避免一次涌入太多新词。
- **目标记忆保留率**：可配置 FSRS `desired_retention`（0.7–0.97）。

## 命令

| 命令 | 说明 |
|---|---|
| `!word add <单词> [释义]` | 添加单词 |
| `!word review` | 取出下一个到期/新词开始复习（别名 `next` `r`） |
| `!word show <单词>` | 查看释义（看答案，别名 `answer`） |
| `!word grade <单词> <1-4>` | 复习评分：1忘了 / 2难 / 3会 / 4简单（别名 `g` `rate`） |
| `!word stats` | 统计：总数/到期/新词/今日新词 |
| `!word list [页码]` | 列出词库（按下次复习时间排序，别名 `ls`） |
| `!word del <单词>` | 删除单词（别名 `rm` `delete`） |
| `!word help` | 帮助 |

评分也支持英文/中文别名：`again/hard/good/easy`、`忘了/难/会/简单`。

## 典型流程

```
!word add apple 苹果
!word add ephemeral 短暂的
!word review          → 取出一个词问你
!word grade apple 3   → 评“会”，FSRS 安排下次复习
!word stats           → 看进度
```

## 配置项

- `daily_new_limit`（默认 20）：每个会话每天最多引入的新卡数，0 = 不限。
- `desired_retention`（默认 0.9）：FSRS 目标回忆概率，越高复习越频繁。

## 数据存储

复习进度以 JSON 存入插件 KV 存储，key 为 `deck:{session_id}`。每张卡片保存完整的 FSRS 状态（`Card.to_dict()`），升级算法参数后仍可无损读取。

# 插件页面 (Plugin Pages)

插件可以注册自定义 HTML 页面，嵌入到 LangBot WebUI 的侧边栏中。页面运行在 iframe 内，通过 `postMessage` 与宿主通信，并可调用插件后端 API。

## 目录

- [注册页面](#注册页面)
- [页面 HTML 开发](#页面-html-开发)
- [JS SDK 参考](#js-sdk-参考)
- [后端 API 处理](#后端-api-处理)
- [通信协议](#通信协议)
- [暗黑模式适配](#暗黑模式适配)
- [i18n 国际化](#i18n-国际化)

---

## 注册页面

页面作为组件注册在 `components/pages/` 目录下，与 EventListener、Tool 等组件遵循相同的规范。

### manifest.yaml 配置

在 `spec.components` 中添加 `Page` 组件类型：

```yaml
spec:
  config: []
  components:
    EventListener:
      fromDirs:
      - path: components/event_listener/
    Page:
      fromDirs:
      - path: components/pages/
        maxDepth: 2
```

### 页面组件 YAML

每个页面有自己的 YAML 元数据文件（如 `dashboard.yaml`），格式与其他组件一致：

```yaml
apiVersion: v1
kind: Page
metadata:
  name: dashboard
  label:
    en_US: Demo Dashboard
    zh_Hans: 演示仪表盘
spec:
  path: index.html
```

- `kind` — 固定为 `Page`
- `metadata.name` — 页面唯一 ID，同一插件内不可重复
- `metadata.label` — 多语言显示名称，显示在 WebUI 侧边栏「插件扩展页」分组中
- `spec.path` — HTML 入口文件，相对于该 YAML 所在目录的路径

### 目录结构

```
MyPlugin/
├── manifest.yaml
├── main.py
├── README.md
├── assets/
│   └── icon.svg
├── components/
│   ├── event_listener/          # 事件监听器组件
│   │   ├── default.yaml
│   │   └── default.py
│   └── pages/                   # 页面组件
│       ├── dashboard/           # 第一个页面
│       │   ├── dashboard.yaml   # 页面元数据
│       │   ├── index.html       # 页面入口
│       │   └── i18n/            # 翻译文件
│       │       ├── en_US.json
│       │       └── zh_Hans.json
│       └── settings/            # 第二个页面
│           ├── settings.yaml
│           ├── index.html
│           └── i18n/
│               ├── en_US.json
│               └── zh_Hans.json
├── requirements.txt
└── config/
```

语言代码使用下划线分隔（如 `zh_Hans`、`en_US`、`ja_JP`），与 LangBot 多语言 README 规范一致。

当没有任何插件注册页面时，侧边栏的「插件扩展页」分组会自动隐藏。

---

## 页面 HTML 开发

在 HTML 文件中引入 JS SDK：

```html
<!DOCTYPE html>
<html>
<head>
  <meta charset="UTF-8">
  <style>
    body {
      background: var(--langbot-bg, #ffffff);
      color: var(--langbot-text, #0a0a0a);
    }
  </style>
</head>
<body>
  <!-- data-i18n 元素会被 SDK 自动翻译 -->
  <h1 data-i18n="title">My Page</h1>
  <p data-i18n="subtitle"></p>

  <script src="/api/v1/plugins/_sdk/page-sdk.js"></script>
  <script>
    langbot.onReady(function(ctx) {
      console.log('Theme:', ctx.theme);      // 'light' or 'dark'
      console.log('Language:', ctx.language); // 'zh-Hans', 'en-US', etc.
      console.log(langbot.t('title'));        // Translated string
    });
  </script>
</body>
</html>
```

> **注意**: SDK 的 `<script>` 标签必须放在使用 `langbot` 对象的代码之前。
> SDK 会自动从 `./i18n/{locale}.json` 加载翻译并应用到带有 `data-i18n` 属性的元素。

---

## JS SDK 参考

SDK 通过全局对象 `window.langbot` 暴露以下 API：

### 属性

| 属性 | 类型 | 说明 |
|------|------|------|
| `langbot.theme` | `string` | 当前主题，`'light'` 或 `'dark'` |
| `langbot.language` | `string` | 当前语言，如 `'zh-Hans'`、`'en-US'` |
| `langbot.ready` | `boolean` | SDK 是否已收到宿主的初始上下文 |

### 方法

#### `langbot.onReady(callback)`

注册初始化回调。SDK 收到宿主上下文并完成 i18n 加载后触发。若已就绪则立即执行。

```js
langbot.onReady(function(ctx) {
  // ctx.theme: 'light' | 'dark'
  // ctx.language: 'zh-Hans' | 'en-US' | ...
  // 此时 i18n 已加载，data-i18n 元素已翻译
});
```

#### `langbot.onThemeChange(callback)`

注册主题变更回调。每次用户切换主题时触发。

```js
langbot.onThemeChange(function(theme) {
  console.log('主题切换为:', theme);
});
```

#### `langbot.onLanguageChange(callback)`

注册语言变更回调。切换语言后触发（翻译已自动重新加载）。

```js
langbot.onLanguageChange(function(lang) {
  // data-i18n 元素已自动更新
  console.log('语言切换为:', lang);
});
```

#### `langbot.t(key, fallback?)`

获取翻译字符串。若 key 不存在则返回 fallback 或 key 本身。

```js
var title = langbot.t('title');                    // 翻译值
var text = langbot.t('missing.key', 'Default');   // 'Default'
```

#### `langbot.applyI18n()`

手动重新应用翻译到所有 `data-i18n` 元素。适用于动态添加 DOM 元素后。

```js
document.getElementById('list').innerHTML += '<li data-i18n="newItem">...</li>';
langbot.applyI18n();
```

#### `langbot.api(endpoint, body?, method?)`

调用插件后端的 `handle_page_api` 方法。返回 `Promise`。

| 参数 | 类型 | 默认值 | 说明 |
|------|------|--------|------|
| `endpoint` | `string` | — | API 端点路径，如 `'/counter/get'` |
| `body` | `any` | `undefined` | 请求体（会序列化为 JSON） |
| `method` | `string` | `'POST'` | HTTP 方法 |

```js
// GET 请求
const data = await langbot.api('/counter/get', null, 'GET');

// POST 请求
const result = await langbot.api('/counter/increment', { step: 1 });
```

---

## 后端 API 处理

在插件类中重写 `handle_page_api` 方法：

```python
from langbot_plugin import BasePlugin

class MyPlugin(BasePlugin):

    async def initialize(self):
        self.counter = 0

    async def handle_page_api(self, page_id: str, endpoint: str, method: str, body=None):
        """处理来自插件页面的 API 请求。

        Args:
            page_id:  页面 ID（manifest.yaml 中定义的 id）
            endpoint: 前端请求的端点路径
            method:   HTTP 方法 (GET/POST/PUT/DELETE)
            body:     请求体 (dict 或 None)

        Returns:
            任意可 JSON 序列化的数据，将作为响应返回给前端
        """
        if endpoint == '/counter/get':
            return {"count": self.counter}

        elif endpoint == '/counter/increment':
            step = (body or {}).get('step', 1)
            self.counter += step
            return {"count": self.counter}

        elif endpoint == '/counter/reset':
            self.counter = 0
            return {"count": 0}

        return {"error": "Unknown endpoint"}
```

`handle_page_api` 可在插件内的任何组件（事件处理器、工具等）中复用同一份状态，因为它们共享同一个插件实例。

---

## 通信协议

页面（iframe）与宿主（LangBot WebUI）之间通过 `postMessage` 通信，共有三种消息类型：

### 1. 上下文推送（宿主 → iframe）

宿主在 iframe 加载完成后和主题/语言变更时发送：

```
方向: Parent → iframe
```

```json
{
  "type": "langbot:context",
  "theme": "light",
  "language": "zh-Hans"
}
```

### 2. API 请求（iframe → 宿主）

页面通过 SDK 的 `langbot.api()` 发起请求：

```
方向: iframe → Parent
```

```json
{
  "type": "langbot:api",
  "requestId": "req_1_1712300000000",
  "endpoint": "/counter/get",
  "method": "GET",
  "body": null
}
```

### 3. API 响应（宿主 → iframe）

宿主将后端返回的数据或错误转发给 iframe：

```
方向: Parent → iframe
```

成功：
```json
{
  "type": "langbot:api:response",
  "requestId": "req_1_1712300000000",
  "data": { "count": 42 }
}
```

失败：
```json
{
  "type": "langbot:api:response",
  "requestId": "req_1_1712300000000",
  "error": "Unknown endpoint"
}
```

### 完整调用链

```
页面 JS (langbot.api)
  → postMessage (langbot:api)
    → page.tsx (PluginPageIframe)
      → httpClient.pluginPageApi()
        → POST /api/v1/plugins/{author}/{name}/page-api
          → LangBot handler
            → WebSocket (LangBotToRuntimeAction.PAGE_API)
              → Runtime control handler
                → WebSocket (RuntimeToPluginAction.PAGE_API)
                  → Plugin: handle_page_api()
  ← postMessage (langbot:api:response)
```

---

## 暗黑模式适配

SDK 会自动在 `<html>` 上设置以下 CSS 自定义属性，页面可直接使用：

| CSS Variable | Light | Dark | 用途 |
|---|---|---|---|
| `--langbot-bg` | `#ffffff` | `#0a0a0a` | 页面背景色 |
| `--langbot-bg-card` | `#f8fafc` | `#171717` | 卡片背景色 |
| `--langbot-text` | `#0a0a0a` | `#fafafa` | 主文字色 |
| `--langbot-text-muted` | `#71717a` | `#a1a1aa` | 次要文字色 |
| `--langbot-border` | `#e4e4e7` | `#27272a` | 边框色 |
| `--langbot-accent` | `#2563eb` | `#3b82f6` | 强调色 |

同时 `<html>` 元素会添加 `light` 或 `dark` class 和 `data-theme` 属性，方便使用 CSS 选择器：

```css
body {
  background: var(--langbot-bg);
  color: var(--langbot-text);
}

/* 或者使用 class 选择器 */
.dark body {
  background: #0a0a0a;
}
```

---

## i18n 国际化

SDK 内置了自动 i18n 支持，无需手动编写翻译加载逻辑。

### 翻译文件

在页面目录下创建 `i18n/` 目录，放入 JSON 翻译文件：

```
pages/dashboard/
├── index.html
└── i18n/
    ├── en_US.json      # 英文（回退语言）
    ├── zh_Hans.json    # 简体中文
    ├── zh_Hant.json    # 繁体中文
    └── ja_JP.json      # 日语
```

文件命名使用下划线：`{语言代码}.json`，与 LangBot 插件目录规范一致。

翻译文件格式为扁平 JSON 键值对：

```json
{
  "title": "仪表盘",
  "subtitle": "欢迎使用插件页面",
  "counter.increment": "+1",
  "counter.reset": "重置"
}
```

### 自动翻译

在 HTML 元素上添加 `data-i18n` 属性，SDK 会自动替换文本内容：

```html
<h1 data-i18n="title">Dashboard</h1>
<button data-i18n="counter.increment">+1</button>
```

需要翻译元素属性（如 `placeholder`）时，配合 `data-i18n-attr`：

```html
<input data-i18n="search.placeholder" data-i18n-attr="placeholder" placeholder="Search...">
```

### 编程式翻译

```js
// 获取翻译
var title = langbot.t('title');
var fallback = langbot.t('missing', 'Default Value');

// 语言变更时更新动态内容
langbot.onLanguageChange(function(lang) {
  updateDynamicContent();
});

// 动态添加元素后重新应用翻译
langbot.applyI18n();
```

### 语言回退

SDK 按以下顺序加载翻译：
1. 尝试加载 `i18n/{当前语言}.json`（如 `i18n/zh_Hans.json`）
2. 若不存在，回退到 `i18n/en_US.json`
3. 若均不存在，保持 HTML 中的原始文本

### 支持的语言代码

| 语言 | 代码 | 文件名 |
|------|------|--------|
| 英文 | en_US | en_US.json |
| 简体中文 | zh_Hans | zh_Hans.json |
| 繁体中文 | zh_Hant | zh_Hant.json |
| 日语 | ja_JP | ja_JP.json |
| 韩语 | ko_KR | ko_KR.json |
| 越南语 | vi_VN | vi_VN.json |

---

## iframe 安全

iframe 使用 `sandbox` 属性限制权限：

```
sandbox="allow-scripts allow-forms"
```

- `allow-scripts` — 允许执行 JavaScript
- `allow-forms` — 允许提交表单

不允许弹窗、导航等操作，确保插件页面在受控环境中运行。

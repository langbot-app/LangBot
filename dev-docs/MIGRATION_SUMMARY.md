# WebChat 到 WebSocket 迁移总结

## 概述

已完全移除旧的基于SSE的WebChat系统，并替换为基于WebSocket的双向实时通信系统。这是一个内置在LangBot中的完整IM系统，支持流式输出。

## 已删除的文件

### 后端
- ❌ `src/langbot/pkg/api/http/controller/groups/pipelines/webchat.py` - 旧的SSE路由
- ❌ `src/langbot/pkg/platform/sources/webchat.py` - 旧的WebChat适配器
- ❌ `src/langbot/pkg/platform/sources/webchat.yaml` - 旧的配置文件

### 前端
- ❌ BackendClient中所有SSE相关代码已完全移除
- ❌ DebugDialog中所有SSE相关逻辑已完全替换

## 新增的文件

### 后端核心文件

**1. WebSocket连接管理器**
```
src/langbot/pkg/platform/sources/websocket_manager.py
```
- 管理所有并发WebSocket连接
- 线程安全的连接池
- 按流水线、会话类型分组
- 广播和单播消息功能
- 连接统计和监控

**2. WebSocket适配器**
```
src/langbot/pkg/platform/sources/websocket_adapter.py
```
- 实现平台适配器接口
- **完整流式支持** (`reply_message_chunk` 方法)
- 双向消息流处理
- 消息历史管理
- 会话管理

**3. WebSocket路由控制器**
```
src/langbot/pkg/api/http/controller/groups/pipelines/websocket_chat.py
```
- WebSocket端点处理
- REST API接口
- 心跳机制
- 连接生命周期管理

**4. 配置文件**
```
src/langbot/pkg/platform/sources/websocket.yaml
```
- WebSocket适配器元数据

### 前端核心文件

**1. WebSocket客户端**
```
web/src/app/infra/websocket/WebSocketClient.ts
```
- WebSocket连接管理
- 自动重连（最多5次）
- 心跳机制（30秒）
- 事件回调系统

**2. 更新的组件**
```
web/src/app/home/pipelines/components/debug-dialog/DebugDialog.tsx
```
- 完全重写，使用WebSocket
- 实时连接状态显示
- 流式消息支持
- 自动重连

**3. HTTP客户端更新**
```
web/src/app/infra/http/BackendClient.ts
```
- 移除所有旧的WebChat API
- 仅保留WebSocket API

### 测试工具

**Python测试客户端**
```
test_websocket_client.py
```
- 单连接交互测试
- 多连接并发测试
- 命令行工具

### 文档

**使用文档**
```
WEBSOCKET_README.md
```
- 完整的API文档
- 架构说明
- 使用示例
- 故障排查

## 核心变更

### 后端变更

**1. botmgr.py**
- ❌ 移除 `webchat_proxy_bot`
- ✅ 仅保留 `websocket_proxy_bot`
- ✅ 更新适配器过滤逻辑（排除`websocket`而非`webchat`）

**2. 适配器注册**
```python
# 旧代码（已删除）
webchat_adapter_class = self.adapter_dict['webchat']
self.webchat_proxy_bot = RuntimeBot(...)

# 新代码
websocket_adapter_class = self.adapter_dict['websocket']
self.websocket_proxy_bot = RuntimeBot(
    uuid='websocket-proxy-bot',
    name='WebSocket',
    adapter='websocket',
    ...
)
```

### 前端变更

**1. API调用完全更换**

旧代码（已删除）:
```typescript
// SSE流式请求
await fetch(url, {
  method: 'POST',
  body: JSON.stringify({ is_stream: true })
})
// 手动解析 text/event-stream
```

新代码:
```typescript
// WebSocket实时通信
const wsClient = new WebSocketClient(pipelineId, sessionType);
await wsClient.connect();

wsClient.onMessage((message) => {
  // 流式消息自动处理
  setMessages(prev => [...prev, message]);
});

wsClient.sendMessage(messageChain);
```

**2. 连接状态管理**

新增功能:
- ✅ 实时连接状态指示器（绿色/红色圆点）
- ✅ 连接/断开toast提示
- ✅ 自动重连逻辑
- ✅ 心跳保活

**3. 流式支持**

完整的流式消息处理:
```typescript
wsClient.onMessage((message) => {
  if (message.is_final) {
    // 最终消息
    finalizeBotMessage(message);
  } else {
    // 中间消息块，实时更新UI
    updateBotMessage(message);
  }
});
```

## API对比

### WebSocket端点

**连接**
```
ws://localhost:8000/api/v1/pipelines/<pipeline_uuid>/ws/connect?session_type=<person|group>
```

**消息格式**

客户端发送:
```json
{
  "type": "message",
  "message": [
    {"type": "Plain", "text": "你好"}
  ]
}
```

服务器响应（流式）:
```json
{
  "type": "response",
  "data": {
    "id": 1,
    "role": "assistant",
    "content": "你好，我是...",
    "is_final": false,
    "timestamp": "2025-01-28T..."
  }
}
```

### REST API

| 端点 | 方法 | 说明 |
|------|------|------|
| `/api/v1/pipelines/<uuid>/ws/messages/<type>` | GET | 获取消息历史 |
| `/api/v1/pipelines/<uuid>/ws/reset/<type>` | POST | 重置会话 |
| `/api/v1/pipelines/<uuid>/ws/connections` | GET | 获取连接统计 |
| `/api/v1/pipelines/<uuid>/ws/broadcast` | POST | 广播消息 |

## 流式支持详解

### 后端流式实现

**WebSocket Adapter**
```python
async def reply_message_chunk(
    self,
    message_source: platform_events.MessageEvent,
    bot_message,
    message: platform_message.MessageChain,
    quote_origin: bool = False,
    is_final: bool = False,
) -> dict:
    """回复消息块 - 流式"""
    message_data = WebSocketMessage(
        id=-1,
        role='assistant',
        content=str(message),
        message_chain=[component.__dict__ for component in message],
        timestamp=datetime.now().isoformat(),
        is_final=is_final and bot_message.tool_calls is None,
    )

    # 发送到队列，由WebSocket连接处理发送
    await session.resp_queues[message_id].put(message_data)
    return message_data.model_dump()

async def is_stream_output_supported(self) -> bool:
    """WebSocket始终支持流式输出"""
    return True
```

### 前端流式处理

**DebugDialog组件**
```typescript
wsClient.onMessage((message) => {
  setMessages((prevMessages) => {
    const existingIndex = prevMessages.findIndex(
      (msg) => msg.role === 'assistant' && msg.content === 'Generating...'
    );

    if (existingIndex !== -1) {
      // 更新正在生成的消息
      const updatedMessages = [...prevMessages];
      updatedMessages[existingIndex] = message;
      return updatedMessages;
    } else {
      // 添加新消息
      return [...prevMessages, message];
    }
  });
});
```

## 兼容性说明

### ⚠️ 不兼容旧版本

此次迁移**完全不兼容**旧的WebChat系统：

1. **API端点变更**
   - 旧: `/api/v1/pipelines/<uuid>/chat/send`
   - 新: `ws://.../<uuid>/ws/connect`

2. **通信协议变更**
   - 旧: HTTP + SSE (Server-Sent Events)
   - 新: WebSocket (双向)

3. **流式实现变更**
   - 旧: `text/event-stream` 格式
   - 新: WebSocket JSON消息

### 迁移要求

使用新系统需要:
1. ✅ 前端必须支持WebSocket
2. ✅ 后端必须运行新的WebSocket适配器
3. ✅ 清除旧的WebChat相关配置

## 优势对比

| 特性 | 旧WebChat (SSE) | 新WebSocket |
|------|----------------|-------------|
| 双向通信 | ❌ 单向（服务器→客户端） | ✅ 双向 |
| 主动推送 | ❌ 不支持 | ✅ 支持 |
| 连接管理 | ❌ 无状态 | ✅ 有状态，完整生命周期 |
| 流式输出 | ✅ 支持 | ✅ 支持（更优） |
| 心跳机制 | ❌ 无 | ✅ 30秒心跳 |
| 自动重连 | ❌ 无 | ✅ 最多5次 |
| 多连接 | ⚠️ 难以管理 | ✅ 完整支持 |
| 连接状态 | ❌ 不可见 | ✅ 实时显示 |
| 广播功能 | ❌ 不支持 | ✅ 支持 |

## 测试方式

### 1. Python测试客户端

```bash
# 单连接测试
python test_websocket_client.py <pipeline_uuid>

# 指定会话类型
python test_websocket_client.py <pipeline_uuid> --session-type group

# 多连接并发测试（5个连接）
python test_websocket_client.py <pipeline_uuid> --multi 5
```

### 2. 前端测试

1. 启动LangBot服务器
2. 访问前端界面
3. 打开流水线调试对话框
4. 观察连接状态指示器（左下角圆点）
5. 发送消息测试流式响应

### 3. 浏览器控制台测试

```javascript
const ws = new WebSocket('ws://localhost:8000/api/v1/pipelines/<uuid>/ws/connect?session_type=person');

ws.onopen = () => {
  console.log('已连接');
  ws.send(JSON.stringify({
    type: 'message',
    message: [{type: 'Plain', text: '你好'}]
  }));
};

ws.onmessage = (event) => {
  console.log('收到:', JSON.parse(event.data));
};
```

## 常见问题

### Q: 为什么完全删除旧代码而不保留兼容性？
A: 根据需求，不需要考虑任何对老版本的兼容性，彻底迁移可以避免代码冗余和维护负担。

### Q: 流式输出如何工作？
A:
1. 后端通过`reply_message_chunk`发送消息块
2. 消息块放入队列
3. WebSocket连接从队列取出并发送
4. 前端实时更新UI
5. `is_final=true`表示最后一块

### Q: 如何确保连接不断开？
A:
1. 客户端每30秒发送心跳（ping）
2. 服务器响应pong
3. 连接断开时自动重连（最多5次）

### Q: 如何实现后端主动推送？
A:
1. 调用 `/api/v1/pipelines/<uuid>/ws/broadcast` API
2. 消息会被推送到该流水线的所有连接
3. 前端通过`onBroadcast`回调接收

## 总结

✅ **完成的工作**
- 完全移除旧的WebChat/SSE系统
- 实现完整的WebSocket双向通信系统
- 支持流式输出
- 支持多连接并发
- 实现自动重连和心跳机制
- 提供完整的测试工具和文档

✅ **核心特性**
- 双向实时通信
- 流式消息支持
- 多连接管理
- 自动重连
- 心跳保活
- 连接状态可视化
- 广播消息

✅ **技术亮点**
- 异步架构（asyncio）
- 线程安全的连接管理
- 独立的消息队列
- 完整的错误处理
- 模块化设计

🎉 系统已完全迁移到WebSocket，无任何旧代码遗留！

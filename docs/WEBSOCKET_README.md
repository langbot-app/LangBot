# LangBot WebSocket 双向通信系统

## 概述

这是一个内置在 LangBot 中的完整 IM (即时通讯) 系统，支持：

- ✅ WebSocket 双向实时通信
- ✅ 多个客户端并发连接
- ✅ 前端到后端的消息发送
- ✅ 后端到前端的主动推送
- ✅ 流式响应支持
- ✅ 连接管理和会话隔离
- ✅ 心跳机制
- ✅ 广播消息功能

## 架构设计

### 核心组件

1. **WebSocketConnectionManager** (`websocket_manager.py`)
   - 管理所有活跃的 WebSocket 连接
   - 支持按流水线、会话类型查询连接
   - 提供广播和单播功能
   - 线程安全的并发访问控制

2. **WebSocketAdapter** (`websocket_adapter.py`)
   - 实现平台适配器接口
   - 处理消息的接收和发送
   - 支持流式输出
   - 管理消息历史

3. **WebSocketChatRouterGroup** (`websocket_chat.py`)
   - WebSocket 路由控制器
   - 处理连接建立、消息收发
   - 实现心跳机制
   - 提供 REST API 接口

## API 接口

### WebSocket 连接

#### 建立连接

```
ws://localhost:8000/api/v1/pipelines/<pipeline_uuid>/ws/connect?session_type=<person|group>
```

**参数:**
- `pipeline_uuid`: 流水线 UUID (必需)
- `session_type`: 会话类型，可选 `person` 或 `group` (默认: `person`)

**连接成功响应:**
```json
{
  "type": "connected",
  "connection_id": "550e8400-e29b-41d4-a716-446655440000",
  "pipeline_uuid": "your-pipeline-uuid",
  "session_type": "person",
  "timestamp": "2025-01-28T12:00:00"
}
```

### 消息格式

#### 客户端发送消息

**发送聊天消息:**
```json
{
  "type": "message",
  "message": [
    {
      "type": "Plain",
      "text": "你好，这是一条测试消息"
    }
  ]
}
```

**发送心跳:**
```json
{
  "type": "ping"
}
```

**主动断开连接:**
```json
{
  "type": "disconnect"
}
```

#### 服务器响应消息

**聊天响应 (流式):**
```json
{
  "type": "response",
  "data": {
    "id": 1,
    "role": "assistant",
    "content": "这是机器人的回复",
    "message_chain": [...],
    "timestamp": "2025-01-28T12:00:00",
    "is_final": false,
    "connection_id": "..."
  }
}
```

**心跳响应:**
```json
{
  "type": "pong",
  "timestamp": "2025-01-28T12:00:00"
}
```

**广播消息:**
```json
{
  "type": "broadcast",
  "message": "这是一条广播消息",
  "timestamp": "2025-01-28T12:00:00"
}
```

**错误消息:**
```json
{
  "type": "error",
  "message": "错误描述"
}
```

### REST API 接口

#### 1. 获取消息历史

```http
GET /api/v1/pipelines/<pipeline_uuid>/ws/messages/<session_type>
```

**响应:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "messages": [...]
  }
}
```

#### 2. 重置会话

```http
POST /api/v1/pipelines/<pipeline_uuid>/ws/reset/<session_type>
```

**响应:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "message": "Session reset successfully"
  }
}
```

#### 3. 获取连接统计

```http
GET /api/v1/pipelines/<pipeline_uuid>/ws/connections
```

**响应:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "stats": {
      "total_connections": 5,
      "pipelines": 2,
      "connections_by_pipeline": {
        "pipeline-1": 3,
        "pipeline-2": 2
      },
      "connections_by_session_type": {
        "person": 4,
        "group": 1
      }
    },
    "connections": [
      {
        "connection_id": "...",
        "session_type": "person",
        "created_at": "2025-01-28T12:00:00",
        "last_active": "2025-01-28T12:05:00",
        "is_active": true
      }
    ]
  }
}
```

#### 4. 广播消息 (后端主动推送)

```http
POST /api/v1/pipelines/<pipeline_uuid>/ws/broadcast
Content-Type: application/json

{
  "message": "这是一条广播消息"
}
```

**响应:**
```json
{
  "code": 0,
  "msg": "ok",
  "data": {
    "message": "Broadcast sent successfully"
  }
}
```

## 使用示例

### Python 客户端示例

使用提供的测试客户端：

```bash
# 安装依赖
pip install websockets

# 单个连接测试
python test_websocket_client.py <pipeline_uuid>

# 指定会话类型
python test_websocket_client.py <pipeline_uuid> --session-type group

# 多连接并发测试
python test_websocket_client.py <pipeline_uuid> --multi 5
```

### JavaScript 客户端示例

```javascript
// 建立 WebSocket 连接
const ws = new WebSocket('ws://localhost:8000/api/v1/pipelines/your-pipeline-uuid/ws/connect?session_type=person');

// 连接建立
ws.onopen = () => {
  console.log('WebSocket 连接已建立');

  // 发送消息
  ws.send(JSON.stringify({
    type: 'message',
    message: [
      {
        type: 'Plain',
        text: '你好'
      }
    ]
  }));
};

// 接收消息
ws.onmessage = (event) => {
  const data = JSON.parse(event.data);

  if (data.type === 'connected') {
    console.log('连接成功:', data.connection_id);
  } else if (data.type === 'response') {
    console.log('机器人回复:', data.data.content);
    if (data.data.is_final) {
      console.log('响应完成');
    }
  } else if (data.type === 'broadcast') {
    console.log('收到广播:', data.message);
  }
};

// 连接关闭
ws.onclose = () => {
  console.log('WebSocket 连接已关闭');
};

// 错误处理
ws.onerror = (error) => {
  console.error('WebSocket 错误:', error);
};

// 发送心跳
setInterval(() => {
  if (ws.readyState === WebSocket.OPEN) {
    ws.send(JSON.stringify({ type: 'ping' }));
  }
}, 30000); // 每 30 秒发送一次心跳
```

## 特性说明

### 1. 多连接支持

系统支持同时建立多个 WebSocket 连接，每个连接都有唯一的 `connection_id`。连接按照流水线和会话类型进行分组管理。

### 2. 双向通信

- **前端 → 后端**: 客户端可以主动发送消息给服务器
- **后端 → 前端**: 服务器可以通过广播 API 主动推送消息给客户端

### 3. 流式响应

支持流式输出，机器人的响应会分块发送，客户端可以实时显示部分响应内容。

### 4. 会话隔离

支持 `person` 和 `group` 两种会话类型，不同类型的会话消息历史互不影响。

### 5. 连接管理

- 自动追踪连接状态
- 记录最后活跃时间
- 支持连接统计查询
- 连接断开时自动清理资源

### 6. 心跳机制

客户端可以定期发送 `ping` 消息，服务器会响应 `pong`，用于保持连接活跃和检测连接状态。

## 架构优势

1. **高并发**: 使用 asyncio 异步架构，支持大量并发连接
2. **可扩展**: 模块化设计，易于扩展新功能
3. **线程安全**: 连接管理器使用锁机制保证并发安全
4. **消息队列**: 每个连接独立的发送队列，避免消息混乱
5. **灵活路由**: 支持按流水线、会话类型灵活路由消息

## 注意事项

1. **认证**: 当前 WebSocket 连接不需要认证，生产环境建议添加认证机制
2. **心跳**: 建议客户端实现心跳机制，避免连接超时
3. **重连**: 客户端应实现断线重连逻辑
4. **消息大小**: 注意控制单条消息大小，避免内存溢出
5. **连接数限制**: 生产环境建议设置最大连接数限制

## 故障排查

### 连接失败

1. 检查流水线 UUID 是否正确
2. 检查服务器是否正常运行
3. 检查防火墙设置

### 消息发送失败

1. 检查消息格式是否正确
2. 检查连接是否仍然活跃
3. 查看服务器日志获取详细错误信息

### 性能问题

1. 检查并发连接数是否过多
2. 检查消息处理速度
3. 考虑使用连接池或负载均衡

## 开发调试

启用详细日志：

```python
import logging
logging.getLogger('langbot.pkg.platform.sources.websocket_adapter').setLevel(logging.DEBUG)
logging.getLogger('langbot.pkg.platform.sources.websocket_manager').setLevel(logging.DEBUG)
logging.getLogger('langbot.pkg.api.http.controller.groups.pipelines.websocket_chat').setLevel(logging.DEBUG)
```

## 后续改进建议

1. 添加用户认证和授权机制
2. 实现消息持久化
3. 添加消息加密
4. 实现更丰富的消息类型 (图片、文件等)
5. 添加消息已读/未读状态
6. 实现群组聊天功能
7. 添加在线状态显示
8. 实现消息撤回功能

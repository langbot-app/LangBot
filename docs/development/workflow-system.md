# Workflow 系统开发者文档

本文档面向 LangBot 开发者，详细介绍 Workflow 系统的技术架构、核心组件和扩展方法。

## 目录

- [系统架构概述](#系统架构概述)
- [目录结构](#目录结构)
- [核心组件](#核心组件)
  - [后端模块](#后端模块)
  - [前端组件](#前端组件)
- [数据库表结构](#数据库表结构)
- [API 接口文档](#api-接口文档)
- [如何添加新节点类型](#如何添加新节点类型)
- [调试功能实现](#调试功能实现)

---

## 系统架构概述

Workflow 系统采用前后端分离架构，主要包含以下层次：

```
┌─────────────────────────────────────────────────────────────┐
│                      前端层 (React)                          │
│  ┌─────────────┬──────────────┬──────────────┬───────────┐  │
│  │ 可视化编辑器 │   节点面板    │   属性面板   │  调试器   │  │
│  │ ReactFlow   │  NodePalette │ PropertyPanel│ Debugger  │  │
│  └─────────────┴──────────────┴──────────────┴───────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      API 层 (Quart)                          │
│  ┌─────────────┬──────────────┬──────────────────────────┐  │
│  │ Workflow API│  Debug API   │     Node Types API       │  │
│  └─────────────┴──────────────┴──────────────────────────┘  │
├─────────────────────────────────────────────────────────────┤
│                     核心引擎层 (Python)                       │
│  ┌─────────────┬──────────────┬──────────────┬───────────┐  │
│  │ Executor    │   Registry   │    Node      │ Entities  │  │
│  │ 执行引擎     │  节点注册表   │   节点基类   │  数据结构  │  │
│  └─────────────┴──────────────┴──────────────┴───────────┘  │
├─────────────────────────────────────────────────────────────┤
│                      存储层 (SQLAlchemy)                     │
│  ┌─────────────┬──────────────┬──────────────────────────┐  │
│  │  Workflow   │  Executions  │        Triggers          │  │
│  └─────────────┴──────────────┴──────────────────────────┘  │
└─────────────────────────────────────────────────────────────┘
```

---

## 目录结构

### 后端代码结构

```
LangBot/src/langbot/pkg/
├── workflow/                      # Workflow 核心模块
│   ├── __init__.py               # 模块初始化，导出公共接口
│   ├── entities.py               # 数据实体定义
│   ├── executor.py               # 执行引擎
│   ├── node.py                   # 节点基类和装饰器
│   ├── registry.py               # 节点类型注册表
│   └── nodes/                    # 内置节点实现
│       ├── __init__.py           # 注册所有内置节点
│       ├── trigger.py            # 触发节点
│       ├── process.py            # 处理节点
│       ├── control.py            # 控制节点
│       └── action.py             # 动作节点
├── entity/persistence/
│   └── workflow.py               # 数据库模型
├── api/http/
│   ├── controller/groups/workflows/
│   │   └── workflows.py          # API 路由控制器
│   └── service/
│       └── workflow.py           # 业务逻辑服务
└── persistence/migrations/
    └── dbm026_workflow_tables.py # 数据库迁移
```

### 前端代码结构

```
LangBot/web/src/app/home/workflows/
├── page.tsx                      # Workflow 列表页
├── WorkflowDetailContent.tsx     # 详情页内容
├── store/
│   └── useWorkflowStore.ts       # Zustand 状态管理
└── components/
    ├── workflow-editor/          # 可视化编辑器
    │   ├── index.ts              # 导出
    │   ├── WorkflowEditorComponent.tsx  # 主编辑器组件
    │   ├── WorkflowNodeComponent.tsx    # 自定义节点组件
    │   ├── NodePalette.tsx       # 节点面板
    │   ├── PropertyPanel.tsx     # 属性面板
    │   └── node-configs/         # 节点配置元数据
    │       ├── types.ts          # 配置类型定义
    │       ├── trigger-configs.ts
    │       ├── ai-configs.ts
    │       ├── process-configs.ts
    │       ├── control-configs.ts
    │       ├── action-configs.ts
    │       ├── integration-configs.ts
    │       └── index.ts          # 配置汇总
    ├── workflow-debugger/        # 调试器组件
    │   ├── index.ts
    │   └── WorkflowDebugger.tsx
    ├── workflow-form/            # 表单组件
    │   └── WorkflowFormComponent.tsx
    └── workflow-executions/      # 执行历史组件
        └── WorkflowExecutionsTab.tsx
```

---

## 核心组件

### 后端模块

#### 1. 执行引擎 (WorkflowExecutor)

位置：[`executor.py`](../../src/langbot/pkg/workflow/executor.py)

执行引擎负责工作流的实际执行，包括：

- **拓扑排序**：确定节点执行顺序
- **节点执行**：调用各节点的 execute 方法
- **控制流处理**：处理条件分支、循环、并行执行
- **错误处理**：支持重试机制

```python
class WorkflowExecutor:
    async def execute(
        self, 
        workflow: WorkflowDefinition, 
        context: ExecutionContext,
        start_node_id: Optional[str] = None
    ) -> ExecutionContext:
        """执行工作流"""
        # 1. 构建执行图
        # 2. 初始化节点状态
        # 3. 找到起始节点
        # 4. 按拓扑顺序执行
```

**调试执行器 (DebugWorkflowExecutor)**

继承自 WorkflowExecutor，增加了调试支持：

- 断点支持
- 单步执行
- 暂停/继续
- 实时日志

```python
class DebugWorkflowExecutor(WorkflowExecutor):
    async def execute_debug(
        self,
        workflow: WorkflowDefinition,
        context: ExecutionContext,
        debug_state: DebugExecutionState,
    ) -> ExecutionContext:
        """调试模式执行"""
```

#### 2. 节点注册表 (NodeTypeRegistry)

位置：[`registry.py`](../../src/langbot/pkg/workflow/registry.py)

单例模式管理所有节点类型：

```python
class NodeTypeRegistry:
    _instance: Optional['NodeTypeRegistry'] = None
    
    def register(self, node_type: str, node_class: type[WorkflowNode]):
        """注册节点类型"""
        
    def create_instance(self, node_type: str, node_id: str, config: dict) -> WorkflowNode:
        """创建节点实例"""
        
    def list_all(self) -> list[dict]:
        """获取所有节点类型的 Schema"""
```

#### 3. 节点基类 (WorkflowNode)

位置：[`node.py`](../../src/langbot/pkg/workflow/node.py)

所有节点必须继承此基类：

```python
class WorkflowNode(abc.ABC):
    # 节点元数据
    type_name: str = ""
    name: str = ""
    description: str = ""
    category: str = "misc"
    icon: str = ""
    
    # 端口定义
    inputs: list[NodePort] = []
    outputs: list[NodePort] = []
    
    # 配置 Schema
    config_schema: list[NodeConfig] = []
    
    @abc.abstractmethod
    async def execute(
        self, 
        inputs: dict[str, Any], 
        context: ExecutionContext
    ) -> dict[str, Any]:
        """执行节点逻辑"""
        pass
```

#### 4. 数据实体 (entities.py)

主要数据结构：

```python
class WorkflowDefinition:
    """工作流定义"""
    uuid: str
    name: str
    nodes: list[NodeDefinition]
    edges: list[EdgeDefinition]
    settings: WorkflowSettings
    
class ExecutionContext:
    """执行上下文"""
    execution_id: str
    workflow_id: str
    status: ExecutionStatus
    variables: dict
    node_states: dict[str, NodeState]
    history: list[ExecutionStep]
```

### 前端组件

#### 1. WorkflowEditorComponent

主编辑器组件，基于 React Flow 实现：

- **画布交互**：拖拽、缩放、平移
- **节点连接**：自动验证端口类型
- **撤销/重做**：基于历史记录栈
- **复制/粘贴**：支持多选复制

关键功能：

```tsx
function WorkflowEditorInner() {
  const { nodes, edges, onNodesChange, onEdgesChange, onConnect } = useWorkflowStore();
  
  // 拖放添加节点
  const onDrop = useCallback((event: React.DragEvent) => {
    const type = event.dataTransfer.getData('application/reactflow');
    const position = screenToFlowPosition({ x: event.clientX, y: event.clientY });
    addNode(type, position);
  }, []);
  
  // 复制粘贴
  const handleCopy = useCallback(() => { ... }, []);
  const handlePaste = useCallback(() => { ... }, []);
}
```

#### 2. NodePalette

节点面板组件，展示可用节点类型：

```tsx
function NodePalette() {
  // 按类别组织节点
  const categories = [
    { id: 'trigger', name: '触发节点', icon: Zap },
    { id: 'ai', name: 'AI 节点', icon: Brain },
    { id: 'process', name: '处理节点', icon: Cpu },
    { id: 'control', name: '控制节点', icon: GitBranch },
    { id: 'action', name: '动作节点', icon: Send },
    { id: 'integration', name: '集成节点', icon: Plug },
  ];
  
  // 拖拽开始
  const onDragStart = (event: React.DragEvent, nodeType: string) => {
    event.dataTransfer.setData('application/reactflow', nodeType);
  };
}
```

#### 3. PropertyPanel

属性面板组件，动态渲染节点配置表单：

```tsx
function PropertyPanel() {
  const { selectedNodeId, nodes, updateNodeData } = useWorkflowStore();
  
  // 根据节点类型获取配置元数据
  const selectedNode = nodes.find(n => n.id === selectedNodeId);
  const nodeConfig = getNodeConfig(selectedNode?.data?.nodeType);
  
  // 动态渲染配置字段
  return (
    <div>
      {nodeConfig?.fields.map(field => (
        <ConfigField key={field.name} field={field} />
      ))}
    </div>
  );
}
```

#### 4. WorkflowDebugger

调试器组件，支持实时调试：

```tsx
function WorkflowDebugger({ workflowUuid, workflow }) {
  const [debugState, setDebugState] = useState<DebugState>('idle');
  const [executionId, setExecutionId] = useState<string>('');
  const [logs, setLogs] = useState<ExecutionLog[]>([]);
  
  // 启动调试
  const startDebug = async () => {
    const result = await backendClient.post(
      `/api/v1/workflows/${workflowUuid}/debug/start`,
      { context, variables, breakpoints }
    );
    setExecutionId(result.execution_id);
  };
  
  // 轮询状态
  useEffect(() => {
    if (debugState === 'running') {
      const interval = setInterval(fetchState, 500);
      return () => clearInterval(interval);
    }
  }, [debugState]);
}
```

#### 5. useWorkflowStore

Zustand 状态管理：

```typescript
interface WorkflowState {
  nodes: WorkflowNode[];
  edges: WorkflowEdge[];
  selectedNodeId: string | null;
  history: HistoryEntry[];
  historyIndex: number;
  isDirty: boolean;
  
  // Actions
  addNode: (type: string, position: XYPosition) => void;
  updateNodeData: (nodeId: string, data: Partial<NodeData>) => void;
  deleteNode: (nodeId: string) => void;
  undo: () => void;
  redo: () => void;
}

export const useWorkflowStore = create<WorkflowState>((set, get) => ({
  // ... state and actions
}));
```

---

## 数据库表结构

### workflows 表

```sql
CREATE TABLE workflows (
    uuid VARCHAR(255) PRIMARY KEY,
    name VARCHAR(255) NOT NULL,
    description TEXT,
    emoji VARCHAR(10) DEFAULT '🔄',
    version INTEGER DEFAULT 1,
    is_enabled BOOLEAN DEFAULT TRUE,
    definition JSON NOT NULL,        -- 节点和边定义
    global_config JSON DEFAULT '{}', -- 全局配置
    extensions_preferences JSON,     -- 插件和 MCP 配置
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

### workflow_versions 表

```sql
CREATE TABLE workflow_versions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    workflow_uuid VARCHAR(255) NOT NULL,
    version INTEGER NOT NULL,
    definition JSON NOT NULL,
    global_config JSON DEFAULT '{}',
    created_at TIMESTAMP,
    created_by VARCHAR(255),
    UNIQUE(workflow_uuid, version)
);
```

### workflow_executions 表

```sql
CREATE TABLE workflow_executions (
    uuid VARCHAR(255) PRIMARY KEY,
    workflow_uuid VARCHAR(255) NOT NULL,
    workflow_version INTEGER NOT NULL,
    status VARCHAR(20) NOT NULL,  -- pending/running/completed/failed/cancelled
    trigger_type VARCHAR(50),
    trigger_data JSON,
    variables JSON,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    error TEXT,
    created_at TIMESTAMP
);
```

### workflow_node_executions 表

```sql
CREATE TABLE workflow_node_executions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    execution_uuid VARCHAR(255) NOT NULL,
    node_id VARCHAR(100) NOT NULL,
    node_type VARCHAR(50) NOT NULL,
    status VARCHAR(20) NOT NULL,
    inputs JSON,
    outputs JSON,
    start_time TIMESTAMP,
    end_time TIMESTAMP,
    error TEXT,
    retry_count INTEGER DEFAULT 0
);
```

### workflow_triggers 表

```sql
CREATE TABLE workflow_triggers (
    uuid VARCHAR(255) PRIMARY KEY,
    workflow_uuid VARCHAR(255) NOT NULL,
    type VARCHAR(50) NOT NULL,  -- message/cron/event/webhook
    config JSON NOT NULL,
    is_enabled BOOLEAN DEFAULT TRUE,
    priority INTEGER DEFAULT 0,
    created_at TIMESTAMP,
    updated_at TIMESTAMP
);
```

---

## API 接口文档

### Workflow CRUD

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/api/v1/workflows` | 获取工作流列表 |
| POST | `/api/v1/workflows` | 创建工作流 |
| GET | `/api/v1/workflows/:uuid` | 获取单个工作流 |
| PUT | `/api/v1/workflows/:uuid` | 更新工作流 |
| DELETE | `/api/v1/workflows/:uuid` | 删除工作流 |
| POST | `/api/v1/workflows/:uuid/copy` | 复制工作流 |

### 执行相关

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/api/v1/workflows/:uuid/execute` | 手动执行工作流 |
| GET | `/api/v1/workflows/:uuid/executions` | 获取执行记录 |

### 版本管理

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/api/v1/workflows/:uuid/versions` | 获取版本列表 |
| POST | `/api/v1/workflows/:uuid/rollback/:version` | 回滚到指定版本 |

### 调试 API

| 方法 | 路径 | 描述 |
|-----|------|------|
| POST | `/api/v1/workflows/:uuid/debug/start` | 启动调试 |
| POST | `/api/v1/workflows/:uuid/debug/:exec_id/pause` | 暂停执行 |
| POST | `/api/v1/workflows/:uuid/debug/:exec_id/resume` | 继续执行 |
| POST | `/api/v1/workflows/:uuid/debug/:exec_id/stop` | 停止执行 |
| POST | `/api/v1/workflows/:uuid/debug/:exec_id/step` | 单步执行 |
| GET | `/api/v1/workflows/:uuid/debug/:exec_id/state` | 获取调试状态 |

### 节点类型

| 方法 | 路径 | 描述 |
|-----|------|------|
| GET | `/api/v1/workflows/_/node-types` | 获取所有节点类型 |
| GET | `/api/v1/workflows/_/node-types/categories` | 按类别获取节点类型 |

---

## 如何添加新节点类型

### 步骤 1：创建节点类

在 `LangBot/src/langbot/pkg/workflow/nodes/` 下创建或修改文件：

```python
from ..node import WorkflowNode, NodePort, NodeConfig, workflow_node
from ..entities import ExecutionContext

@workflow_node('my_custom_node')
class MyCustomNode(WorkflowNode):
    """自定义节点"""
    
    # 元数据
    type_name = 'my_custom_node'
    name = '我的自定义节点'
    description = '这是一个自定义节点'
    category = 'process'  # trigger/process/control/action/integration
    icon = '🔧'
    
    # 输入端口
    inputs = [
        NodePort(name='input', type='string', description='输入数据', required=True),
    ]
    
    # 输出端口
    outputs = [
        NodePort(name='output', type='string', description='输出数据'),
    ]
    
    # 配置字段
    config_schema = [
        NodeConfig(
            name='option',
            type='select',
            required=True,
            options=['选项A', '选项B'],
            description='选择一个选项'
        ),
        NodeConfig(
            name='value',
            type='string',
            required=False,
            default='默认值',
            description='配置值'
        ),
    ]
    
    async def execute(
        self, 
        inputs: dict[str, Any], 
        context: ExecutionContext
    ) -> dict[str, Any]:
        """执行节点逻辑"""
        input_data = inputs.get('input', '')
        option = self.get_config('option')
        value = self.get_config('value', '')
        
        # 处理逻辑
        result = f"处理: {input_data} with {option} and {value}"
        
        return {'output': result}
```

### 步骤 2：注册节点

在 `LangBot/src/langbot/pkg/workflow/nodes/__init__.py` 中导入：

```python
from .process import (
    CodeExecutorNode,
    HttpRequestNode,
    DataTransformNode,
    MyCustomNode,  # 添加新节点
)
```

### 步骤 3：添加前端配置

在 `LangBot/web/src/app/home/workflows/components/workflow-editor/node-configs/` 目录下添加配置：

```typescript
// process-configs.ts
export const processNodeConfigs: NodeConfigMap = {
  // ... 其他配置
  
  my_custom_node: {
    type: 'my_custom_node',
    label: 'workflows.nodes.myCustomNode',
    description: 'workflows.nodes.myCustomNodeDesc',
    icon: 'Wrench',
    category: 'process',
    fields: [
      {
        name: 'option',
        type: 'select',
        label: 'workflows.fields.option',
        required: true,
        options: [
          { value: '选项A', label: '选项 A' },
          { value: '选项B', label: '选项 B' },
        ],
      },
      {
        name: 'value',
        type: 'string',
        label: 'workflows.fields.value',
        required: false,
        defaultValue: '默认值',
      },
    ],
  },
};
```

### 步骤 4：添加国际化

在 `LangBot/web/src/i18n/locales/` 中添加翻译：

```typescript
// zh-Hans.ts
workflows: {
  nodes: {
    myCustomNode: '我的自定义节点',
    myCustomNodeDesc: '这是一个自定义节点',
  },
  fields: {
    option: '选项',
    value: '值',
  },
}
```

---

## 调试功能实现

### 后端调试状态管理

```python
class DebugExecutionState:
    """调试执行状态"""
    
    def __init__(self, execution_id: str, breakpoints: list[str] = None):
        self.execution_id = execution_id
        self.status: str = 'running'
        self.is_paused: bool = False
        self.is_stopped: bool = False
        self.breakpoints: set[str] = set(breakpoints or [])
        self.logs: list[ExecutionLog] = []
        self._pause_event = asyncio.Event()
    
    def pause(self):
        """暂停执行"""
        self.is_paused = True
        self._pause_event.clear()
    
    def resume(self):
        """继续执行"""
        self.is_paused = False
        self._pause_event.set()
    
    async def wait_if_paused(self):
        """如果暂停则等待"""
        if self.is_paused:
            await self._pause_event.wait()
```

### 前端调试流程

1. **设置断点**：点击节点设置断点
2. **启动调试**：调用 `/debug/start` 启动调试执行
3. **轮询状态**：定期调用 `/debug/:id/state` 获取状态
4. **控制执行**：调用 pause/resume/step/stop 控制执行
5. **查看日志**：实时显示执行日志和节点状态

```typescript
// 调试状态轮询
const fetchDebugState = async () => {
  const state = await backendClient.get(
    `/api/v1/workflows/${workflowUuid}/debug/${executionId}/state`
  );
  
  // 更新节点状态
  setNodeStates(state.node_states);
  
  // 追加新日志
  if (state.new_logs.length > 0) {
    setLogs(prev => [...prev, ...state.new_logs]);
  }
  
  // 检查完成状态
  if (state.status === 'completed' || state.status === 'error') {
    setDebugState('idle');
  }
};
```

---

## 扩展阅读

- [Workflow 功能设计文档](../../../plans/langbot-workflow-design.md)
- [用户使用指南](../user-guide/workflow-guide.md)
- [API 认证文档](../API_KEY_AUTH.md)

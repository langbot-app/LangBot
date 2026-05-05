import { I18nObject } from '@/app/infra/entities/common';
import { IDynamicFormItemSchema } from '@/app/infra/entities/form/dynamic';

// 节点位置
export interface Position {
  x: number;
  y: number;
}

// 端口定义
export interface PortDefinition {
  name: string;
  type: string;
  description?: string;
  required?: boolean;
}

// 节点定义
export interface NodeDefinition {
  id: string;
  type: string;
  name: string;
  position: Position;
  config: Record<string, unknown>;
  data?: Record<string, unknown>;
}

// 边定义
export interface EdgeDefinition {
  id: string;
  source: string;
  sourceHandle?: string;
  target: string;
  targetHandle?: string;
  condition?: string;
}

// 触发器定义
export interface TriggerDefinition {
  id: string;
  type: string;
  config: Record<string, unknown>;
  enabled: boolean;
}

// 工作流设置
export interface WorkflowSettings {
  timeout?: number;
  max_retries?: number;
  retry_delay?: number;
  error_handling?: 'stop' | 'continue' | 'retry';
}

// 工作流定义
export interface WorkflowDefinition {
  uuid: string;
  name: string;
  emoji?: string;
  description?: string;
  version: number;
  nodes: NodeDefinition[];
  edges: EdgeDefinition[];
  variables?: Record<string, unknown>;
  settings?: WorkflowSettings;
  triggers?: TriggerDefinition[];
  is_enabled: boolean;
  created_at: string;
  updated_at: string;
}

// 节点类型元数据
export interface NodeTypeMetadata {
  type: string;
  name: I18nObject;
  description?: I18nObject;
  category: NodeCategory;
  icon?: string;
  color?: string;
  inputs: PortDefinition[];
  outputs: PortDefinition[];
  config_schema: IDynamicFormItemSchema[];
}

// 节点类别
export type NodeCategory = 'trigger' | 'process' | 'control' | 'action' | 'integration';

// 节点类别信息
export interface NodeCategoryInfo {
  id: NodeCategory;
  name: I18nObject;
  icon: string;
  color: string;
}

// 工作流执行状态
export type ExecutionStatus = 'pending' | 'running' | 'completed' | 'failed' | 'cancelled';

// 工作流执行记录
export interface WorkflowExecution {
  id: string;
  workflow_uuid: string;
  workflow_version: number;
  status: ExecutionStatus;
  trigger_type?: string;
  trigger_data?: Record<string, unknown>;
  variables?: Record<string, unknown>;
  start_time?: string;
  end_time?: string;
  error?: string;
  created_at: string;
}

// 节点执行记录
export interface NodeExecution {
  id: number;
  execution_id: string;
  node_id: string;
  node_type: string;
  status: ExecutionStatus;
  inputs?: Record<string, unknown>;
  outputs?: Record<string, unknown>;
  start_time?: string;
  end_time?: string;
  error?: string;
  retry_count: number;
}

// API 响应类型
export interface ApiRespWorkflows {
  workflows: WorkflowDefinition[];
}

export interface ApiRespWorkflow {
  workflow: WorkflowDefinition;
}

export interface ApiRespNodeTypes {
  node_types: NodeTypeMetadata[];
  categories: NodeCategoryInfo[];
}

export interface ApiRespWorkflowExecutions {
  executions: WorkflowExecution[];
  total: number;
}

export interface ApiRespWorkflowExecution {
  execution: WorkflowExecution;
  node_executions: NodeExecution[];
}

// 创建工作流请求
export interface CreateWorkflowRequest {
  name: string;
  emoji?: string;
  description?: string;
  nodes?: NodeDefinition[];
  edges?: EdgeDefinition[];
  variables?: Record<string, unknown>;
  settings?: WorkflowSettings;
  triggers?: TriggerDefinition[];
}

// 更新工作流请求
export interface UpdateWorkflowRequest {
  name?: string;
  emoji?: string;
  description?: string;
  nodes?: NodeDefinition[];
  edges?: EdgeDefinition[];
  variables?: Record<string, unknown>;
  settings?: WorkflowSettings;
  triggers?: TriggerDefinition[];
  is_enabled?: boolean;
}

// 执行工作流请求
export interface ExecuteWorkflowRequest {
  trigger_type?: string;
  trigger_data?: Record<string, unknown>;
  variables?: Record<string, unknown>;
}

// 节点类别配置
export const NODE_CATEGORIES: NodeCategoryInfo[] = [
  {
    id: 'trigger',
    name: { en_US: 'Trigger', zh_Hans: '触发' },
    icon: 'Zap',
    color: '#f59e0b',
  },
  {
    id: 'process',
    name: { en_US: 'Process', zh_Hans: '处理' },
    icon: 'Cpu',
    color: '#3b82f6',
  },
  {
    id: 'control',
    name: { en_US: 'Control', zh_Hans: '控制' },
    icon: 'GitBranch',
    color: '#8b5cf6',
  },
  {
    id: 'action',
    name: { en_US: 'Action', zh_Hans: '动作' },
    icon: 'Play',
    color: '#10b981',
  },
  {
    id: 'integration',
    name: { en_US: 'Integration', zh_Hans: '集成' },
    icon: 'Plug',
    color: '#ec4899',
  },
];

"""Workflow-Pipeline通信适配器

这个模块提供了Workflow和Pipeline之间的通信适配，使用SDK标准的MessageEnvelope格式。
"""

from __future__ import annotations

import logging
from typing import Any, Optional

logger = logging.getLogger(__name__)


class _WorkflowPipelineCaptureAdapter:
    """Workflow-Pipeline通信适配器
    
    用于在Workflow节点和Pipeline之间进行标准化的消息传递。
    支持MessageEnvelope格式的双向转换。
    """
    
    def __init__(self, context: Any):
        """初始化适配器
        
        Args:
            context: ExecutionContext - Workflow执行上下文
        """
        self.context = context
        self.responses: list[dict[str, Any]] = []
        self.bot_account_id: Optional[str] = None
        self._logger = logging.getLogger(__name__)
    
    async def call_pipeline_with_envelope(
        self,
        envelope: Any,
        pipeline_executor: Any
    ) -> Any:
        """使用MessageEnvelope调用Pipeline
        
        Args:
            envelope: MessageEnvelope - 标准消息信封
            pipeline_executor: Pipeline执行器实例
            
        Returns:
            MessageEnvelope - 执行结果信封
        """
        try:
            # 动态导入以避免循环依赖
            from langbot_plugin_sdk.workflow import envelope_to_query, query_to_envelope
            
            # 1. 转换为Query
            query = envelope_to_query(envelope)
            
            # 2. 调用Pipeline
            result_query = await pipeline_executor.execute(query)
            
            # 3. 转换回Envelope
            result_envelope = query_to_envelope(result_query, envelope)
            
            self._logger.debug(
                f'Pipeline execution completed for workflow {envelope.workflow_id}',
                extra={
                    'workflow_id': envelope.workflow_id,
                    'execution_id': envelope.execution_id,
                    'node_id': envelope.node_id,
                }
            )
            
            return result_envelope
            
        except Exception as e:
            self._logger.error(
                f'Pipeline execution failed: {e}',
                exc_info=True,
                extra={
                    'workflow_id': envelope.workflow_id,
                    'execution_id': envelope.execution_id,
                    'node_id': envelope.node_id,
                }
            )
            raise
    
    def validate_envelope(self, envelope: Any) -> bool:
        """验证MessageEnvelope的有效性
        
        Args:
            envelope: MessageEnvelope - 要验证的消息信封
            
        Returns:
            bool - 验证是否通过
        """
        required_fields = [
            'message_id',
            'workflow_id',
            'node_id',
            'execution_id',
            'payload',
            'launcher_type',
        ]
        
        for field in required_fields:
            if not hasattr(envelope, field):
                self._logger.warning(
                    f'MessageEnvelope missing required field: {field}'
                )
                return False
        
        return True
    
    def get_responses(self) -> list[dict[str, Any]]:
        """获取所有响应
        
        Returns:
            list - 响应列表
        """
        return self.responses.copy()
    
    def add_response(self, response: dict[str, Any]) -> None:
        """添加响应
        
        Args:
            response: dict - 响应数据
        """
        self.responses.append(response)
    
    def get_last_text_response(self) -> str:
        """获取最后一个文本响应
        
        Returns:
            str - 最后一个响应的文本内容
        """
        if not self.responses:
            return ''
        
        last_response = self.responses[-1]
        return str(last_response.get('content', '') or '')
    
    def clear_responses(self) -> None:
        """清空所有响应"""
        self.responses.clear()


class WorkflowPipelineCompatibilityLayer:
    """Workflow-Pipeline兼容性层
    
    提供向后兼容性，支持旧的Pipeline Query格式和新的MessageEnvelope格式。
    """
    
    def __init__(self):
        """初始化兼容性层"""
        self._logger = logging.getLogger(__name__)
    
    def is_workflow_context(self, query: Any) -> bool:
        """检查Query是否包含Workflow上下文
        
        Args:
            query: Query - Pipeline Query对象
            
        Returns:
            bool - 是否来自Workflow
        """
        if hasattr(query, 'is_from_workflow'):
            return query.is_from_workflow()
        
        if hasattr(query, 'get_workflow_context'):
            context = query.get_workflow_context()
            return bool(context and context.get('workflow_id'))
        
        return False
    
    def get_workflow_id(self, query: Any) -> Optional[str]:
        """从Query获取Workflow ID
        
        Args:
            query: Query - Pipeline Query对象
            
        Returns:
            str - Workflow ID，如果不存在则返回None
        """
        if hasattr(query, 'get_workflow_id'):
            return query.get_workflow_id()
        
        if hasattr(query, 'get_workflow_context'):
            context = query.get_workflow_context()
            return context.get('workflow_id') if context else None
        
        return None
    
    def get_execution_id(self, query: Any) -> Optional[str]:
        """从Query获取执行ID
        
        Args:
            query: Query - Pipeline Query对象
            
        Returns:
            str - 执行ID，如果不存在则返回None
        """
        if hasattr(query, 'get_execution_id'):
            return query.get_execution_id()
        
        if hasattr(query, 'get_workflow_context'):
            context = query.get_workflow_context()
            return context.get('execution_id') if context else None
        
        return None

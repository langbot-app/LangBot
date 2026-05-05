"""Workflow service for managing workflow CRUD and execution"""
from __future__ import annotations

import asyncio
import uuid
from datetime import datetime, timedelta
from typing import Any, Optional

import sqlalchemy

from ....core import app
from ....entity.persistence import workflow as persistence_workflow
from ....workflow.entities import (
    WorkflowDefinition,
    ExecutionContext,
    ExecutionStatus,
    NodeDefinition,
    EdgeDefinition,
    Position,
    MessageContext,
    NodeStatus,
)
from ....workflow.executor import WorkflowExecutor
from ....workflow.registry import NodeTypeRegistry


class WorkflowExecutionFailedError(Exception):
    """Raised when a workflow execution finishes with failed status."""

    def __init__(
        self,
        execution_id: str,
        message: str,
        *,
        details: str | None = None,
    ) -> None:
        super().__init__(message)
        self.execution_id = execution_id
        self.message = message
        self.details = details or message


class WorkflowService:
    """Workflow service for managing workflows"""

    DEFAULT_MAX_EXECUTION_TIME = 300
    STALE_EXECUTION_TIMEOUT_SECONDS = 300
    
    ap: app.Application
    
    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.executor = WorkflowExecutor(ap)
        self.registry = NodeTypeRegistry.instance()
        
        # Import workflow nodes to trigger registration
        from ....workflow import nodes  # noqa: F401
    
    async def get_workflows(
        self, 
        sort_by: str = 'created_at', 
        sort_order: str = 'DESC',
        enabled_only: bool = False
    ) -> list[dict]:
        """Get all workflows"""
        query = sqlalchemy.select(persistence_workflow.Workflow)
        
        if enabled_only:
            query = query.where(persistence_workflow.Workflow.is_enabled == True)
        
        if sort_by == 'created_at':
            if sort_order == 'DESC':
                query = query.order_by(persistence_workflow.Workflow.created_at.desc())
            else:
                query = query.order_by(persistence_workflow.Workflow.created_at.asc())
        elif sort_by == 'updated_at':
            if sort_order == 'DESC':
                query = query.order_by(persistence_workflow.Workflow.updated_at.desc())
            else:
                query = query.order_by(persistence_workflow.Workflow.updated_at.asc())
        elif sort_by == 'name':
            if sort_order == 'DESC':
                query = query.order_by(persistence_workflow.Workflow.name.desc())
            else:
                query = query.order_by(persistence_workflow.Workflow.name.asc())
        
        result = await self.ap.persistence_mgr.execute_async(query)
        workflows = result.all()
        
        return [
            self._serialize_workflow(workflow)
            for workflow in workflows
        ]
    
    async def get_workflow(self, workflow_uuid: str) -> Optional[dict]:
        """Get a single workflow by UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.Workflow).where(
                persistence_workflow.Workflow.uuid == workflow_uuid
            )
        )
        
        workflow = result.first()
        
        if workflow is None:
            return None
        
        return self._serialize_workflow(workflow)
    
    async def create_workflow(self, workflow_data: dict) -> str:
        """Create a new workflow"""
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_workflows = limitation.get('max_workflows', -1)
        if max_workflows >= 0:
            existing_workflows = await self.get_workflows()
            if len(existing_workflows) >= max_workflows:
                raise ValueError(f'Maximum number of workflows ({max_workflows}) reached')
        
        workflow_uuid = str(uuid.uuid4())
        
        # Prepare workflow data
        new_workflow = {
            'uuid': workflow_uuid,
            'name': workflow_data.get('name', 'New Workflow'),
            'description': workflow_data.get('description', ''),
            'emoji': workflow_data.get('emoji', '🔄'),
            'version': 1,
            'is_enabled': workflow_data.get('is_enabled', True),
            'definition': workflow_data.get('definition', {
                'nodes': [],
                'edges': [],
                'variables': {},
            }),
            'global_config': workflow_data.get('global_config', {}),
            'extensions_preferences': workflow_data.get('extensions_preferences', {
                'enable_all_plugins': True,
                'enable_all_mcp_servers': True,
                'plugins': [],
                'mcp_servers': [],
            }),
        }
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.Workflow).values(**new_workflow)
        )
        
        return workflow_uuid
    
    async def update_workflow(self, workflow_uuid: str, workflow_data: dict) -> None:
        """Update an existing workflow"""
        # Remove protected fields
        protected_fields = ['uuid', 'created_at']
        for field in protected_fields:
            workflow_data.pop(field, None)
        
        # Get current workflow to check version
        current = await self.get_workflow(workflow_uuid)
        if current is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        # Handle nodes, edges and variables fields - merge them into definition
        # This handles the case where frontend sends nodes/edges/variables at top level
        nodes = workflow_data.pop('nodes', None)
        edges = workflow_data.pop('edges', None)
        variables = workflow_data.pop('variables', None)
        
        # Remove fields that don't exist as database columns
        workflow_data.pop('settings', None)
        workflow_data.pop('triggers', None)
        
        if nodes is not None or edges is not None or variables is not None:
            # Get current definition or create new one
            definition = workflow_data.get('definition', current.get('definition', {}))
            if not isinstance(definition, dict):
                definition = {}
            
            # Update nodes, edges and variables in definition
            if nodes is not None:
                definition['nodes'] = nodes
            if edges is not None:
                definition['edges'] = edges
            if variables is not None:
                definition['variables'] = variables
            
            workflow_data['definition'] = definition
        
        # Increment version if definition changed
        if 'definition' in workflow_data:
            workflow_data['version'] = current.get('version', 0) + 1
            
            # Save version history
            await self._save_version_history(
                workflow_uuid,
                current.get('version', 1),
                current.get('definition', {}),
                current.get('global_config', {})
            )
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.Workflow)
            .where(persistence_workflow.Workflow.uuid == workflow_uuid)
            .values(**workflow_data)
        )
    
    async def delete_workflow(self, workflow_uuid: str) -> None:
        """Delete a workflow"""
        # Delete related records first
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_workflow.WorkflowVersion).where(
                persistence_workflow.WorkflowVersion.workflow_uuid == workflow_uuid
            )
        )
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_workflow.WorkflowTrigger).where(
                persistence_workflow.WorkflowTrigger.workflow_uuid == workflow_uuid
            )
        )
        
        # Delete the workflow
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.delete(persistence_workflow.Workflow).where(
                persistence_workflow.Workflow.uuid == workflow_uuid
            )
        )
    
    async def copy_workflow(self, workflow_uuid: str) -> str:
        """Copy a workflow"""
        # Check limitation
        limitation = self.ap.instance_config.data.get('system', {}).get('limitation', {})
        max_workflows = limitation.get('max_workflows', -1)
        if max_workflows >= 0:
            existing_workflows = await self.get_workflows()
            if len(existing_workflows) >= max_workflows:
                raise ValueError(f'Maximum number of workflows ({max_workflows}) reached')
        
        # Get original workflow
        original = await self.get_workflow(workflow_uuid)
        if original is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        # Create copy
        new_uuid = str(uuid.uuid4())
        new_workflow = {
            'uuid': new_uuid,
            'name': f"{original['name']} (Copy)",
            'description': original.get('description', ''),
            'emoji': original.get('emoji', '🔄'),
            'version': 1,
            'is_enabled': False,  # Disabled by default
            'definition': original.get('definition', {}),
            'global_config': original.get('global_config', {}),
            'extensions_preferences': original.get('extensions_preferences', {
                'enable_all_plugins': True,
                'enable_all_mcp_servers': True,
                'plugins': [],
                'mcp_servers': [],
            }),
        }
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.Workflow).values(**new_workflow)
        )
        
        return new_uuid
    
    async def execute_workflow(
        self, 
        workflow_uuid: str, 
        trigger_type: str = 'manual',
        trigger_data: Optional[dict] = None,
        session_id: Optional[str] = None,
        user_id: Optional[str] = None,
        bot_id: Optional[str] = None
    ) -> str:
        """Execute a workflow and return execution ID"""
        workflow_dict = await self.get_workflow(workflow_uuid)
        if workflow_dict is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        # Create execution record
        execution_uuid = str(uuid.uuid4())
        execution_record = {
            'uuid': execution_uuid,
            'workflow_uuid': workflow_uuid,
            'workflow_version': workflow_dict.get('version', 1),
            'status': ExecutionStatus.PENDING.value,
            'trigger_type': trigger_type,
            'trigger_data': trigger_data or {},
            'variables': {},
            'start_time': datetime.now(),
        }
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.WorkflowExecution).values(**execution_record)
        )
        
        # Build WorkflowDefinition from dict
        definition = workflow_dict.get('definition', {})
        workflow = WorkflowDefinition(
            uuid=workflow_uuid,
            name=workflow_dict.get('name', ''),
            description=workflow_dict.get('description', ''),
            version=workflow_dict.get('version', 1),
            nodes=[
                NodeDefinition(
                    id=n.get('id', ''),
                    type=n.get('type', ''),
                    name=n.get('name', ''),
                    position=Position(**n.get('position', {'x': 0, 'y': 0})),
                    config=n.get('config', {}),
                )
                for n in definition.get('nodes', [])
            ],
            edges=[
                EdgeDefinition(
                    id=e.get('id', ''),
                    source_node=e.get('source_node', '') or e.get('source', ''),
                    source_port=e.get('source_port', '') or e.get('sourceHandle', 'output'),
                    target_node=e.get('target_node', '') or e.get('target', ''),
                    target_port=e.get('target_port', '') or e.get('targetHandle', 'input'),
                    condition=e.get('condition') or (e.get('data', {}) or {}).get('condition'),
                )
                for e in definition.get('edges', [])
            ],
            variables=definition.get('variables', {}),
        )
        
        raw_trigger_data = trigger_data or {}

        # Create execution context
        context = ExecutionContext(
            execution_id=execution_uuid,
            workflow_id=workflow_uuid,
            workflow_version=workflow_dict.get('version', 1),
            trigger_type=trigger_type,
            trigger_data=raw_trigger_data,
            session_id=session_id,
            user_id=user_id,
            bot_id=bot_id,
        )

        if trigger_type == 'message':
            message_context_data = raw_trigger_data.get('message_context') or {}
            if message_context_data:
                context.message_context = MessageContext(
                    message_id=str(message_context_data.get('message_id', execution_uuid)),
                    message_content=str(message_context_data.get('message_content', '')),
                    sender_id=str(message_context_data.get('sender_id', '')),
                    sender_name=str(message_context_data.get('sender_name', '')),
                    platform=str(message_context_data.get('platform', '')),
                    conversation_id=str(message_context_data.get('conversation_id', '')),
                    is_group=bool(message_context_data.get('is_group', False)),
                    group_id=(
                        str(message_context_data.get('group_id'))
                        if message_context_data.get('group_id') is not None
                        else None
                    ),
                    mentions=[str(item) for item in message_context_data.get('mentions', [])],
                    reply_to=(
                        str(message_context_data.get('reply_to'))
                        if message_context_data.get('reply_to') is not None
                        else None
                    ),
                    raw_message=message_context_data.get('raw_message', {}),
                )
        
        max_execution_time = self.DEFAULT_MAX_EXECUTION_TIME
        workflow_settings = definition.get('settings', {}) if isinstance(definition, dict) else {}
        if isinstance(workflow_settings, dict):
            raw_timeout = workflow_settings.get('max_execution_time', self.DEFAULT_MAX_EXECUTION_TIME)
            try:
                max_execution_time = int(raw_timeout)
            except (TypeError, ValueError):
                max_execution_time = self.DEFAULT_MAX_EXECUTION_TIME
        if max_execution_time <= 0:
            max_execution_time = self.DEFAULT_MAX_EXECUTION_TIME

        # Execute asynchronously (in production, this should be done in a background task)
        try:
            context = await asyncio.wait_for(
                self.executor.execute(workflow, context),
                timeout=max_execution_time,
            )

            error_message = context.error
            if context.status == ExecutionStatus.FAILED and not error_message:
                failed_nodes = [
                    state
                    for state in context.node_states.values()
                    if getattr(state, 'status', None) == NodeStatus.FAILED
                ]
                error_message = next(
                    (
                        state.error
                        for state in failed_nodes
                        if getattr(state, 'error', None)
                    ),
                    'Workflow execution failed',
                )

            # Update execution record
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_workflow.WorkflowExecution)
                .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
                .values(
                    status=context.status.value,
                    end_time=context.end_time,
                    error=error_message,
                    variables=context.variables,
                )
            )

            if context.status == ExecutionStatus.FAILED:
                raise WorkflowExecutionFailedError(
                    execution_uuid,
                    error_message,
                    details=context.error or error_message,
                )
        except asyncio.TimeoutError as e:
            timeout_message = f'Workflow execution timed out after {max_execution_time} seconds'
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_workflow.WorkflowExecution)
                .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
                .values(
                    status=ExecutionStatus.CANCELLED.value,
                    end_time=datetime.now(),
                    error=timeout_message,
                )
            )
            raise WorkflowExecutionFailedError(
                execution_uuid,
                timeout_message,
                details=str(e),
            ) from e
        except WorkflowExecutionFailedError:
            raise
        except Exception as e:
            # Update execution record with error
            await self.ap.persistence_mgr.execute_async(
                sqlalchemy.update(persistence_workflow.WorkflowExecution)
                .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
                .values(
                    status=ExecutionStatus.FAILED.value,
                    end_time=datetime.now(),
                    error=str(e),
                )
            )
            raise WorkflowExecutionFailedError(
                execution_uuid,
                str(e),
                details=context.error or str(e),
            ) from e

        return execution_uuid
    
    async def get_executions(
        self,
        workflow_uuid: Optional[str] = None,
        limit: int = 50,
        offset: int = 0,
        status: Optional[str] = None
    ) -> dict:
        """Get workflow executions with total count"""
        base_filter = []
        
        if workflow_uuid:
            base_filter.append(
                persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid
            )
        
        if status:
            base_filter.append(
                persistence_workflow.WorkflowExecution.status == status
            )
        
        # Get total count
        count_query = sqlalchemy.select(
            sqlalchemy.func.count(persistence_workflow.WorkflowExecution.uuid)
        )
        for f in base_filter:
            count_query = count_query.where(f)
        count_result = await self.ap.persistence_mgr.execute_async(count_query)
        total = count_result.scalar() or 0
        
        # Get paginated results
        query = sqlalchemy.select(persistence_workflow.WorkflowExecution)
        for f in base_filter:
            query = query.where(f)
        
        query = query.order_by(
            persistence_workflow.WorkflowExecution.created_at.desc()
        ).limit(limit).offset(offset)
        
        result = await self.ap.persistence_mgr.execute_async(query)
        executions = result.all()
        
        return {
            'executions': [
                self.ap.persistence_mgr.serialize_model(
                    persistence_workflow.WorkflowExecution, 
                    execution
                )
                for execution in executions
            ],
            'total': total,
        }
    
    async def get_execution(self, execution_uuid: str) -> Optional[dict]:
        """Get a single execution by UUID"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowExecution).where(
                persistence_workflow.WorkflowExecution.uuid == execution_uuid
            )
        )
        
        execution = result.first()
        
        if execution is None:
            return None
        
        return self.ap.persistence_mgr.serialize_model(
            persistence_workflow.WorkflowExecution, 
            execution
        )
    
    async def get_node_types(self) -> list[dict]:
        """Get all available node types"""
        # Process pending registrations
        self.registry.process_pending_registrations()
        node_types = self.registry.list_all()
        
        # Enrich node schemas with pipeline config metadata
        return self._enrich_node_type_configs(node_types)
    
    async def get_node_types_by_category(self) -> dict[str, list[dict]]:
        """Get node types organized by category"""
        self.registry.process_pending_registrations()
        categories = self.registry.get_categories()
        
        # Enrich node schemas with pipeline config metadata
        for category, nodes in categories.items():
            categories[category] = self._enrich_node_type_configs(nodes)
        
        return categories

    async def get_node_types_by_category_meta(self) -> list[dict]:
        """Get workflow node category metadata for the editor UI."""
        self.registry.process_pending_registrations()
        categories = self.registry.get_categories()

        ordered_categories = ['trigger', 'process', 'control', 'action', 'integration', 'misc']
        label_map = {
            'trigger': {'en-US': 'Trigger', 'en': 'Trigger', 'zh-Hans': '触发器', 'zh-CN': '触发器'},
            'process': {'en-US': 'Process', 'en': 'Process', 'zh-Hans': '处理', 'zh-CN': '处理'},
            'control': {'en-US': 'Control', 'en': 'Control', 'zh-Hans': '控制', 'zh-CN': '控制'},
            'action': {'en-US': 'Action', 'en': 'Action', 'zh-Hans': '动作', 'zh-CN': '动作'},
            'integration': {'en-US': 'Integration', 'en': 'Integration', 'zh-Hans': '集成', 'zh-CN': '集成'},
            'misc': {'en-US': 'Misc', 'en': 'Misc', 'zh-Hans': '其他', 'zh-CN': '其他'},
        }

        result = []
        for order, category_name in enumerate(ordered_categories):
            if category_name not in categories:
                continue
            result.append({
                'name': category_name,
                'label': label_map.get(category_name, {
                    'en-US': category_name,
                    'en': category_name,
                    'zh-Hans': category_name,
                    'zh-CN': category_name,
                }),
                'order': order,
            })

        return result
    
    def _enrich_node_type_configs(self, node_types: list[dict]) -> list[dict]:
        """Enrich node schemas with node YAML config metadata if available"""
        # Get workflow node configs loaded from YAML files
        workflow_node_configs = getattr(self.ap, 'workflow_node_configs', {})
        
        for node_schema in node_types:
            node_type = node_schema.get('type', '')
            
            # First, try to load config from dedicated node YAML file
            if node_type in workflow_node_configs:
                node_config = workflow_node_configs[node_type]
                
                # Enrich inputs from YAML if Python class has empty inputs
                yaml_inputs = node_config.get('inputs', [])
                if yaml_inputs and not node_schema.get('inputs'):
                    node_schema['inputs'] = [
                        self._normalize_port_item(inp) for inp in yaml_inputs
                    ]
                
                # Enrich outputs from YAML if Python class has empty outputs
                yaml_outputs = node_config.get('outputs', [])
                if yaml_outputs and not node_schema.get('outputs'):
                    node_schema['outputs'] = [
                        self._normalize_port_item(out) for out in yaml_outputs
                    ]
                
                # Enrich config_schema from YAML
                yaml_configs = node_config.get('config', [])
                
                # Normalize and add YAML configs to config_schema
                existing_names = {cfg.get('name') for cfg in node_schema.get('config_schema', [])}
                for cfg in yaml_configs:
                    if cfg.get('name') not in existing_names:
                        normalized_cfg = self._normalize_config_item(cfg)
                        node_schema['config_schema'].append(normalized_cfg)
                        existing_names.add(cfg.get('name'))
            
            # Second, try to load from pipeline config metadata (for backward compatibility)
            config_schema_source = node_schema.get('config_schema_source')
            config_stages = node_schema.get('config_stages', [])
            
            if config_schema_source and config_stages:
                # Get pipeline config metadata
                pipeline_meta = self._get_pipeline_config_meta(config_schema_source)
                if pipeline_meta:
                    # Extract config items from specified stages
                    enriched_configs = []
                    for stage_name in config_stages:
                        stage_data = self._find_stage_in_pipeline(pipeline_meta, stage_name)
                        if stage_data and 'config' in stage_data:
                            enriched_configs.extend(stage_data['config'])
                    
                    # Merge with existing config_schema (avoid duplicates by name)
                    existing_names = {cfg.get('name') for cfg in node_schema.get('config_schema', [])}
                    for cfg in enriched_configs:
                        if cfg.get('name') not in existing_names:
                            # Normalize config item format for frontend compatibility
                            normalized_cfg = self._normalize_config_item(cfg)
                            node_schema['config_schema'].append(normalized_cfg)
                            existing_names.add(cfg.get('name'))
        
        return node_types
    
    def _normalize_port_item(self, port: dict) -> dict:
        """Normalize a port (input/output) item from YAML format to frontend-compatible format"""
        label = port.get('label')
        if isinstance(label, dict):
            normalized_label = {
                'en_US': label.get('en_US', label.get('en', '')),
                'en': label.get('en_US', label.get('en', '')),
                'zh_Hans': label.get('zh_Hans', label.get('zh', '')),
            }
            port = {**port, 'label': normalized_label}
        else:
            name = port.get('name', '')
            port = {**port, 'label': {
                'en_US': name,
                'en': name,
                'zh_Hans': name,
            }}

        description = port.get('description')
        if isinstance(description, dict):
            normalized_desc = {
                'en_US': description.get('en_US', description.get('en', '')),
                'en': description.get('en_US', description.get('en', '')),
                'zh_Hans': description.get('zh_Hans', description.get('zh', '')),
            }
            port = {**port, 'description': normalized_desc}
        else:
            port = {**port, 'description': {
                'en_US': '',
                'en': '',
                'zh_Hans': '',
            }}

        return port

    def _normalize_config_item(self, cfg: dict) -> dict:
        """Normalize config item from YAML format to frontend-compatible format"""
        # Ensure label is in proper i18n format (using underscore format like en_US, zh_Hans)
        label = cfg.get('label')
        if isinstance(label, dict):
            # Convert YAML label to frontend i18n format
            normalized_label = {
                'en_US': label.get('en_US', label.get('en', '')),
                'en': label.get('en_US', label.get('en', '')),
                'zh_Hans': label.get('zh_Hans', label.get('zh', '')),
            }
            cfg = {**cfg, 'label': normalized_label}
        else:
            # Create default label from name (handles both None and non-dict cases)
            name = cfg.get('name', '')
            cfg = {**cfg, 'label': {
                'en_US': name,
                'en': name,
                'zh_Hans': name,
            }}
        
        # Ensure description is in proper i18n format
        description = cfg.get('description')
        if isinstance(description, dict):
            normalized_desc = {
                'en_US': description.get('en_US', description.get('en', '')),
                'en': description.get('en_US', description.get('en', '')),
                'zh_Hans': description.get('zh_Hans', description.get('zh', '')),
            }
            cfg = {**cfg, 'description': normalized_desc}
        else:
            cfg = {**cfg, 'description': {
                'en_US': '',
                'en': '',
                'zh_Hans': '',
            }}
        
        # Handle options - convert from list of {name, label} to list of {name, label}
        options = cfg.get('options')
        if isinstance(options, list) and len(options) > 0 and isinstance(options[0], dict):
            normalized_options = []
            for opt in options:
                opt_label = opt.get('label')
                if isinstance(opt_label, dict):
                    normalized_opt_label = {
                        'en_US': opt_label.get('en_US', opt_label.get('en', '')),
                        'en': opt_label.get('en_US', opt_label.get('en', '')),
                        'zh_Hans': opt_label.get('zh_Hans', opt_label.get('zh', '')),
                    }
                else:
                    normalized_opt_label = {
                        'en_US': opt.get('name', ''),
                        'en': opt.get('name', ''),
                        'zh_Hans': opt.get('name', ''),
                    }
                normalized_options.append({**opt, 'label': normalized_opt_label})
            cfg = {**cfg, 'options': normalized_options}
        
        return cfg
    
    def _get_pipeline_config_meta(self, source: str) -> Optional[dict]:
        """Get pipeline config metadata by source prefix"""
        if source.startswith('pipeline:'):
            parts = source.split(':')
            if len(parts) >= 2:
                pipeline_type = parts[1]  # e.g., 'trigger', 'ai', 'output', 'safety'
                meta_attr = f'pipeline_config_meta_{pipeline_type}'
                return getattr(self.ap, meta_attr, None)
        return None
    
    def _find_stage_in_pipeline(self, pipeline_meta: dict, stage_name: str) -> Optional[dict]:
        """Find a stage in pipeline config metadata"""
        stages = pipeline_meta.get('stages', [])
        for stage in stages:
            if stage.get('name') == stage_name:
                return stage
        return None
    
    async def get_versions(self, workflow_uuid: str) -> list[dict]:
        """Get version history for a workflow"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowVersion)
            .where(persistence_workflow.WorkflowVersion.workflow_uuid == workflow_uuid)
            .order_by(persistence_workflow.WorkflowVersion.version.desc())
        )
        
        versions = result.all()
        
        return [
            self.ap.persistence_mgr.serialize_model(
                persistence_workflow.WorkflowVersion, 
                version
            )
            for version in versions
        ]
    
    async def rollback_to_version(self, workflow_uuid: str, version: int) -> None:
        """Rollback workflow to a specific version"""
        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowVersion)
            .where(
                persistence_workflow.WorkflowVersion.workflow_uuid == workflow_uuid,
                persistence_workflow.WorkflowVersion.version == version
            )
        )
        
        version_record = result.first()
        
        if version_record is None:
            raise ValueError(f'Version {version} not found for workflow {workflow_uuid}')
        
        # Update workflow with the old version's definition
        await self.update_workflow(workflow_uuid, {
            'definition': version_record.definition,
            'global_config': version_record.global_config,
        })
    
    async def _save_version_history(
        self, 
        workflow_uuid: str, 
        version: int, 
        definition: dict,
        global_config: dict
    ) -> None:
        """Save workflow version to history"""
        # Check if version already exists (database-agnostic)
        existing = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowVersion).where(
                persistence_workflow.WorkflowVersion.workflow_uuid == workflow_uuid,
                persistence_workflow.WorkflowVersion.version == version,
            )
        )
        if existing.first() is not None:
            return
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.WorkflowVersion).values(
                workflow_uuid=workflow_uuid,
                version=version,
                definition=definition,
                global_config=global_config,
            )
        )
    
    def _serialize_workflow(self, workflow) -> dict:
        """Serialize workflow entity to dict"""
        result = self.ap.persistence_mgr.serialize_model(
            persistence_workflow.Workflow,
            workflow
        )
        
        # Extract nodes and edges from definition to top level for frontend compatibility
        definition = result.get('definition', {})
        if isinstance(definition, dict):
            result['nodes'] = definition.get('nodes', [])
            result['edges'] = definition.get('edges', [])
            result['variables'] = definition.get('variables', {})
        else:
            result['nodes'] = []
            result['edges'] = []
            result['variables'] = {}
        
        return result
    
    async def update_workflow_extensions(
        self,
        workflow_uuid: str,
        bound_plugins: list[dict],
        bound_mcp_servers: Optional[list[str]] = None,
        enable_all_plugins: bool = True,
        enable_all_mcp_servers: bool = True,
    ) -> None:
        """Update the bound plugins and MCP servers for a workflow"""
        workflow = await self.get_workflow(workflow_uuid)
        if workflow is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        extensions_preferences = workflow.get('extensions_preferences', {})
        extensions_preferences['enable_all_plugins'] = enable_all_plugins
        extensions_preferences['enable_all_mcp_servers'] = enable_all_mcp_servers
        extensions_preferences['plugins'] = bound_plugins
        if bound_mcp_servers is not None:
            extensions_preferences['mcp_servers'] = bound_mcp_servers
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.Workflow)
            .where(persistence_workflow.Workflow.uuid == workflow_uuid)
            .values(extensions_preferences=extensions_preferences)
        )
    
    async def publish_workflow(self, workflow_uuid: str) -> None:
        """Publish a workflow (set is_enabled to True)"""
        workflow = await self.get_workflow(workflow_uuid)
        if workflow is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.Workflow)
            .where(persistence_workflow.Workflow.uuid == workflow_uuid)
            .values(is_enabled=True)
        )
    
    async def unpublish_workflow(self, workflow_uuid: str) -> None:
        """Unpublish a workflow (set is_enabled to False)"""
        workflow = await self.get_workflow(workflow_uuid)
        if workflow is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.Workflow)
            .where(persistence_workflow.Workflow.uuid == workflow_uuid)
            .values(is_enabled=False)
        )
    
    async def get_workflow_stats(self, workflow_uuid: str) -> dict:
        """Get workflow statistics"""
        # Verify workflow exists
        workflow = await self.get_workflow(workflow_uuid)
        if workflow is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        # Get total execution count
        total_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(sqlalchemy.func.count(persistence_workflow.WorkflowExecution.uuid))
            .where(persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid)
        )
        total_executions = total_result.scalar()
        
        # Get executions by status
        status_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(
                persistence_workflow.WorkflowExecution.status,
                sqlalchemy.func.count(persistence_workflow.WorkflowExecution.uuid)
            )
            .where(persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid)
            .group_by(persistence_workflow.WorkflowExecution.status)
        )
        status_counts = {row[0]: row[1] for row in status_result.all()}
        
        # Get success and failure counts
        success_count = status_counts.get('completed', 0)
        failed_count = status_counts.get('failed', 0)
        pending_count = status_counts.get('pending', 0)
        running_count = status_counts.get('running', 0)
        cancelled_count = status_counts.get('cancelled', 0)
        
        # Calculate success rate (as 0-1 ratio for frontend)
        success_rate = 0.0
        if total_executions > 0:
            success_rate = success_count / total_executions
        
        # Get average execution time (for completed executions)
        avg_time_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(
                sqlalchemy.func.avg(
                    sqlalchemy.func.strftime('%s', persistence_workflow.WorkflowExecution.end_time) -
                    sqlalchemy.func.strftime('%s', persistence_workflow.WorkflowExecution.start_time)
                )
            )
            .where(
                persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid,
                persistence_workflow.WorkflowExecution.status == 'completed',
                persistence_workflow.WorkflowExecution.start_time.isnot(None),
                persistence_workflow.WorkflowExecution.end_time.isnot(None)
            )
        )
        avg_execution_time = avg_time_result.scalar()
        # Ensure we always return a valid number, not None
        avg_execution_time = float(avg_execution_time) if avg_execution_time is not None else 0.0
        
        # Get last execution time
        last_execution_result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.select(persistence_workflow.WorkflowExecution.created_at)
            .where(persistence_workflow.WorkflowExecution.workflow_uuid == workflow_uuid)
            .order_by(persistence_workflow.WorkflowExecution.created_at.desc())
            .limit(1)
        )
        last_execution = last_execution_result.first()
        
        return {
            'total_executions': int(total_executions),
            'successful_executions': int(success_count),
            'failed_executions': int(failed_count),
            'pending_executions': int(pending_count),
            'running_executions': int(running_count),
            'cancelled_executions': int(cancelled_count),
            'success_rate': round(success_rate, 4),  # Already 0-1 ratio
            'average_duration_ms': round(avg_execution_time * 1000, 2) if avg_execution_time > 0 else 0,  # Convert to milliseconds
            'last_execution_time': last_execution[0] if last_execution else None,
        }
    
    async def start_debug_execution(
        self,
        workflow_uuid: str,
        context: Optional[dict] = None,
        variables: Optional[dict] = None,
        breakpoints: Optional[list[str]] = None
    ) -> str:
        """Start a debug execution and return execution ID"""
        workflow = await self.get_workflow(workflow_uuid)
        if workflow is None:
            raise ValueError(f'Workflow {workflow_uuid} not found')
        
        execution_uuid = str(uuid.uuid4())
        execution_record = {
            'uuid': execution_uuid,
            'workflow_uuid': workflow_uuid,
            'workflow_version': workflow.get('version', 1),
            'status': ExecutionStatus.PENDING.value,
            'trigger_type': 'debug',
            'trigger_data': {'context': context or {}, 'breakpoints': breakpoints or []},
            'variables': variables or {},
            'start_time': datetime.now(),
        }
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.insert(persistence_workflow.WorkflowExecution).values(**execution_record)
        )
        
        return execution_uuid
    
    async def pause_debug_execution(self, workflow_uuid: str, execution_uuid: str) -> None:
        """Pause a debug execution"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowExecution)
            .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
            .values(status='paused')
        )
    
    async def resume_debug_execution(self, workflow_uuid: str, execution_uuid: str) -> None:
        """Resume a paused debug execution"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowExecution)
            .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
            .values(status='running')
        )
    
    async def step_debug_execution(self, workflow_uuid: str, execution_uuid: str) -> dict:
        """Step through a debug execution"""
        return {'status': 'stepped', 'execution_uuid': execution_uuid}
    
    async def stop_debug_execution(self, workflow_uuid: str, execution_uuid: str) -> None:
        """Stop a debug execution"""
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowExecution)
            .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
            .values(
                status='cancelled',
                end_time=datetime.now()
            )
        )
    
    async def get_debug_state(self, workflow_uuid: str, execution_uuid: str) -> dict:
        """Get the current debug state"""
        execution = await self.get_execution(execution_uuid)
        if execution is None:
            raise ValueError(f'Execution {execution_uuid} not found')
        
        return {
            'execution_uuid': execution_uuid,
            'status': execution.get('status'),
            'variables': execution.get('variables', {}),
        }
    
    async def cancel_execution(self, execution_uuid: str) -> None:
        """Cancel a workflow execution"""
        execution = await self.get_execution(execution_uuid)
        if execution is None:
            raise ValueError(f'Execution {execution_uuid} not found')
        
        if execution.get('status') not in ['pending', 'running']:
            raise RuntimeError(f'Cannot cancel execution with status {execution.get("status")}')
        
        await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowExecution)
            .where(persistence_workflow.WorkflowExecution.uuid == execution_uuid)
            .values(
                status='cancelled',
                end_time=datetime.now()
            )
        )
    
    async def rerun_execution(self, workflow_uuid: str, execution_uuid: str) -> str:
        """Rerun a workflow execution with the same trigger data"""
        original_execution = await self.get_execution(execution_uuid)
        if original_execution is None:
            raise ValueError(f'Execution {execution_uuid} not found')
        
        trigger_data = original_execution.get('trigger_data', {})
        new_execution_uuid = await self.execute_workflow(
            workflow_uuid,
            trigger_type=original_execution.get('trigger_type', 'manual'),
            trigger_data=trigger_data
        )
        
        return new_execution_uuid

    async def cleanup_stale_executions(self, timeout_seconds: int | None = None) -> int:
        """Cancel stale pending/running workflow executions."""
        effective_timeout = timeout_seconds or self.STALE_EXECUTION_TIMEOUT_SECONDS
        if effective_timeout <= 0:
            effective_timeout = self.STALE_EXECUTION_TIMEOUT_SECONDS

        stale_before = datetime.now() - timedelta(seconds=effective_timeout)
        stale_statuses = [
            ExecutionStatus.PENDING.value,
            ExecutionStatus.RUNNING.value,
            ExecutionStatus.WAITING.value,
        ]

        result = await self.ap.persistence_mgr.execute_async(
            sqlalchemy.update(persistence_workflow.WorkflowExecution)
            .where(
                persistence_workflow.WorkflowExecution.status.in_(stale_statuses),
                persistence_workflow.WorkflowExecution.start_time.isnot(None),
                persistence_workflow.WorkflowExecution.start_time < stale_before,
            )
            .values(
                status=ExecutionStatus.CANCELLED.value,
                end_time=datetime.now(),
                error=f'Workflow execution auto-cancelled after exceeding {effective_timeout} seconds',
            )
        )

        return int(getattr(result, 'rowcount', 0) or 0)
    
    async def get_execution_logs(
        self,
        workflow_uuid: str,
        execution_uuid: str,
        limit: int = 100,
        offset: int = 0
    ) -> dict:
        """Get execution logs for a workflow execution"""
        execution = await self.get_execution(execution_uuid)
        if execution is None:
            raise ValueError(f'Execution {execution_uuid} not found')
        
        query = sqlalchemy.select(persistence_workflow.WorkflowNodeExecution).where(
            persistence_workflow.WorkflowNodeExecution.execution_uuid == execution_uuid
        ).order_by(
            persistence_workflow.WorkflowNodeExecution.id.asc()
        ).limit(limit).offset(offset)
        
        result = await self.ap.persistence_mgr.execute_async(query)
        node_executions = result.all()
        
        logs = [
            self.ap.persistence_mgr.serialize_model(
                persistence_workflow.WorkflowNodeExecution,
                node_exec
            )
            for node_exec in node_executions
        ]
        
        return {'logs': logs, 'total': len(logs)}

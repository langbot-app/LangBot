"""Call Workflow Node - invoke an existing workflow

Node metadata is loaded from: ../../templates/metadata/nodes/call_workflow.yaml
"""

from __future__ import annotations

from typing import Any, Optional

from langbot_plugin.api.entities.builtin.workflow import ExecutionContext

from ..node import WorkflowNode, workflow_node


@workflow_node('call_workflow')
class CallWorkflowNode(WorkflowNode):
    """Call workflow node - invoke an existing workflow"""

    category = 'action'

    async def execute(self, inputs: dict[str, Any], context: ExecutionContext) -> dict[str, Any]:
        if not self.ap:
            raise RuntimeError('Application instance not available — cannot call workflow')

        # Get workflow reference from config
        workflow_ref = str(self.get_config('workflow_uuid', '') or '').strip()
        if not workflow_ref:
            raise ValueError('No workflow configured for call workflow node')

        # Get workflow definition from service
        workflow_data = await self.ap.workflow_service.get_workflow(workflow_ref)
        if workflow_data is None:
            raise ValueError(f'Workflow not found: {workflow_ref}')

        workflow_uuid = str(workflow_data.get('uuid', '') or '')
        if not workflow_uuid:
            raise ValueError(f'Workflow UUID missing for: {workflow_ref}')

        # Build variables to pass to the called workflow
        variables = dict(inputs.get('variables', {}) or {})

        # Inherit current workflow variables if configured
        if self.get_config('inherit_variables', True):
            for key, value in (context.variables or {}).items():
                if key not in variables:
                    variables[key] = value

        # Add context markers for debugging
        variables['_called_from_workflow'] = True
        variables['_parent_workflow_id'] = context.workflow_id
        variables['_parent_execution_id'] = context.execution_id

        # Execute the workflow
        execution_id = await self.ap.workflow_service.execute_workflow(
            workflow_uuid=workflow_uuid,
            trigger_type='workflow_call',
            trigger_data={
                'variables': variables,
                'parent_execution_id': context.execution_id,
            },
            session_id=context.session_id,
            user_id=context.user_id,
            bot_id=context.bot_id,
        )

        # Get execution result
        execution = await self.ap.workflow_service.get_execution(execution_id)
        if execution is None:
            raise ValueError(f'Execution result not found: {execution_id}')

        # Build result
        result = {
            'workflow_uuid': workflow_uuid,
            'workflow_name': workflow_data.get('name', ''),
            'execution_id': execution_id,
            'status': execution.get('status', 'unknown'),
            'variables': execution.get('variables', {}),
            'error': execution.get('error'),
        }

        return {
            'result': result,
            'status': execution.get('status', 'unknown'),
            'error': execution.get('error'),
        }

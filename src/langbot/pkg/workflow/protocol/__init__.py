"""Host-side workflow protocol models."""

from . import entities, query

# ExecutionContext references WorkflowQuery only for type checking; resolve it here.
entities.ExecutionContext.model_rebuild(_types_namespace={'WorkflowQuery': query.WorkflowQuery})

"""Core workflow nodes package"""

# Import all node modules to trigger registration
# Trigger nodes
from . import message_trigger
from . import cron_trigger
from . import webhook_trigger
from . import event_trigger

# Process nodes
from . import llm_call
from . import code_executor
from . import http_request
from . import data_transform
from . import question_classifier
from . import parameter_extractor
from . import knowledge_retrieval

# Control nodes
from . import condition
from . import switch
from . import loop
from . import iterator
from . import parallel
from . import wait
from . import merge
from . import variable_aggregator

# Action nodes
from . import send_message
from . import reply_message
from . import call_pipeline
from . import store_data
from . import set_variable
from . import opening_statement
from . import end

# Integration nodes
from . import database_query
from . import redis_operation
from . import mcp_tool
from . import memory_store
from . import dify_workflow
from . import dify_knowledge_query
from . import n8n_workflow
from . import langflow_flow
from . import coze_bot
# from . import plugin_call

__all__ = [
    # Trigger nodes
    'message_trigger',
    'cron_trigger',
    'webhook_trigger',
    'event_trigger',
    # Process nodes
    'llm_call',
    'code_executor',
    'http_request',
    'data_transform',
    'question_classifier',
    'parameter_extractor',
    'knowledge_retrieval',
    # Control nodes
    'condition',
    'switch',
    'loop',
    'iterator',
    'parallel',
    'wait',
    'merge',
    'variable_aggregator',
    # Action nodes
    'send_message',
    'reply_message',
    'call_pipeline',
    'store_data',
    'set_variable',
    'opening_statement',
    'end',
    # Integration nodes
    'database_query',
    'redis_operation',
    'mcp_tool',
    'memory_store',
    'dify_workflow',
    'dify_knowledge_query',
    'n8n_workflow',
    'langflow_flow',
    'coze_bot',
]

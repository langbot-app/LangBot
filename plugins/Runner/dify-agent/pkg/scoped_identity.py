"""Namespace upstream identity from the current trusted invocation binding."""

import hashlib
import json
import os

from langbot_plugin.api.proxies.invocation import current_binding


def _scope(binding):
    return [binding.instance_uuid, binding.workspace_uuid, binding.installation_uuid]


def scoped_identity(runner, ctx, local_id):
    handler = getattr(runner, "_plugin_runtime_handler", None)
    # The active invocation's binding is task-local; bound_action_context is only
    # the permanently bound connection (dedicated workers).
    binding = current_binding(handler) if handler is not None else None
    if binding is None:
        binding = getattr(handler, "bound_action_context", None)
    if binding is not None:
        scope = _scope(binding)
    else:
        if os.environ.get("LANGBOT_PLUGIN_RUNTIME_PROFILE") == "shared":
            # Shared workers always carry a trusted invocation binding; without one
            # an upstream identity would collide across installations, so refuse
            # before any provider call rather than fall back to a weaker scope.
            raise RuntimeError(
                "shared invocation has no trusted installation binding; refusing to build an upstream identity"
            )
        workspace = getattr(ctx.conversation, "workspace_id", None)
        if not workspace:
            # Dedicated OSS without a Workspace keeps its documented legacy IDs.
            return local_id
        scope = [workspace]
    encoded = json.dumps([scope, local_id], ensure_ascii=False, separators=(",", ":")).encode()
    return "lb_" + hashlib.sha256(encoded).hexdigest()

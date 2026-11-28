"""HTTP compatibility exports for transport-neutral API authorization.

Authorization primitives live in :mod:`langbot.pkg.api.authz` so application
operations can be used by HTTP, MCP, assistant and CLI adapters without
importing a transport package.  Keep this module as a compatibility re-export
for existing HTTP service/controller imports.
"""

from ..authz import *  # noqa: F401,F403

from __future__ import annotations

import json

from ...config import manager as config_mgr
from ...config.impls import pymodule


load_python_module_config = config_mgr.load_python_module_config
load_json_config = config_mgr.load_json_config

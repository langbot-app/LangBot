"""Run existing genuine SDK RPC fixture against this exact extracted artifact."""

import asyncio
import runpy
import sys
from pathlib import Path

sys.path.insert(0, str(Path.cwd()))
probe = runpy.run_path(str(Path(__file__).resolve().parents[1] / "tests/fixtures/real_sdk_runtime_probe.py"))
probe["probe"].__globals__["PLUGIN"] = sys.argv[1]
asyncio.run(probe["probe"](Path(sys.argv[2]).resolve()))

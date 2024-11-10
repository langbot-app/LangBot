from __future__ import annotations

import asyncio
import os

import quart
import quart_cors

from ....core import app
from .groups import logs, system, settings, plugins, stats
from . import group


class HTTPController:

    ap: app.Application

    quart_app: quart.Quart

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.quart_app = quart.Quart(__name__)
        quart_cors.cors(self.quart_app, allow_origin="*")

    async def initialize(self) -> None:
        await self.register_routes()

    async def run(self) -> None:
        if self.ap.system_cfg.data["http-api"]["enable"]:

            async def shutdown_trigger_placeholder():
                while True:
                    await asyncio.sleep(1)

            self.ap.task_mgr.create_task(
                self.quart_app.run_task(
                    host=self.ap.system_cfg.data["http-api"]["host"],
                    port=self.ap.system_cfg.data["http-api"]["port"],
                    shutdown_trigger=shutdown_trigger_placeholder,
                ),
                name="http-api-quart",
            )

    async def register_routes(self) -> None:

        @self.quart_app.route("/healthz")
        async def healthz():
            return {"code": 0, "msg": "ok"}

        for g in group.preregistered_groups:
            ginst = g(self.ap, self.quart_app)
            await ginst.initialize()

        frontend_path = "web/dist"

        @self.quart_app.route("/")
        async def index():
            return await quart.send_from_directory(frontend_path, "index.html")

        @self.quart_app.route("/<path:path>")
        async def static_file(path: str):
            return await quart.send_from_directory(frontend_path, path)

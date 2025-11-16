from __future__ import annotations

import asyncio
import os

import quart
import quart_cors
from werkzeug.exceptions import RequestEntityTooLarge

from ....core import app, entities as core_entities
from ....utils import importutil

from . import groups
from . import group
from .groups import provider as groups_provider
from .groups import platform as groups_platform
from .groups import pipelines as groups_pipelines
from .groups import knowledge as groups_knowledge
from .groups import resources as groups_resources

importutil.import_modules_in_pkg(groups)
importutil.import_modules_in_pkg(groups_provider)
importutil.import_modules_in_pkg(groups_platform)
importutil.import_modules_in_pkg(groups_pipelines)
importutil.import_modules_in_pkg(groups_knowledge)
importutil.import_modules_in_pkg(groups_resources)


class HTTPController:
    ap: app.Application

    quart_app: quart.Quart

    def __init__(self, ap: app.Application) -> None:
        self.ap = ap
        self.quart_app = quart.Quart(__name__)
        quart_cors.cors(self.quart_app, allow_origin='*')

        # Set maximum content length to prevent large file uploads
        self.quart_app.config['MAX_CONTENT_LENGTH'] = group.MAX_FILE_SIZE

    async def initialize(self) -> None:
        # Register custom error handler for file size limit
        @self.quart_app.errorhandler(RequestEntityTooLarge)
        async def handle_request_entity_too_large(e):
            return quart.jsonify(
                {
                    'code': 400,
                    'msg': 'File size exceeds 10MB limit. Please split large files into smaller parts.',
                }
            ), 400

        await self.register_routes()

    async def run(self) -> None:
        if True:

            async def shutdown_trigger_placeholder():
                while True:
                    await asyncio.sleep(1)

            async def exception_handler(*args, **kwargs):
                try:
                    await self.quart_app.run_task(*args, **kwargs)
                except Exception as e:
                    self.ap.logger.error(f'Failed to start HTTP service: {e}')

            self.ap.task_mgr.create_task(
                exception_handler(
                    host='0.0.0.0',
                    port=self.ap.instance_config.data['api']['port'],
                    shutdown_trigger=shutdown_trigger_placeholder,
                ),
                name='http-api-quart',
                scopes=[core_entities.LifecycleControlScope.APPLICATION],
            )

            # await asyncio.sleep(5)

    async def register_routes(self) -> None:
        @self.quart_app.route('/healthz')
        async def healthz():
            return {'code': 0, 'msg': 'ok'}

        for g in group.preregistered_groups:
            ginst = g(self.ap, self.quart_app)
            await ginst.initialize()

        from ....utils import paths

        frontend_path = paths.get_frontend_path()

        @self.quart_app.route('/')
        async def index():
            return await quart.send_from_directory(frontend_path, 'index.html', mimetype='text/html')

        @self.quart_app.route('/<path:path>')
        async def static_file(path: str):
            if not (
                os.path.exists(os.path.join(frontend_path, path)) and os.path.isfile(os.path.join(frontend_path, path))
            ):
                if os.path.exists(os.path.join(frontend_path, path + '.html')):
                    path += '.html'
                else:
                    return await quart.send_from_directory(frontend_path, '404.html')

            mimetype = None

            if path.endswith('.html'):
                mimetype = 'text/html'
            elif path.endswith('.js'):
                mimetype = 'application/javascript'
            elif path.endswith('.css'):
                mimetype = 'text/css'
            elif path.endswith('.png'):
                mimetype = 'image/png'
            elif path.endswith('.jpg'):
                mimetype = 'image/jpeg'
            elif path.endswith('.jpeg'):
                mimetype = 'image/jpeg'
            elif path.endswith('.gif'):
                mimetype = 'image/gif'
            elif path.endswith('.svg'):
                mimetype = 'image/svg+xml'
            elif path.endswith('.ico'):
                mimetype = 'image/x-icon'
            elif path.endswith('.json'):
                mimetype = 'application/json'
            elif path.endswith('.txt'):
                mimetype = 'text/plain'

            response = await quart.send_from_directory(frontend_path, path, mimetype=mimetype)
            response.headers['Cache-Control'] = 'no-cache, no-store, must-revalidate'
            response.headers['Pragma'] = 'no-cache'
            response.headers['Expires'] = '0'
            return response

from __future__ import annotations

import pytest


@pytest.fixture(scope='module')
def http_controller_cls(mock_circular_import_chain):
    """Import HTTPController under each module's circular-import isolation."""
    from langbot.pkg.api.http.controller.main import HTTPController

    return HTTPController

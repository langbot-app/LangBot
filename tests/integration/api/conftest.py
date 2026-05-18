from __future__ import annotations

import pytest


def dedupe_preregistered_groups() -> None:
    """Keep API integration route registration isolated across test modules."""
    from langbot.pkg.api.http.controller import group

    seen: set[tuple[str, str]] = set()
    unique_groups = []
    for group_cls in group.preregistered_groups:
        key = (group_cls.name, group_cls.path)
        if key in seen:
            continue
        seen.add(key)
        unique_groups.append(group_cls)

    group.preregistered_groups[:] = unique_groups


@pytest.fixture(scope='module')
def http_controller_cls(mock_circular_import_chain):
    """Import HTTPController under each module's circular-import isolation."""
    from langbot.pkg.api.http.controller.main import HTTPController

    dedupe_preregistered_groups()
    return HTTPController

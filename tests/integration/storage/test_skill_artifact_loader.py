"""Real SQLite/opt-in storage path from activated Skill through model content."""
# ruff: noqa: F811

import base64
import io
import json
from types import SimpleNamespace
import zipfile

import pytest
import sqlalchemy as sa
from quart.datastructures import FileStorage
from pypdf import PdfWriter

from langbot.pkg.entity.persistence.agent_run import AgentRun
from langbot.pkg.provider.tools.loaders.skill import register_activated_skill
from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader
from langbot.pkg.storage.artifacts import ArtifactError
from tests.integration.skill.test_persistent_skill_replicas import _data, _zip_package, _NAME, _PNG, _GUIDE
from tests.integration.storage.test_artifact_run_outputs import _start_run, _end_run
from tests.integration.storage.test_artifacts import (
    artifact_replicas,  # noqa: F401
    persistence_case,  # noqa: F401
    replicas,  # noqa: F401
)

pytestmark = [pytest.mark.integration, pytest.mark.asyncio]


async def test_real_run_skill_loader_text_png_pdf_and_revocation(artifact_replicas):
    case = artifact_replicas
    package = io.BytesIO(_zip_package())
    document = PdfWriter()
    document.add_blank_page(width=72, height=72)
    pdf_stream = io.BytesIO()
    document.write(pdf_stream)
    pdf = pdf_stream.getvalue()
    with zipfile.ZipFile(package, 'a') as archive:
        archive.writestr(f'{_NAME}/asset.png', _PNG)
        archive.writestr(f'{_NAME}/asset.pdf', pdf)
    installed = await _data(
        await case.a.client.post(
            '/api/v1/skills/install/upload',
            headers=case.headers,
            files={'file': FileStorage(io.BytesIO(package.getvalue()), filename='probe.zip')},
        )
    )
    revision = installed['skills'][0]['revision']
    context = await _start_run(case)
    run_id = context.trigger_principal.run_id
    async with case.a.app.persistence_mgr.tenant_uow(context.workspace_uuid) as uow:
        await uow.execute(
            sa.update(AgentRun)
            .where(AgentRun.run_id == run_id)
            .values(
                metadata_json=json.dumps({'activated_skills': {_NAME: revision}}),
            )
        )
    query = SimpleNamespace(variables={}, _execution_context=context, _agent_run_session={'run_id': run_id})
    register_activated_skill(query, {'name': _NAME, 'revision': revision})
    loader = SkillToolLoader(case.a.app)
    text = await loader.invoke_tool('read_skill_resource', {'skill_name': _NAME, 'path': 'references/guide.md'}, query)
    assert text['content'] == _GUIDE and text['artifact']['source'] == 'skill_resource'
    for path, mode, field, expected in (
        ('asset.png', 'auto', 'image_base64', _PNG),
        ('asset.pdf', 'native', 'file_base64', pdf),
    ):
        contents = await loader.invoke_tool(
            'read_skill_resource', {'skill_name': _NAME, 'path': path, 'mode': mode}, query
        )
        assert base64.b64decode(contents[1][field].split(',', 1)[1]) == expected
    await _end_run(case, context)
    with pytest.raises(ArtifactError):
        await loader.invoke_tool('read_skill_resource', {'skill_name': _NAME, 'path': 'asset.png'}, query)

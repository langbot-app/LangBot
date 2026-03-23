"""Tests for SkillManager, SkillToolLoader (skill_exec), and BoxService skill sandbox."""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot_plugin.box.models import BoxExecutionResult, BoxExecutionStatus


def _make_ap(logger=None):
    """Create a minimal Application mock."""
    ap = SimpleNamespace()
    ap.logger = logger or Mock()
    ap.persistence_mgr = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda cls, row: row)
    return ap


def _make_skill_data(
    name='test-skill',
    instructions='Do something',
    package_root=None,
    entry_file='SKILL.md',
    sandbox_timeout_sec=120,
    sandbox_network=False,
    requires_skills=None,
    **kwargs,
):
    return {
        'uuid': f'uuid-{name}',
        'name': name,
        'description': f'Description of {name}',
        'instructions': instructions,
        'type': 'skill',
        'package_root': package_root or '',
        'entry_file': entry_file,
        'sandbox_timeout_sec': sandbox_timeout_sec,
        'sandbox_network': sandbox_network,
        'requires_tools': [],
        'requires_kbs': [],
        'requires_skills': requires_skills or [],
        'auto_activate': True,
        'trigger_keywords': [],
        'is_enabled': True,
        'is_builtin': False,
        **kwargs,
    }


class TestSkillManagerPackageLoading:
    """Test SkillManager._load_skill_file()."""

    def test_load_skill_file_success(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = os.path.join(tmpdir, 'SKILL.md')
            with open(skill_md, 'w') as f:
                f.write('---\ndescription: Test skill\n---\n\n# Test Skill\nDo things.')

            skill_data = _make_skill_data(
                package_root=tmpdir,
            )
            result = mgr._load_skill_file(skill_data)

            assert result is True
            assert skill_data['instructions'] == '# Test Skill\nDo things.'
            assert skill_data['description'] == 'Test skill'

    def test_load_skill_file_missing_file(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_data = _make_skill_data(
                package_root=tmpdir,
            )
            result = mgr._load_skill_file(skill_data)

            assert result is False
            ap.logger.warning.assert_called_once()

    def test_load_skill_file_no_package_root(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        skill_data = _make_skill_data(package_root='')
        result = mgr._load_skill_file(skill_data)

        assert result is False

    def test_load_skill_file_custom_entry_file(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            entry = os.path.join(tmpdir, 'README.md')
            with open(entry, 'w') as f:
                f.write('Custom entry')

            skill_data = _make_skill_data(
                package_root=tmpdir,
                entry_file='README.md',
            )
            result = mgr._load_skill_file(skill_data)

            assert result is True

    def test_refresh_skill_from_disk_updates_cached_dict_in_place(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = os.path.join(tmpdir, 'SKILL.md')
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write('---\ndescription: First\n---\n\nOriginal instructions')

            skill_data = _make_skill_data(name='test-skill', package_root=tmpdir)
            assert mgr._load_skill_file(skill_data) is True

            mgr.skills['test-skill'] = skill_data
            mgr.skills_by_uuid[skill_data['uuid']] = skill_data

            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write('---\ndescription: Second\n---\n\nUpdated instructions')

            assert mgr.refresh_skill_from_disk('test-skill') is True
            assert mgr.skills['test-skill'] is skill_data
            assert skill_data['instructions'] == 'Updated instructions'
            assert skill_data['description'] == 'Second'


class TestSkillExecLoader:
    """Test SkillToolLoader with skill_exec generic tool."""

    def test_has_tool_with_activated_skill(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
            register_activated_skill,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        register_activated_skill(query, skill_data)

        assert loader.has_tool(SKILL_EXEC_TOOL_NAME, query) is True

    def test_has_tool_without_activated_skill(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        assert loader.has_tool(SKILL_EXEC_TOOL_NAME, query) is False

    def test_has_tool_wrong_name(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SkillToolLoader,
            register_activated_skill,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        register_activated_skill(query, skill_data)

        assert loader.has_tool('wrong_name', query) is False

    def test_query_isolation(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
            register_activated_skill,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query1 = SimpleNamespace(variables={})
        query2 = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        register_activated_skill(query1, skill_data)

        assert loader.has_tool(SKILL_EXEC_TOOL_NAME, query1) is True
        assert loader.has_tool(SKILL_EXEC_TOOL_NAME, query2) is False

    def test_no_variables_returns_false(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables=None)
        assert loader.has_tool(SKILL_EXEC_TOOL_NAME, query) is False

    @pytest.mark.asyncio
    async def test_invoke_tool_skill_not_activated(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        with pytest.raises(ValueError, match='not activated'):
            await loader.invoke_tool(
                SKILL_EXEC_TOOL_NAME,
                {'skill_name': 'nonexistent', 'command': 'echo hi'},
                query,
            )

    @pytest.mark.asyncio
    async def test_invoke_tool_calls_box_service(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            SKILL_EXEC_TOOL_NAME,
            SkillToolLoader,
            register_activated_skill,
        )

        ap = _make_ap()
        ap.box_service = Mock()
        ap.box_service.execute_in_skill_sandbox = AsyncMock(return_value={'ok': True})
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='my-skill')
        register_activated_skill(query, skill_data)

        result = await loader.invoke_tool(
            SKILL_EXEC_TOOL_NAME,
            {'skill_name': 'my-skill', 'command': 'python scripts/check.py'},
            query,
        )

        assert result == {'ok': True}
        ap.box_service.execute_in_skill_sandbox.assert_called_once_with(
            skill_data=skill_data,
            command='python scripts/check.py',
            query=query,
        )

    def test_register_multiple_skills(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILLS_KEY,
            register_activated_skill,
        )

        query = SimpleNamespace(variables={})
        skill1 = _make_skill_data(name='skill-a')
        skill2 = _make_skill_data(name='skill-b')

        register_activated_skill(query, skill1)
        register_activated_skill(query, skill2)

        activated = query.variables[ACTIVATED_SKILLS_KEY]
        assert 'skill-a' in activated
        assert 'skill-b' in activated

    def test_register_same_skill_twice_no_overwrite(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILLS_KEY,
            register_activated_skill,
        )

        query = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        register_activated_skill(query, skill_data)
        register_activated_skill(query, skill_data)

        activated = query.variables[ACTIVATED_SKILLS_KEY]
        assert len(activated) == 1


class TestBoxServiceSkillExec:
    """Test BoxService skill sandbox execution helpers."""

    @pytest.mark.asyncio
    async def test_execute_in_skill_sandbox_mounts_skill_rw_and_refreshes_cache(self):
        from langbot.pkg.box.service import BoxService
        from langbot_plugin.box.models import BoxHostMountMode

        client = Mock()
        client.execute = AsyncMock(
            return_value=BoxExecutionResult(
                session_id='skill-1',
                backend_name='fake',
                status=BoxExecutionStatus.COMPLETED,
                exit_code=0,
                stdout='ok',
                stderr='',
                duration_ms=5,
            )
        )

        ap = _make_ap()
        ap.skill_mgr = Mock()

        with tempfile.TemporaryDirectory() as tmpdir:
            ap.instance_config = SimpleNamespace(
                data={'box': {'profile': 'default', 'allowed_host_mount_roots': [tmpdir], 'default_host_workspace': ''}}
            )

            service = BoxService(ap, client=client)
            service._available = True

            skill_data = _make_skill_data(name='writer', package_root=tmpdir)
            query = SimpleNamespace(query_id=7)

            result = await service.execute_in_skill_sandbox(skill_data, 'python scripts/run.py', query)

        assert result['ok'] is True
        spec = client.execute.await_args.args[0]
        assert spec.host_path_mode == BoxHostMountMode.READ_WRITE
        ap.skill_mgr.refresh_skill_from_disk.assert_called_once_with('writer')

    def test_build_skill_session_id_with_launcher(self):
        from langbot.pkg.box.service import BoxService

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        query = SimpleNamespace(query_id=42, launcher_type='person', launcher_id='123')
        skill_data = {'uuid': 'skill-uuid-1'}

        sid = service._build_skill_session_id(skill_data, query)
        assert sid == 'skill-person_123-skill-uuid-1'

    def test_build_skill_session_id_fallback(self):
        from langbot.pkg.box.service import BoxService

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        query = SimpleNamespace(query_id=99)
        skill_data = {'uuid': 'skill-uuid-2'}

        sid = service._build_skill_session_id(skill_data, query)
        assert sid == 'skill-99-skill-uuid-2'

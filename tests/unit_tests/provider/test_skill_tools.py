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


class TestSkillManagerActivation:
    """Test multi-skill activation parsing and prompt building."""

    def test_detect_skill_activations_returns_unique_ordered_skills(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {
            'alpha': _make_skill_data(name='alpha'),
            'beta': _make_skill_data(name='beta'),
        }

        response = (
            '[ACTIVATE_SKILL: alpha]\n'
            '[ACTIVATE_SKILL: beta]\n'
            '[ACTIVATE_SKILL: alpha]\n'
            'Let me handle this.'
        )

        assert mgr.detect_skill_activations(response) == ['alpha', 'beta']
        assert mgr.detect_skill_activation(response) == 'alpha'

    def test_detect_skill_activations_ignores_unknown_skills(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {
            'alpha': _make_skill_data(name='alpha'),
        }

        response = '[ACTIVATE_SKILL: missing]\n[ACTIVATE_SKILL: alpha]'
        assert mgr.detect_skill_activations(response) == ['alpha']

    def test_build_activation_prompt_for_skills_includes_roles(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {
            'primary': _make_skill_data(name='primary', instructions='Primary instructions'),
            'aux': _make_skill_data(name='aux', instructions='Aux instructions'),
        }

        prompt = mgr.build_activation_prompt_for_skills(['primary', 'aux'])

        assert 'Activated skills: primary, aux' in prompt
        assert 'role="primary"' in prompt
        assert 'role="auxiliary"' in prompt
        assert 'primary skill > auxiliary skills' in prompt

    def test_remove_activation_marker_removes_multiple_markers(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        response = '[ACTIVATE_SKILL: alpha]\n[ACTIVATE_SKILL: beta]\nFinal answer'
        assert mgr.remove_activation_marker(response) == 'Final answer'


class TestSkillActivationHelper:
    """Test activation preparation helper."""

    def test_prepare_skill_activation_registers_only_explicit_activated_skills(self):
        from langbot.pkg.skill.activation import prepare_skill_activation
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY, SKILL_EXEC_TOOL_NAME
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {
            'primary': _make_skill_data(name='primary', instructions='Primary instructions'),
            'aux': _make_skill_data(name='aux', instructions='Aux instructions'),
        }
        ap.skill_mgr = mgr

        query = SimpleNamespace(variables={}, use_funcs=[])
        activation = prepare_skill_activation(
            ap,
            query,
            '[ACTIVATE_SKILL: primary]\n[ACTIVATE_SKILL: aux]\nWorking on it.',
        )

        assert activation is not None
        assert activation.activated_skill_names == ['primary', 'aux']
        assert activation.cleaned_content == 'Working on it.'
        assert set(query.variables[ACTIVATED_SKILLS_KEY].keys()) == {'primary', 'aux'}
        assert any(getattr(tool, 'name', None) == SKILL_EXEC_TOOL_NAME for tool in query.use_funcs)


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

    @pytest.mark.asyncio
    async def test_skill_get_returns_visible_skill_details(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            PIPELINE_BOUND_SKILLS_KEY,
            SKILL_GET_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={
                'visible': _make_skill_data(
                    name='visible',
                    instructions='Visible instructions',
                ),
                'hidden': _make_skill_data(name='hidden', instructions='Hidden instructions'),
            }
        )
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={PIPELINE_BOUND_SKILLS_KEY: ['uuid-visible']})

        result = await loader.invoke_tool(
            SKILL_GET_TOOL_NAME,
            {'skill_name': 'visible'},
            query,
        )

        assert result['name'] == 'visible'
        assert result['instructions'] == 'Visible instructions'

    @pytest.mark.asyncio
    async def test_skill_get_rejects_invisible_skill(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            PIPELINE_BOUND_SKILLS_KEY,
            SKILL_GET_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={
                'visible': _make_skill_data(name='visible'),
                'hidden': _make_skill_data(name='hidden'),
            }
        )
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={PIPELINE_BOUND_SKILLS_KEY: ['uuid-visible']})

        with pytest.raises(ValueError, match='not visible'):
            await loader.invoke_tool(
                SKILL_GET_TOOL_NAME,
                {'skill_name': 'hidden'},
                query,
            )


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

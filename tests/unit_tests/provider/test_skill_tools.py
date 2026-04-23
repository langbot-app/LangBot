from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


def _make_ap(logger=None):
    ap = SimpleNamespace()
    ap.logger = logger or Mock()
    ap.persistence_mgr = Mock()
    ap.persistence_mgr.execute_async = AsyncMock(return_value=Mock(all=Mock(return_value=[])))
    ap.persistence_mgr.serialize_model = Mock(side_effect=lambda cls, row: row)
    return ap


def _make_skill_data(
    name='test-skill',
    instructions='Do something',
    package_root='',
    entry_file='SKILL.md',
    **kwargs,
):
    return {
        'name': name,
        'display_name': kwargs.pop('display_name', name),
        'description': kwargs.pop('description', f'Description of {name}'),
        'instructions': instructions,
        'package_root': package_root,
        'entry_file': entry_file,
        **kwargs,
    }


class TestSkillManagerPackageLoading:
    def test_load_skill_file_success(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = os.path.join(tmpdir, 'SKILL.md')
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write('---\ndescription: Test skill\n---\n\n# Test Skill\nDo things.')

            skill_data = _make_skill_data(package_root=tmpdir)
            result = mgr._load_skill_file(skill_data)

            assert result is True
            assert skill_data['instructions'] == '# Test Skill\nDo things.'
            assert skill_data['description'] == 'Test skill'

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

            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write('---\ndescription: Second\n---\n\nUpdated instructions')

            assert mgr.refresh_skill_from_disk('test-skill') is True
            assert mgr.skills['test-skill'] is skill_data
            assert skill_data['instructions'] == 'Updated instructions'
            assert skill_data['description'] == 'Second'


class TestSkillManagerActivation:
    def test_detect_skill_activations_returns_unique_ordered_skills(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {
            'alpha': _make_skill_data(name='alpha'),
            'beta': _make_skill_data(name='beta'),
        }

        response = '[ACTIVATE_SKILL: alpha]\n[ACTIVATE_SKILL: beta]\n[ACTIVATE_SKILL: alpha]\nLet me handle this.'

        assert mgr.detect_skill_activations(response) == ['alpha', 'beta']
        assert mgr.detect_skill_activation(response) == 'alpha'

    def test_build_activation_prompt_for_skills_includes_runtime_guidance(self):
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
        assert '/workspace/.skills/<skill-name>' in prompt

    def test_remove_activation_marker_removes_multiple_markers(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        response = '[ACTIVATE_SKILL: alpha]\n[ACTIVATE_SKILL: beta]\nFinal answer'
        assert mgr.remove_activation_marker(response) == 'Final answer'


class TestSkillActivationHelper:
    def test_prepare_skill_activation_registers_only_explicit_activated_skills(self):
        from langbot.pkg.skill.activation import prepare_skill_activation
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY
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


class TestSkillPathHelpers:
    def test_get_visible_skills_filters_by_bound_names(self):
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY, get_visible_skills

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={
                'visible': _make_skill_data(name='visible'),
                'hidden': _make_skill_data(name='hidden'),
            }
        )
        query = SimpleNamespace(variables={PIPELINE_BOUND_SKILLS_KEY: ['visible']})

        result = get_visible_skills(ap, query)

        assert list(result.keys()) == ['visible']

    def test_resolve_virtual_skill_path_allows_visible_skill_reads(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            PIPELINE_BOUND_SKILLS_KEY,
            resolve_virtual_skill_path,
        )

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo')})
        query = SimpleNamespace(variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']})

        skill, rewritten = resolve_virtual_skill_path(
            ap,
            query,
            '/workspace/.skills/demo/SKILL.md',
            include_visible=True,
            include_activated=False,
        )

        assert skill['name'] == 'demo'
        assert rewritten == '/workspace/SKILL.md'

    def test_build_skill_session_id_uses_name_based_identifier(self):
        from langbot.pkg.provider.tools.loaders.skill import build_skill_session_id

        with_launcher = build_skill_session_id(
            {'name': 'writer'},
            SimpleNamespace(query_id=42, launcher_type='person', launcher_id='123'),
        )
        fallback = build_skill_session_id({'name': 'writer'}, SimpleNamespace(query_id=99))

        assert with_launcher == 'skill-person_123-writer'
        assert fallback == 'skill-99-writer'

    def test_should_prepare_skill_python_env_detects_manifests_and_venv(self):
        from langbot.pkg.provider.tools.loaders.skill import should_prepare_skill_python_env

        with tempfile.TemporaryDirectory() as tmpdir:
            assert should_prepare_skill_python_env(tmpdir) is False

            with open(os.path.join(tmpdir, 'requirements.txt'), 'w', encoding='utf-8') as f:
                f.write('requests==2.32.0\n')
            assert should_prepare_skill_python_env(tmpdir) is True

        with tempfile.TemporaryDirectory() as tmpdir:
            os.makedirs(os.path.join(tmpdir, '.venv'))
            assert should_prepare_skill_python_env(tmpdir) is True

    def test_wrap_skill_command_with_python_env_bootstraps_then_runs_command(self):
        from langbot.pkg.provider.tools.loaders.skill import wrap_skill_command_with_python_env

        command = wrap_skill_command_with_python_env('python scripts/run.py')

        assert 'python -m venv "$_LB_VENV_DIR"' in command
        assert 'export VIRTUAL_ENV="$_LB_VENV_DIR"' in command
        assert command.rstrip().endswith('python scripts/run.py')


class TestSkillAuthoringToolLoader:
    @pytest.mark.asyncio
    async def test_create_skill_creates_managed_prompt_only_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            CREATE_SKILL_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            create_skill=AsyncMock(
                return_value=_make_skill_data(name='prompt-skill', package_root='/data/skills/prompt-skill')
            ),
            reload_skills=AsyncMock(),
            list_skills=AsyncMock(return_value=[]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            CREATE_SKILL_TOOL_NAME,
            {
                'name': 'prompt-skill',
                'display_name': 'Prompt Skill',
                'description': 'Prompt only skill',
                'instructions': 'Follow these steps carefully.',
            },
            SimpleNamespace(),
        )

        ap.skill_service.create_skill.assert_awaited_once_with(
            {
                'name': 'prompt-skill',
                'display_name': 'Prompt Skill',
                'description': 'Prompt only skill',
                'instructions': 'Follow these steps carefully.',
            }
        )
        assert result == {
            'created': True,
            'skill': _make_skill_data(name='prompt-skill', package_root='/data/skills/prompt-skill'),
        }

    @pytest.mark.asyncio
    async def test_list_skills_returns_managed_skills(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            LIST_SKILLS_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            list_skills=AsyncMock(return_value=[_make_skill_data(name='alpha'), _make_skill_data(name='beta')]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(LIST_SKILLS_TOOL_NAME, {}, SimpleNamespace())

        assert result == {
            'skills': [_make_skill_data(name='alpha'), _make_skill_data(name='beta')],
            'skill_names': ['alpha', 'beta'],
            'count': 2,
        }

    @pytest.mark.asyncio
    async def test_get_skill_returns_one_managed_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            GET_SKILL_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            get_skill=AsyncMock(return_value=_make_skill_data(name='time-now', package_root='/data/skills/time-now')),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(GET_SKILL_TOOL_NAME, {'name': 'time-now'}, SimpleNamespace())

        ap.skill_service.get_skill.assert_awaited_once_with('time-now')
        assert result == {
            'skill': _make_skill_data(name='time-now', package_root='/data/skills/time-now'),
        }

    @pytest.mark.asyncio
    async def test_update_skill_updates_managed_prompt_only_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            UPDATE_SKILL_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            create_skill=AsyncMock(),
            update_skill=AsyncMock(
                return_value=_make_skill_data(name='time-now', package_root='/data/skills/time-now')
            ),
            reload_skills=AsyncMock(),
            list_skills=AsyncMock(return_value=[]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            UPDATE_SKILL_TOOL_NAME,
            {
                'name': 'time-now',
                'description': 'Fixed to Beijing time',
                'instructions': 'Always use Asia/Shanghai and never offer other timezones.',
            },
            SimpleNamespace(),
        )

        ap.skill_service.update_skill.assert_awaited_once_with(
            'time-now',
            {
                'name': 'time-now',
                'description': 'Fixed to Beijing time',
                'instructions': 'Always use Asia/Shanghai and never offer other timezones.',
            },
        )
        assert result == {
            'updated': True,
            'skill': _make_skill_data(name='time-now', package_root='/data/skills/time-now'),
        }

    @pytest.mark.asyncio
    async def test_delete_skill_deletes_managed_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            DELETE_SKILL_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            delete_skill=AsyncMock(return_value=True),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(DELETE_SKILL_TOOL_NAME, {'name': 'time-now'}, SimpleNamespace())

        ap.skill_service.delete_skill.assert_awaited_once_with('time-now')
        assert result == {
            'deleted': True,
            'skill_name': 'time-now',
        }

    @pytest.mark.asyncio
    async def test_import_skill_from_directory_uses_workspace_path_and_service_import(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.box_service = SimpleNamespace(default_host_workspace='/tmp/langbot-workspace')
        ap.skill_service = SimpleNamespace(
            scan_directory=Mock(
                return_value={
                    'name': 'cloned-skill',
                    'display_name': 'Cloned Skill',
                    'description': 'Imported from clone',
                    'instructions': 'Do work',
                }
            ),
            create_skill=AsyncMock(return_value=_make_skill_data(name='cloned-skill', package_root='/repo/root')),
            reload_skills=AsyncMock(),
            list_skills=AsyncMock(return_value=[]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        with tempfile.TemporaryDirectory() as tmpdir:
            ap.box_service.default_host_workspace = tmpdir
            repo_dir = os.path.join(tmpdir, 'repos', 'cloned-skill')
            os.makedirs(repo_dir)

            result = await loader.invoke_tool(
                IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
                {'path': '/workspace/repos/cloned-skill'},
                SimpleNamespace(),
            )

        ap.skill_service.scan_directory.assert_called_once_with(os.path.realpath(repo_dir))
        ap.skill_service.create_skill.assert_awaited_once_with(
            {
                'name': 'cloned-skill',
                'display_name': 'Cloned Skill',
                'description': 'Imported from clone',
                'instructions': 'Do work',
                'package_root': os.path.realpath(repo_dir),
            }
        )
        assert result['imported'] is True
        assert result['source_path'] == '/workspace/repos/cloned-skill'

    @pytest.mark.asyncio
    async def test_import_skill_from_directory_rejects_workspace_escape(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.box_service = SimpleNamespace(default_host_workspace='/tmp/langbot-workspace')
        ap.skill_service = SimpleNamespace(
            scan_directory=Mock(),
            create_skill=AsyncMock(),
            reload_skills=AsyncMock(),
            list_skills=AsyncMock(return_value=[]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        with pytest.raises(ValueError, match='escapes the workspace boundary'):
            await loader.invoke_tool(
                IMPORT_SKILL_FROM_DIRECTORY_TOOL_NAME,
                {'path': '/workspace/../../etc'},
                SimpleNamespace(),
            )

    @pytest.mark.asyncio
    async def test_reload_skills_rescans_filesystem_and_returns_current_names(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            RELOAD_SKILLS_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            reload_skills=AsyncMock(),
            list_skills=AsyncMock(return_value=[_make_skill_data(name='alpha'), _make_skill_data(name='beta')]),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(RELOAD_SKILLS_TOOL_NAME, {}, SimpleNamespace())

        assert result == {
            'reloaded': True,
            'skill_names': ['alpha', 'beta'],
            'count': 2,
        }
        ap.skill_service.reload_skills.assert_awaited_once_with()


class TestNativeToolLoaderSkillPaths:
    @pytest.mark.asyncio
    async def test_read_visible_skill_file(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = os.path.join(tmpdir, 'SKILL.md')
            with open(skill_md, 'w', encoding='utf-8') as f:
                f.write('demo instructions')

            ap = _make_ap()
            ap.box_service = SimpleNamespace(available=True, default_host_workspace=tmpdir)
            ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            result = await loader.invoke_tool(
                'read',
                {'path': '/workspace/.skills/demo/SKILL.md'},
                SimpleNamespace(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']}),
            )

            assert result == {'ok': True, 'content': 'demo instructions'}

    @pytest.mark.asyncio
    async def test_exec_in_activated_skill_mount_rewrites_command_and_refreshes(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                available=True,
                default_host_workspace=tmpdir,
                execute_tool=AsyncMock(return_value={'ok': True}),
            )
            ap.skill_mgr = SimpleNamespace(refresh_skill_from_disk=Mock())
            loader = NativeToolLoader(ap)

            query = SimpleNamespace(
                query_id='q1',
                launcher_type='person',
                launcher_id='123',
                variables={},
                pipeline_config=None,
            )
            register_activated_skill(query, _make_skill_data(name='demo', package_root=tmpdir))

            result = await loader.invoke_tool(
                'exec',
                {
                    'command': 'python /workspace/.skills/demo/scripts/run.py',
                    'workdir': '/workspace/.skills/demo',
                },
                query,
            )

            assert result == {'ok': True}
            call_params = ap.box_service.execute_tool.await_args.args[0]
            # The command is passed through to execute_tool (no rewriting in the unified model)
            assert 'python' in call_params['command']
            assert '/workspace/.skills/demo' in call_params['command']
            ap.skill_mgr.refresh_skill_from_disk.assert_called_once_with('demo')

    @pytest.mark.asyncio
    async def test_write_requires_skill_activation(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(available=True, default_host_workspace=tmpdir)
            ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            query = SimpleNamespace(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']})

            with pytest.raises(ValueError, match='Skill "demo" is not available at this path'):
                await loader.invoke_tool(
                    'write',
                    {'path': '/workspace/.skills/demo/notes.txt', 'content': 'hi'},
                    query,
                )

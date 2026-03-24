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
    auto_activate=True,
    **kwargs,
):
    return {
        'name': name,
        'display_name': kwargs.pop('display_name', name),
        'description': kwargs.pop('description', f'Description of {name}'),
        'instructions': instructions,
        'package_root': package_root,
        'entry_file': entry_file,
        'auto_activate': auto_activate,
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

        response = (
            '[ACTIVATE_SKILL: alpha]\n'
            '[ACTIVATE_SKILL: beta]\n'
            '[ACTIVATE_SKILL: alpha]\n'
            'Let me handle this.'
        )

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
    async def test_list_skills_returns_current_summary_shape(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            LIST_SKILLS_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            list_skills=AsyncMock(
                return_value=[
                    _make_skill_data(name='alpha', instructions='Alpha instructions', updated_at='2026-03-23T00:00:00Z')
                ]
            )
        )
        ap.pipeline_service = SimpleNamespace()

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(LIST_SKILLS_TOOL_NAME, {}, SimpleNamespace(pipeline_uuid='pipe-1'))

        assert result['skills'] == [
            {
                'name': 'alpha',
                'display_name': 'alpha',
                'description': 'Description of alpha',
                'auto_activate': True,
                'updated_at': '2026-03-23T00:00:00Z',
            }
        ]

    @pytest.mark.asyncio
    async def test_create_skill_calls_service_and_returns_detail(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            CREATE_SKILL_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        created_skill = _make_skill_data(
            name='writer',
            description='Writes release notes',
            instructions='Do the release notes work.',
            display_name='Release Writer',
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(create_skill=AsyncMock(return_value=created_skill))
        ap.pipeline_service = SimpleNamespace()

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            CREATE_SKILL_TOOL_NAME,
            {
                'name': 'writer',
                'display_name': 'Release Writer',
                'description': 'Writes release notes',
                'instructions': 'Do the release notes work.',
                'package_root': '/tmp/imported-skill',
                'auto_activate': False,
            },
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )

        assert result['skill']['name'] == 'writer'
        payload = ap.skill_service.create_skill.await_args.args[0]
        assert payload == {
            'name': 'writer',
            'display_name': 'Release Writer',
            'description': 'Writes release notes',
            'instructions': 'Do the release notes work.',
            'package_root': '/tmp/imported-skill',
            'auto_activate': False,
        }

    @pytest.mark.asyncio
    async def test_update_skill_uses_name_based_lookup(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            SkillAuthoringToolLoader,
            UPDATE_SKILL_TOOL_NAME,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            get_skill=AsyncMock(return_value=_make_skill_data(name='writer', instructions='Old instructions')),
            update_skill=AsyncMock(return_value=_make_skill_data(name='writer', instructions='New instructions')),
        )
        ap.pipeline_service = SimpleNamespace()

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            UPDATE_SKILL_TOOL_NAME,
            {
                'skill_name': 'writer',
                'updates': {'instructions': 'New instructions'},
            },
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )

        assert result['skill']['instructions'] == 'New instructions'
        ap.skill_service.update_skill.assert_awaited_once_with('writer', {'instructions': 'New instructions'})

    @pytest.mark.asyncio
    async def test_get_pipeline_skills_defaults_to_current_query_pipeline(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            GET_PIPELINE_SKILLS_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            list_skills=AsyncMock(
                return_value=[
                    _make_skill_data(name='alpha'),
                    _make_skill_data(name='beta'),
                ]
            )
        )
        ap.pipeline_service = SimpleNamespace(
            get_pipeline=AsyncMock(
                return_value={
                    'uuid': 'pipe-1',
                    'extensions_preferences': {
                        'enable_all_skills': False,
                        'skills': ['alpha'],
                    },
                }
            )
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            GET_PIPELINE_SKILLS_TOOL_NAME,
            {},
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )

        assert result['pipeline_uuid'] == 'pipe-1'
        assert result['enable_all_skills'] is False
        assert result['bound_skill_names'] == ['alpha']

    @pytest.mark.asyncio
    async def test_update_pipeline_skills_preserves_other_extension_settings(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            SkillAuthoringToolLoader,
            UPDATE_PIPELINE_SKILLS_TOOL_NAME,
        )

        original_pipeline = {
            'uuid': 'pipe-1',
            'extensions_preferences': {
                'enable_all_plugins': False,
                'enable_all_mcp_servers': False,
                'enable_all_skills': False,
                'plugins': [{'name': 'plugin-a'}],
                'mcp_servers': ['mcp-a'],
                'skills': ['old-skill'],
            },
        }
        updated_pipeline = {
            'uuid': 'pipe-1',
            'extensions_preferences': {
                'enable_all_plugins': False,
                'enable_all_mcp_servers': False,
                'enable_all_skills': False,
                'plugins': [{'name': 'plugin-a'}],
                'mcp_servers': ['mcp-a'],
                'skills': ['new-skill'],
            },
        }

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            get_skill=AsyncMock(return_value={'name': 'new-skill'}),
            list_skills=AsyncMock(return_value=[_make_skill_data(name='new-skill')]),
        )
        ap.pipeline_service = SimpleNamespace(
            get_pipeline=AsyncMock(side_effect=[original_pipeline, updated_pipeline]),
            update_pipeline_extensions=AsyncMock(),
        )

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        result = await loader.invoke_tool(
            UPDATE_PIPELINE_SKILLS_TOOL_NAME,
            {
                'bound_skill_names': ['new-skill'],
                'enable_all_skills': False,
            },
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )

        ap.pipeline_service.update_pipeline_extensions.assert_awaited_once_with(
            pipeline_uuid='pipe-1',
            bound_plugins=[{'name': 'plugin-a'}],
            bound_mcp_servers=['mcp-a'],
            enable_all_plugins=False,
            enable_all_mcp_servers=False,
            bound_skills=['new-skill'],
            enable_all_skills=False,
        )
        assert result['bound_skill_names'] == ['new-skill']

    @pytest.mark.asyncio
    async def test_skill_file_tools_route_to_skill_service(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            SKILL_LIST_FILES_TOOL_NAME,
            SKILL_READ_FILE_TOOL_NAME,
            SKILL_WRITE_FILE_TOOL_NAME,
            SkillAuthoringToolLoader,
        )

        ap = _make_ap()
        ap.skill_service = SimpleNamespace(
            get_skill=AsyncMock(return_value=_make_skill_data(name='mood-logger')),
            list_skill_files=AsyncMock(return_value={'entries': [{'path': 'resources'}]}),
            read_skill_file=AsyncMock(return_value={'path': 'resources/affinity.py', 'content': 'print("ok")\n'}),
            write_skill_file=AsyncMock(return_value={'path': 'resources/affinity.py', 'bytes_written': 12}),
        )
        ap.pipeline_service = SimpleNamespace()
        ap.skill_mgr = SimpleNamespace(get_skill_runtime_data=Mock(return_value={'instructions': 'x'}))

        loader = SkillAuthoringToolLoader(ap)
        await loader.initialize()

        listed = await loader.invoke_tool(
            SKILL_LIST_FILES_TOOL_NAME,
            {'skill_name': 'mood-logger', 'path': 'resources'},
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )
        read_back = await loader.invoke_tool(
            SKILL_READ_FILE_TOOL_NAME,
            {'skill_name': 'mood-logger', 'path': 'resources/affinity.py'},
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )
        written = await loader.invoke_tool(
            SKILL_WRITE_FILE_TOOL_NAME,
            {
                'skill_name': 'mood-logger',
                'path': 'resources/affinity.py',
                'content': 'print("ok")\n',
            },
            SimpleNamespace(pipeline_uuid='pipe-1'),
        )

        assert listed['entries'] == [{'path': 'resources'}]
        assert read_back['path'] == 'resources/affinity.py'
        assert written['bytes_written'] == 12
        ap.skill_service.list_skill_files.assert_awaited_once_with(
            'mood-logger',
            path='resources',
            include_hidden=False,
            max_entries=200,
        )
        ap.skill_service.read_skill_file.assert_awaited_once_with('mood-logger', 'resources/affinity.py')
        ap.skill_service.write_skill_file.assert_awaited_once_with(
            'mood-logger',
            'resources/affinity.py',
            'print("ok")\n',
        )


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
                execute_spec_payload=AsyncMock(return_value={'ok': True}),
            )
            ap.skill_mgr = SimpleNamespace(refresh_skill_from_disk=Mock())
            loader = NativeToolLoader(ap)

            query = SimpleNamespace(query_id='q1', launcher_type='person', launcher_id='123', variables={})
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
            spec_payload = ap.box_service.execute_spec_payload.await_args.args[0]
            assert spec_payload['cmd'] == 'python /workspace/scripts/run.py'
            assert spec_payload['workdir'] == '/workspace'
            assert spec_payload['host_path'] == tmpdir
            assert spec_payload['session_id'] == 'skill-person_123-demo'
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

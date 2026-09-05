from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest

from langbot.pkg.api.http.context import ExecutionContext


_CONTEXT = ExecutionContext(
    instance_uuid='instance-a',
    workspace_uuid='workspace-a',
    placement_generation=1,
    query_uuid='query-a',
)


def _make_query(*, variables=None, **kwargs):
    return SimpleNamespace(
        query_id=kwargs.pop('query_id', 'query-a'),
        query_uuid=kwargs.pop('query_uuid', 'query-a'),
        instance_uuid=kwargs.pop('instance_uuid', _CONTEXT.instance_uuid),
        workspace_uuid=kwargs.pop('workspace_uuid', _CONTEXT.workspace_uuid),
        placement_generation=kwargs.pop('placement_generation', _CONTEXT.placement_generation),
        variables={} if variables is None else variables,
        **kwargs,
    )


def _make_skill_manager(skills: dict[str, dict], **kwargs):
    return SimpleNamespace(
        skills=skills,
        get_skills=Mock(return_value=skills),
        get_skill_by_name=Mock(side_effect=lambda _context, name: skills.get(name)),
        **kwargs,
    )


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


class TestSkillManagerCache:
    """SkillManager caches the Core-owned SkillRepository catalog."""

    def test_refresh_skill_from_disk_reports_cache_presence(self):
        """Disk mutations are reflected by an explicit repository reload."""
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        # Empty cache → returns False
        assert mgr.refresh_skill_from_disk(_CONTEXT, 'test-skill') is False

        # Cache populated → returns True; method does NOT mutate the cache
        cached = _make_skill_data(name='test-skill', instructions='Cached')
        mgr._skills_by_scope[mgr._scope_key(_CONTEXT)] = {'test-skill': cached}
        assert mgr.refresh_skill_from_disk(_CONTEXT, 'test-skill') is True
        assert mgr.get_skills(_CONTEXT)['test-skill'] is cached
        assert mgr.refresh_skill_from_disk(_CONTEXT, '') is False

    @pytest.mark.asyncio
    async def test_reload_skills_uses_repository_when_box_is_disabled(self):
        from langbot.pkg.skill.manager import SkillManager

        repository = SimpleNamespace(
            list_skills=AsyncMock(
                return_value=[
                    _make_skill_data(name='alpha', package_root='/skills/alpha'),
                    _make_skill_data(name='beta', package_root='/skills/beta'),
                ]
            ),
        )
        ap = _make_ap()
        ap.box_service = SimpleNamespace(available=False, enabled=False)
        ap.skill_repository = repository
        mgr = SkillManager(ap)

        await mgr.reload_skills(_CONTEXT)

        assert sorted(mgr.get_skills(_CONTEXT)) == ['alpha', 'beta']
        repository.list_skills.assert_awaited_once_with(_CONTEXT)


class TestSkillActivationHelper:
    """Skill activation is now Tool-Call based.

    The legacy text-marker mechanism (``[ACTIVATE_SKILL: x]`` detection,
    ``build_activation_prompt_for_skills``, ``remove_activation_marker``,
    ``prepare_skill_activation``) has been removed. Activation now goes
    through ``skill.activation.register_activated_skill``, invoked by the
    ``activate`` Tool Call.
    """

    def test_register_activated_skill_records_known_skill(self):
        from langbot.pkg.skill.activation import register_activated_skill
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr._skills_by_scope[mgr._scope_key(_CONTEXT)] = {
            'primary': _make_skill_data(name='primary', instructions='Primary instructions'),
        }
        ap.skill_mgr = mgr

        query = _make_query()

        assert register_activated_skill(ap, query, 'primary') is True
        assert set(query.variables[ACTIVATED_SKILLS_KEY].keys()) == {'primary'}
        assert query.variables[ACTIVATED_SKILLS_KEY]['primary']['name'] == 'primary'

    def test_register_activated_skill_rejects_unknown_skill(self):
        from langbot.pkg.skill.activation import register_activated_skill
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr._skills_by_scope[mgr._scope_key(_CONTEXT)] = {'primary': _make_skill_data(name='primary')}
        ap.skill_mgr = mgr

        query = _make_query()

        assert register_activated_skill(ap, query, 'missing') is False
        assert ACTIVATED_SKILLS_KEY not in query.variables

    def test_register_activated_skill_without_skill_manager_returns_false(self):
        from langbot.pkg.skill.activation import register_activated_skill

        ap = _make_ap()  # no skill_mgr attribute
        query = _make_query()

        assert register_activated_skill(ap, query, 'primary') is False


class TestSkillPathHelpers:
    def test_get_visible_skills_filters_by_bound_names(self):
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY, get_visible_skills

        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager(
            {
                'visible': _make_skill_data(name='visible'),
                'hidden': _make_skill_data(name='hidden'),
            }
        )
        query = _make_query(variables={PIPELINE_BOUND_SKILLS_KEY: ['visible']})

        result = get_visible_skills(ap, query)

        assert list(result.keys()) == ['visible']

    def test_restore_activated_skills_uses_caller_provided_names_and_visibility(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILLS_KEY,
            PIPELINE_BOUND_SKILLS_KEY,
            get_activated_skill_names,
            restore_activated_skills,
        )

        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager(
            {
                'visible': _make_skill_data(name='visible'),
                'hidden': _make_skill_data(name='hidden'),
            }
        )
        query = _make_query(variables={PIPELINE_BOUND_SKILLS_KEY: ['visible']})

        restored = restore_activated_skills(ap, query, ['visible', 'hidden', 'visible', ''])

        assert restored == ['visible']
        assert list(query.variables[ACTIVATED_SKILLS_KEY].keys()) == ['visible']
        assert get_activated_skill_names(query) == ['visible']

    def test_resolve_virtual_skill_path_allows_visible_skill_reads(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            PIPELINE_BOUND_SKILLS_KEY,
            resolve_virtual_skill_path,
        )

        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo')})
        query = _make_query(variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']})

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

        assert '_LB_SYSTEM_PYTHON="$(command -v python3 || command -v python || true)"' in command
        assert '"$_LB_SYSTEM_PYTHON" -m venv "$_LB_VENV_DIR"' in command
        assert 'export VIRTUAL_ENV="$_LB_VENV_DIR"' in command
        assert command.rstrip().endswith('python scripts/run.py')

    def test_wrap_skill_python_env_keeps_state_outside_read_only_source(self):
        from langbot.pkg.provider.tools.loaders.skill import wrap_skill_command_with_python_env

        command = wrap_skill_command_with_python_env(
            'python scripts/run.py',
            mount_path='/workspace/.skills/demo',
            state_path='/workspace/.skill-envs/demo',
        )

        assert '_LB_VENV_DIR="/workspace/.skill-envs/demo/.venv"' in command
        assert '_LB_META_DIR="/workspace/.skill-envs/demo/.langbot"' in command
        assert '_LB_TMP_DIR="/workspace/.skill-envs/demo/.tmp"' in command
        assert '_LB_PIP_CACHE_DIR="/workspace/.skill-envs/demo/.cache/pip"' in command
        assert 'root = "/workspace/.skills/demo"' in command
        assert 'pip install "/workspace/.skills/demo"' in command


class TestSkillToolLoader:
    """Skill activation and resources are independent from sandbox execution.

    The legacy CRUD authoring tools (create/list/get/update/delete/
    import_skill_from_directory/reload_skills) were removed; skill CRUD is
    handled by SkillService via the HTTP API / web UI instead.
    """

    @pytest.mark.asyncio
    async def test_activate_returns_instructions_and_registers_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            ACTIVATE_SKILL_TOOL_NAME,
            SkillToolLoader,
        )
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY

        skill = _make_skill_data(name='demo', package_root='/data/skills/demo', instructions='Step 1')
        skill['revision'] = 'sha256:demo'
        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager({'demo': skill})
        ap.skill_repository = SimpleNamespace(get_skill=AsyncMock(return_value=skill))
        ap.box_service = SimpleNamespace(is_workspace_sandbox_available=AsyncMock(return_value=False))

        loader = SkillToolLoader(ap)
        query = _make_query()

        result = await loader.invoke_tool(ACTIVATE_SKILL_TOOL_NAME, {'skill_name': 'demo'}, query)

        assert result['activated'] is True
        assert result['skill_name'] == 'demo'
        assert result['mount_path'] is None
        assert result['revision'] == 'sha256:demo'
        assert result['capabilities']['resources_readable'] is True
        assert result['capabilities']['execution_available'] is False
        assert result['activated_skill_names'] == ['demo']
        assert 'Step 1' in result['content']
        assert '<package-root>' not in result['content']
        assert set(query.variables[ACTIVATED_SKILLS_KEY].keys()) == {'demo'}

    @pytest.mark.asyncio
    async def test_activate_unknown_skill_raises(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            ACTIVATE_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo')})

        loader = SkillToolLoader(ap)

        with pytest.raises(ValueError, match='not found'):
            await loader.invoke_tool(
                ACTIVATE_SKILL_TOOL_NAME,
                {'skill_name': 'ghost'},
                _make_query(),
            )

    @pytest.mark.asyncio
    async def test_register_skill_scans_directory_and_creates_skill(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            REGISTER_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            repo_dir = os.path.join(tmpdir, 'repo')
            os.makedirs(repo_dir)

            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                default_workspace=tmpdir,
                available=True,
                require_workspace_sandbox=AsyncMock(return_value=_CONTEXT),
            )
            ap.skill_service = SimpleNamespace(
                scan_directory_async=AsyncMock(
                    return_value={
                        'name': 'cloned-skill',
                        'display_name': 'Cloned Skill',
                        'description': 'Imported from clone',
                        'instructions': 'Do work',
                    }
                ),
                import_skill_directory=AsyncMock(
                    return_value=_make_skill_data(name='cloned-skill', package_root=os.path.realpath(repo_dir))
                ),
            )

            loader = SkillToolLoader(ap)
            result = await loader.invoke_tool(
                REGISTER_SKILL_TOOL_NAME,
                {'path': '/workspace/repo'},
                _make_query(),
            )

        ap.skill_service.scan_directory_async.assert_awaited_once_with(_CONTEXT, os.path.realpath(repo_dir))
        ap.skill_service.import_skill_directory.assert_awaited_once_with(
            _CONTEXT,
            os.path.realpath(repo_dir),
            {
                'name': 'cloned-skill',
                'display_name': 'Cloned Skill',
                'description': 'Imported from clone',
                'instructions': 'Do work',
            },
        )
        assert result['registered'] is True
        assert result['skill_name'] == 'cloned-skill'
        assert result['source_path'] == '/workspace/repo'

    @pytest.mark.asyncio
    async def test_register_skill_rejects_workspace_escape(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            REGISTER_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                default_workspace=tmpdir,
                available=True,
                require_workspace_sandbox=AsyncMock(return_value=_CONTEXT),
            )
            ap.skill_service = SimpleNamespace(
                scan_directory_async=AsyncMock(),
                import_skill_directory=AsyncMock(),
            )

            loader = SkillToolLoader(ap)

            with pytest.raises(ValueError, match='escapes the workspace boundary'):
                await loader.invoke_tool(
                    REGISTER_SKILL_TOOL_NAME,
                    {'path': '/workspace/../../etc'},
                    _make_query(),
                )

    @pytest.mark.asyncio
    async def test_register_skill_requires_skill_service(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            REGISTER_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()  # no skill_service attribute
            ap.box_service = SimpleNamespace(
                default_workspace=tmpdir,
                available=True,
                require_workspace_sandbox=AsyncMock(return_value=_CONTEXT),
            )

            loader = SkillToolLoader(ap)

            with pytest.raises(ValueError, match='Skill service not available'):
                await loader.invoke_tool(
                    REGISTER_SKILL_TOOL_NAME,
                    {'path': '/workspace/foo'},
                    _make_query(),
                )

    @pytest.mark.asyncio
    async def test_read_only_tools_remain_when_sandbox_unavailable(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(skills={})
        ap.skill_repository = SimpleNamespace()

        loader = SkillToolLoader(ap)
        await loader.initialize()

        assert sorted(tool.name for tool in await loader.get_tools(sandbox_available=False)) == [
            'activate',
            'list_skill_resources',
            'read_skill_resource',
        ]
        assert await loader.has_tool('activate') is True
        assert await loader.has_tool('register_skill') is False

    @pytest.mark.asyncio
    async def test_tools_exposed_when_sandbox_backend_available(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo')})
        ap.skill_repository = SimpleNamespace()

        loader = SkillToolLoader(ap)
        await loader.initialize()

        tools = await loader.get_tools(sandbox_available=True)

        assert sorted(tool.name for tool in tools) == [
            'activate',
            'list_skill_resources',
            'read_skill_resource',
            'register_skill',
        ]
        assert await loader.has_tool('activate') is True
        assert await loader.has_tool('register_skill', sandbox_available=True) is True

    @pytest.mark.asyncio
    async def test_register_skill_appears_after_sandbox_recovers(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo')})
        ap.skill_repository = SimpleNamespace()

        loader = SkillToolLoader(ap)
        await loader.initialize()
        assert 'register_skill' not in {tool.name for tool in await loader.get_tools(sandbox_available=False)}
        assert 'register_skill' in {tool.name for tool in await loader.get_tools(sandbox_available=True)}

    @pytest.mark.asyncio
    async def test_resources_require_activation_and_use_pinned_revision(self):
        from langbot.pkg.provider.tools.loaders.skill import register_activated_skill
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        skill = _make_skill_data(name='demo', instructions='Read references')
        skill['revision'] = 'sha256:demo'
        ap = _make_ap()
        ap.skill_mgr = _make_skill_manager({'demo': skill})
        ap.skill_repository = SimpleNamespace(
            list_skill_resources=AsyncMock(
                return_value={'entries': [{'path': 'references/a.md'}], 'revision': 'sha256:demo'}
            ),
            read_skill_resource=AsyncMock(
                return_value={
                    'path': 'references/a.md',
                    'content': 'reference text',
                    'revision': 'sha256:demo',
                    'mime_type': 'text/markdown',
                }
            ),
        )
        loader = SkillToolLoader(ap)
        query = _make_query()

        with pytest.raises(ValueError, match='must be activated'):
            await loader.invoke_tool(
                'read_skill_resource',
                {'skill_name': 'demo', 'path': 'references/a.md'},
                query,
            )

        register_activated_skill(query, skill)
        listed = await loader.invoke_tool('list_skill_resources', {'skill_name': 'demo'}, query)
        read = await loader.invoke_tool(
            'read_skill_resource',
            {'skill_name': 'demo', 'path': 'references/a.md', 'revision': 'sha256:demo'},
            query,
        )

        assert listed['entries'][0]['path'] == 'references/a.md'
        assert read['content'] == 'reference text'
        ap.skill_repository.list_skill_resources.assert_awaited_once_with(
            _CONTEXT,
            'demo',
            '.',
            expected_revision='sha256:demo',
        )
        ap.skill_repository.read_skill_resource.assert_awaited_once_with(
            _CONTEXT,
            'demo',
            'references/a.md',
            expected_revision='sha256:demo',
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
            ap.box_service = SimpleNamespace(
                available=True,
                default_workspace=tmpdir,
                shares_filesystem_with_box=True,
            )
            ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            result = await loader.invoke_tool(
                'read',
                {'path': '/workspace/.skills/demo/SKILL.md'},
                _make_query(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']}),
            )

            assert result['ok'] is True
            assert result['content'] == 'demo instructions'
            assert result['truncated'] is False

    @pytest.mark.asyncio
    async def test_external_runtime_read_uses_core_skill_repository(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'SKILL.md'), 'w', encoding='utf-8') as file_obj:
                file_obj.write('core-host-secret')

            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                available=True,
                shares_filesystem_with_box=False,
            )
            ap.skill_repository = SimpleNamespace(
                read_skill_file=AsyncMock(return_value={'content': 'repository-content'})
            )
            ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)
            query = _make_query(
                query_id='q-external-read',
                variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']},
            )

            result = await loader.invoke_tool(
                'read',
                {'path': '/workspace/.skills/demo/SKILL.md'},
                query,
            )

            assert result['ok'] is True
            assert result['content'] == 'repository-content'
            assert 'core-host-secret' not in repr(result)
            ap.skill_repository.read_skill_file.assert_awaited_once_with(_CONTEXT, 'demo', 'SKILL.md')

    @pytest.mark.asyncio
    async def test_core_owned_skill_path_does_not_depend_on_runtime_topology(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            with open(os.path.join(tmpdir, 'secret.txt'), 'w', encoding='utf-8') as file_obj:
                file_obj.write('core-host-secret')

            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                available=True,
                shares_filesystem_with_box=False,
            )
            ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)
            query = _make_query(
                query_id='q-external-no-protocol',
                variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']},
            )

            result = await loader.invoke_tool(
                'grep',
                {
                    'path': '/workspace/.skills/demo',
                    'pattern': 'core-host-secret',
                },
                query,
            )

            assert result['ok'] is True
            assert result['total'] == 1

    @pytest.mark.asyncio
    async def test_exec_in_activated_skill_mount_rewrites_command_without_mutating_skill(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                available=True,
                default_workspace=tmpdir,
                execute_tool=AsyncMock(return_value={'ok': True}),
            )
            skill_data = _make_skill_data(name='demo', package_root=tmpdir)
            ap.skill_mgr = _make_skill_manager(
                {'demo': skill_data},
                refresh_skill_from_disk=Mock(),
            )
            loader = NativeToolLoader(ap)

            query = _make_query(query_id='q1', launcher_type='person', launcher_id='123')
            register_activated_skill(query, skill_data)

            result = await loader.invoke_tool(
                'exec',
                {
                    'command': 'python /workspace/.skills/demo/scripts/run.py',
                    'workdir': '/workspace/.skills/demo',
                },
                query,
            )

            assert result['ok'] is True
            tool_parameters = ap.box_service.execute_tool.await_args.args[0]
            assert tool_parameters['command'] == 'python /workspace/.skills/demo/scripts/run.py'
            assert tool_parameters['workdir'] == '/workspace/.skills/demo'
            assert 'skill_name' not in ap.box_service.execute_tool.await_args.kwargs
            ap.skill_mgr.refresh_skill_from_disk.assert_not_called()

    @pytest.mark.asyncio
    async def test_external_runtime_python_skill_uses_trusted_metadata_and_writable_env(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

        ap = _make_ap()
        ap.box_service = SimpleNamespace(
            available=True,
            shares_filesystem_with_box=False,
            execute_tool=AsyncMock(return_value={'ok': True}),
        )
        skill_data = _make_skill_data(
            name='demo',
            package_root='/box-runtime/skills/tenants/workspace/demo',
            python_project=True,
        )
        ap.skill_mgr = _make_skill_manager(
            {'demo': skill_data},
            refresh_skill_from_disk=Mock(),
        )
        loader = NativeToolLoader(ap)
        query = _make_query(query_id='q-external', launcher_type='person', launcher_id='123')
        register_activated_skill(query, skill_data)

        result = await loader.invoke_tool(
            'exec',
            {
                'command': 'python /workspace/.skills/demo/scripts/run.py',
                'workdir': '/workspace/.skills/demo',
            },
            query,
        )

        assert result['ok'] is True
        tool_parameters = ap.box_service.execute_tool.await_args.args[0]
        wrapped = tool_parameters['command']
        assert '_LB_VENV_DIR="/workspace/.skill-envs/demo/.venv"' in wrapped
        assert 'root = "/workspace/.skills/demo"' in wrapped
        assert '/box-runtime/skills/tenants/workspace/demo' not in wrapped
        assert 'skill_name' not in ap.box_service.execute_tool.await_args.kwargs

    @pytest.mark.asyncio
    async def test_write_requires_skill_activation(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(available=True, default_workspace=tmpdir)
            ap.skill_mgr = _make_skill_manager({'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            query = _make_query(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']})

            with pytest.raises(ValueError, match='Skill "demo" is not available at this path'):
                await loader.invoke_tool(
                    'write',
                    {'path': '/workspace/.skills/demo/notes.txt', 'content': 'hi'},
                    query,
                )

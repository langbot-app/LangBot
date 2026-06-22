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


class TestSkillManagerCache:
    """The Box runtime is the only source of truth — SkillManager just holds
    an in-memory cache populated by ``reload_skills``. There is no local
    filesystem reader anymore."""

    def test_refresh_skill_from_disk_reports_cache_presence(self):
        """Box is the only source of truth for skill content. refresh_skill_from_disk
        now just reports whether the skill is still in the in-memory cache —
        the actual content refresh is driven by SkillService awaiting
        ``reload_skills`` after every Box mutation."""
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        # Empty cache → returns False
        assert mgr.refresh_skill_from_disk('test-skill') is False

        # Cache populated → returns True; method does NOT mutate the cache
        cached = _make_skill_data(name='test-skill', instructions='Cached')
        mgr.skills['test-skill'] = cached
        assert mgr.refresh_skill_from_disk('test-skill') is True
        assert mgr.skills['test-skill'] is cached
        assert mgr.refresh_skill_from_disk('') is False

    @pytest.mark.asyncio
    async def test_reload_skills_drops_box_skills_with_missing_package_root(self):
        """When LangBot shares a filesystem with Box (local stdio mode) and Box
        reports a skill whose package_root is gone from that shared filesystem,
        the cache must drop it instead of keeping a stale entry that would later
        produce a bad mount."""
        from langbot.pkg.skill.manager import SkillManager

        with tempfile.TemporaryDirectory() as live_dir:
            ghost_dir = os.path.join(live_dir, '_does_not_exist')
            box_service = SimpleNamespace(
                available=True,
                shares_filesystem_with_box=True,
                list_skills=AsyncMock(
                    return_value=[
                        _make_skill_data(name='alive', package_root=live_dir),
                        _make_skill_data(name='ghost', package_root=ghost_dir),
                    ]
                ),
            )

            ap = _make_ap()
            ap.box_service = box_service
            mgr = SkillManager(ap)

            await mgr.reload_skills()

        assert list(mgr.skills) == ['alive']
        # Warning fired with the dropped skill name so operators can see it.
        warning_messages = [str(call.args[0]) for call in ap.logger.warning.call_args_list]
        assert any('ghost' in msg and 'package_root missing' in msg for msg in warning_messages)

    @pytest.mark.asyncio
    async def test_reload_skills_trusts_box_paths_when_filesystem_not_shared(self):
        """In separated deployments (Docker Compose, k8s sidecar,
        --standalone-box, remote endpoint) the package_root reported by Box
        lives on the Box runtime's filesystem and is not resolvable on the
        LangBot side. The cache must keep every Box-reported skill rather than
        dropping them all via a local isdir() check."""
        from langbot.pkg.skill.manager import SkillManager

        box_service = SimpleNamespace(
            available=True,
            shares_filesystem_with_box=False,
            list_skills=AsyncMock(
                return_value=[
                    _make_skill_data(name='alpha', package_root='/box/skills/alpha'),
                    _make_skill_data(name='beta', package_root='/box/skills/beta'),
                ]
            ),
        )

        ap = _make_ap()
        ap.box_service = box_service
        mgr = SkillManager(ap)

        await mgr.reload_skills()

        assert sorted(mgr.skills) == ['alpha', 'beta']
        # No skill dropped → no "package_root missing" warning.
        warning_messages = [str(call.args[0]) for call in ap.logger.warning.call_args_list]
        assert not any('package_root missing' in msg for msg in warning_messages)


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
        mgr.skills = {
            'primary': _make_skill_data(name='primary', instructions='Primary instructions'),
        }
        ap.skill_mgr = mgr

        query = SimpleNamespace(variables={})

        assert register_activated_skill(ap, query, 'primary') is True
        assert set(query.variables[ACTIVATED_SKILLS_KEY].keys()) == {'primary'}
        assert query.variables[ACTIVATED_SKILLS_KEY]['primary']['name'] == 'primary'

    def test_register_activated_skill_rejects_unknown_skill(self):
        from langbot.pkg.skill.activation import register_activated_skill
        from langbot.pkg.provider.tools.loaders.skill import ACTIVATED_SKILLS_KEY
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {'primary': _make_skill_data(name='primary')}
        ap.skill_mgr = mgr

        query = SimpleNamespace(variables={})

        assert register_activated_skill(ap, query, 'missing') is False
        assert ACTIVATED_SKILLS_KEY not in query.variables

    def test_register_activated_skill_without_skill_manager_returns_false(self):
        from langbot.pkg.skill.activation import register_activated_skill

        ap = _make_ap()  # no skill_mgr attribute
        query = SimpleNamespace(variables={})

        assert register_activated_skill(ap, query, 'primary') is False


class TestPersistActivatedSkill:
    """Host-side persistence of activated skills into conversation state (S-01/S-02)."""

    @pytest.mark.asyncio
    async def test_persist_writes_conversation_state(self):
        from unittest.mock import patch
        from langbot.pkg.provider.tools.loaders.skill import (
            persist_activated_skill,
            ACTIVATED_SKILLS_KEY,
            ACTIVATED_SKILL_NAMES_STATE_KEY,
        )

        ap = _make_ap()
        ap.persistence_mgr.get_db_engine = Mock(return_value=Mock())

        query = SimpleNamespace(variables={ACTIVATED_SKILLS_KEY: {'pdf': {'name': 'pdf'}}})
        query._agent_run_session = {
            'runner_id': 'plugin:langbot/local-agent/default',
            'state_context': {
                'scope_keys': {'conversation': 'conv-scope-key'},
                'binding_identity': 'binding-1',
                'conversation_id': 'c1',
            },
        }

        store = SimpleNamespace(state_set=AsyncMock(return_value=(True, None)))
        with patch(
            'langbot.pkg.agent.runner.persistent_state_store.get_persistent_state_store',
            return_value=store,
        ):
            await persist_activated_skill(ap, query, 'pdf')

        store.state_set.assert_awaited_once()
        kwargs = store.state_set.await_args.kwargs
        assert kwargs['scope_key'] == 'conv-scope-key'
        assert kwargs['state_key'] == ACTIVATED_SKILL_NAMES_STATE_KEY
        assert kwargs['value'] == ['pdf']
        assert kwargs['scope'] == 'conversation'
        assert kwargs['runner_id'] == 'plugin:langbot/local-agent/default'
        assert kwargs['binding_identity'] == 'binding-1'

    @pytest.mark.asyncio
    async def test_persist_noop_without_run_session(self):
        from unittest.mock import patch
        from langbot.pkg.provider.tools.loaders.skill import persist_activated_skill

        ap = _make_ap()
        query = SimpleNamespace(variables={'_activated_skills': {'pdf': {'name': 'pdf'}}})

        with patch(
            'langbot.pkg.agent.runner.persistent_state_store.get_persistent_state_store',
        ) as mock_factory:
            await persist_activated_skill(ap, query, 'pdf')

        mock_factory.assert_not_called()


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

    def test_restore_activated_skills_from_state_filters_by_visibility(self):
        from langbot.pkg.provider.tools.loaders.skill import (
            ACTIVATED_SKILLS_KEY,
            ACTIVATED_SKILL_NAMES_STATE_KEY,
            PIPELINE_BOUND_SKILLS_KEY,
            get_activated_skill_names,
            restore_activated_skills_from_state,
        )

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={
                'visible': _make_skill_data(name='visible'),
                'hidden': _make_skill_data(name='hidden'),
            }
        )
        query = SimpleNamespace(variables={PIPELINE_BOUND_SKILLS_KEY: ['visible']})
        state = {'conversation': {ACTIVATED_SKILL_NAMES_STATE_KEY: ['visible', 'hidden', 'visible', '']}}

        restored = restore_activated_skills_from_state(ap, query, state)

        assert restored == ['visible']
        assert list(query.variables[ACTIVATED_SKILLS_KEY].keys()) == ['visible']
        assert get_activated_skill_names(query) == ['visible']

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

        assert '_LB_SYSTEM_PYTHON="$(command -v python3 || command -v python || true)"' in command
        assert '"$_LB_SYSTEM_PYTHON" -m venv "$_LB_VENV_DIR"' in command
        assert 'export VIRTUAL_ENV="$_LB_VENV_DIR"' in command
        assert command.rstrip().endswith('python scripts/run.py')


class TestSkillToolLoader:
    """The skill tool surface is now just ``activate`` + ``register_skill``.

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
        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={'demo': skill},
            get_skill_by_name=lambda name: skill if name == 'demo' else None,
        )

        loader = SkillToolLoader(ap)
        query = SimpleNamespace(variables={})

        result = await loader.invoke_tool(ACTIVATE_SKILL_TOOL_NAME, {'skill_name': 'demo'}, query)

        assert result['activated'] is True
        assert result['skill_name'] == 'demo'
        assert result['mount_path'] == '/workspace/.skills/demo'
        assert result['activated_skill_names'] == ['demo']
        assert 'Step 1' in result['content']
        assert set(query.variables[ACTIVATED_SKILLS_KEY].keys()) == {'demo'}

    @pytest.mark.asyncio
    async def test_activate_unknown_skill_raises(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            ACTIVATE_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(
            skills={'demo': _make_skill_data(name='demo')},
            get_skill_by_name=lambda name: None,
        )

        loader = SkillToolLoader(ap)

        with pytest.raises(ValueError, match='not found'):
            await loader.invoke_tool(
                ACTIVATE_SKILL_TOOL_NAME,
                {'skill_name': 'ghost'},
                SimpleNamespace(variables={}),
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
            ap.box_service = SimpleNamespace(default_workspace=tmpdir, available=True)
            ap.skill_service = SimpleNamespace(
                scan_directory_async=AsyncMock(
                    return_value={
                        'name': 'cloned-skill',
                        'display_name': 'Cloned Skill',
                        'description': 'Imported from clone',
                        'instructions': 'Do work',
                    }
                ),
                create_skill=AsyncMock(
                    return_value=_make_skill_data(name='cloned-skill', package_root=os.path.realpath(repo_dir))
                ),
            )

            loader = SkillToolLoader(ap)
            result = await loader.invoke_tool(
                REGISTER_SKILL_TOOL_NAME,
                {'path': '/workspace/repo'},
                SimpleNamespace(),
            )

        ap.skill_service.scan_directory_async.assert_awaited_once_with(os.path.realpath(repo_dir))
        ap.skill_service.create_skill.assert_awaited_once_with(
            {
                'name': 'cloned-skill',
                'display_name': 'Cloned Skill',
                'description': 'Imported from clone',
                'instructions': 'Do work',
                'package_root': os.path.realpath(repo_dir),
            }
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
            ap.box_service = SimpleNamespace(default_workspace=tmpdir, available=True)
            ap.skill_service = SimpleNamespace(scan_directory_async=AsyncMock(), create_skill=AsyncMock())

            loader = SkillToolLoader(ap)

            with pytest.raises(ValueError, match='escapes the workspace boundary'):
                await loader.invoke_tool(
                    REGISTER_SKILL_TOOL_NAME,
                    {'path': '/workspace/../../etc'},
                    SimpleNamespace(),
                )

    @pytest.mark.asyncio
    async def test_register_skill_requires_skill_service(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import (
            REGISTER_SKILL_TOOL_NAME,
            SkillToolLoader,
        )

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()  # no skill_service attribute
            ap.box_service = SimpleNamespace(default_workspace=tmpdir, available=True)

            loader = SkillToolLoader(ap)

            with pytest.raises(ValueError, match='Skill service not available'):
                await loader.invoke_tool(
                    REGISTER_SKILL_TOOL_NAME,
                    {'path': '/workspace/foo'},
                    SimpleNamespace(),
                )

    @pytest.mark.asyncio
    async def test_tools_hidden_when_sandbox_backend_unavailable(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(skills={})
        ap.box_service = SimpleNamespace(
            available=True,
            get_status=AsyncMock(return_value={'backend': {'available': False}}),
        )

        loader = SkillToolLoader(ap)
        await loader.initialize()

        assert await loader.get_tools() == []
        assert await loader.has_tool('activate') is False
        assert await loader.has_tool('register_skill') is False

    @pytest.mark.asyncio
    async def test_tools_exposed_when_sandbox_backend_available(self):
        from langbot.pkg.provider.tools.loaders.skill_authoring import SkillToolLoader

        ap = _make_ap()
        ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo')})
        ap.box_service = SimpleNamespace(
            available=True,
            get_status=AsyncMock(return_value={'backend': {'available': True}}),
        )

        loader = SkillToolLoader(ap)
        await loader.initialize()

        tools = await loader.get_tools()

        assert sorted(tool.name for tool in tools) == ['activate', 'register_skill']
        assert await loader.has_tool('activate') is True
        assert await loader.has_tool('register_skill') is True


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
            ap.box_service = SimpleNamespace(available=True, default_workspace=tmpdir)
            ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            result = await loader.invoke_tool(
                'read',
                {'path': '/workspace/.skills/demo/SKILL.md'},
                SimpleNamespace(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']}),
            )

            assert result['ok'] is True
            assert result['content'] == 'demo instructions'
            assert result['truncated'] is False

    @pytest.mark.asyncio
    async def test_exec_in_activated_skill_mount_rewrites_command_and_refreshes(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import register_activated_skill

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(
                available=True,
                default_workspace=tmpdir,
                execute_tool=AsyncMock(return_value={'ok': True}),
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

            assert result['ok'] is True
            tool_parameters = ap.box_service.execute_tool.await_args.args[0]
            assert tool_parameters['command'] == 'python /workspace/.skills/demo/scripts/run.py'
            assert tool_parameters['workdir'] == '/workspace/.skills/demo'
            ap.skill_mgr.refresh_skill_from_disk.assert_called_once_with('demo')

    @pytest.mark.asyncio
    async def test_write_requires_skill_activation(self):
        from langbot.pkg.provider.tools.loaders.native import NativeToolLoader
        from langbot.pkg.provider.tools.loaders.skill import PIPELINE_BOUND_SKILLS_KEY

        with tempfile.TemporaryDirectory() as tmpdir:
            ap = _make_ap()
            ap.box_service = SimpleNamespace(available=True, default_workspace=tmpdir)
            ap.skill_mgr = SimpleNamespace(skills={'demo': _make_skill_data(name='demo', package_root=tmpdir)})
            loader = NativeToolLoader(ap)

            query = SimpleNamespace(query_id='q1', variables={PIPELINE_BOUND_SKILLS_KEY: ['demo']})

            with pytest.raises(ValueError, match='Skill "demo" is not available at this path'):
                await loader.invoke_tool(
                    'write',
                    {'path': '/workspace/.skills/demo/notes.txt', 'content': 'hi'},
                    query,
                )

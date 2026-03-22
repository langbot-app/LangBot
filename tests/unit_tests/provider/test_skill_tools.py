"""Tests for SkillManager package skill loading and skill tool aggregation."""

from __future__ import annotations

import os
import tempfile
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock

import pytest


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
    source_type='inline',
    instructions='Do something',
    package_root=None,
    entry_file='SKILL.md',
    skill_tools=None,
    requires_skills=None,
    **kwargs,
):
    return {
        'uuid': f'uuid-{name}',
        'name': name,
        'description': f'Description of {name}',
        'instructions': instructions,
        'type': 'skill',
        'source_type': source_type,
        'package_root': package_root,
        'entry_file': entry_file,
        'skill_tools': skill_tools or [],
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
    """Test SkillManager._load_package_instructions()."""

    def test_load_package_instructions_success(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_md = os.path.join(tmpdir, 'SKILL.md')
            with open(skill_md, 'w') as f:
                f.write('# Test Skill\nDo things.')

            skill_data = _make_skill_data(
                source_type='package',
                package_root=tmpdir,
            )
            result = mgr._load_package_instructions(skill_data)

            assert result is True
            assert skill_data['instructions'] == '# Test Skill\nDo things.'

    def test_load_package_instructions_missing_file(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            skill_data = _make_skill_data(
                source_type='package',
                package_root=tmpdir,
            )
            result = mgr._load_package_instructions(skill_data)

            assert result is False
            ap.logger.warning.assert_called_once()

    def test_load_package_instructions_no_package_root(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        skill_data = _make_skill_data(source_type='package', package_root=None)
        result = mgr._load_package_instructions(skill_data)

        assert result is False

    def test_load_package_instructions_custom_entry_file(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        with tempfile.TemporaryDirectory() as tmpdir:
            entry = os.path.join(tmpdir, 'README.md')
            with open(entry, 'w') as f:
                f.write('Custom entry')

            skill_data = _make_skill_data(
                source_type='package',
                package_root=tmpdir,
                entry_file='README.md',
            )
            result = mgr._load_package_instructions(skill_data)

            assert result is True
            assert skill_data['instructions'] == 'Custom entry'


class TestSkillManagerGetSkillTools:
    """Test SkillManager.get_skill_tools() and namespace behavior."""

    def test_get_skill_tools_empty(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {'my-skill': _make_skill_data(name='my-skill', skill_tools=[])}

        tools = mgr.get_skill_tools('my-skill')
        assert tools == []

    def test_get_skill_tools_namespaced(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        tool_def = {
            'name': 'run_review',
            'description': 'Run review',
            'entry': 'scripts/review.py',
            'parameters': {},
            'timeout_sec': 30,
            'network': False,
        }
        mgr.skills = {
            'code-review': _make_skill_data(name='code-review', skill_tools=[tool_def])
        }

        tools = mgr.get_skill_tools('code-review')
        assert len(tools) == 1
        assert tools[0]['name'] == 'skill__code-review__run_review'
        assert tools[0]['_original_name'] == 'run_review'
        assert tools[0]['_skill_name'] == 'code-review'

    def test_get_skill_tools_with_sub_skills(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)

        parent_tool = {'name': 'parent_tool', 'description': 'P', 'entry': 'scripts/p.py', 'parameters': {}}
        child_tool = {'name': 'child_tool', 'description': 'C', 'entry': 'scripts/c.py', 'parameters': {}}

        mgr.skills = {
            'parent': _make_skill_data(
                name='parent',
                skill_tools=[parent_tool],
                requires_skills=['child'],
            ),
            'child': _make_skill_data(
                name='child',
                skill_tools=[child_tool],
            ),
        }

        tools = mgr.get_skill_tools('parent')
        assert len(tools) == 2
        names = {t['name'] for t in tools}
        assert 'skill__parent__parent_tool' in names
        assert 'skill__child__child_tool' in names

    def test_get_skill_tools_nonexistent_skill(self):
        from langbot.pkg.skill.manager import SkillManager

        ap = _make_ap()
        mgr = SkillManager(ap)
        mgr.skills = {}

        tools = mgr.get_skill_tools('nonexistent')
        assert tools == []


class TestSkillToolLoader:
    """Test SkillToolLoader query-scoped registration and lookup."""

    def test_register_and_has_tool(self):
        from langbot.pkg.provider.tools.loaders.skill import SkillToolLoader, register_skill_tools

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        skill_tools = [
            {
                'name': 'skill__test__run',
                '_original_name': 'run',
                '_skill_name': 'test',
                'entry': 'scripts/run.py',
                'description': 'Run',
                'parameters': {},
            }
        ]

        register_skill_tools(query, skill_tools, skill_data)

        assert loader.has_tool('skill__test__run', query) is True
        assert loader.has_tool('nonexistent', query) is False

    def test_query_isolation(self):
        from langbot.pkg.provider.tools.loaders.skill import SkillToolLoader, register_skill_tools

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query1 = SimpleNamespace(variables={})
        query2 = SimpleNamespace(variables={})
        skill_data = _make_skill_data(name='test')
        skill_tools = [
            {
                'name': 'skill__test__run',
                '_original_name': 'run',
                '_skill_name': 'test',
                'entry': 'scripts/run.py',
                'description': 'Run',
                'parameters': {},
            }
        ]

        register_skill_tools(query1, skill_tools, skill_data)

        assert loader.has_tool('skill__test__run', query1) is True
        assert loader.has_tool('skill__test__run', query2) is False

    def test_no_variables_returns_false(self):
        from langbot.pkg.provider.tools.loaders.skill import SkillToolLoader

        ap = _make_ap()
        loader = SkillToolLoader(ap)

        query = SimpleNamespace(variables=None)
        assert loader.has_tool('anything', query) is False


class TestBoxServiceSkillTool:
    """Test BoxService.execute_skill_tool() spec construction."""

    def test_build_entry_command_py(self):
        from langbot.pkg.box.service import BoxService

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        cmd = service._build_entry_command('scripts/review.py')
        assert cmd == 'python /workspace/scripts/review.py'

    def test_build_entry_command_sh(self):
        from langbot.pkg.box.service import BoxService

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        cmd = service._build_entry_command('scripts/run.sh')
        assert cmd == 'bash /workspace/scripts/run.sh'

    def test_build_entry_command_js(self):
        from langbot.pkg.box.service import BoxService

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        cmd = service._build_entry_command('scripts/app.js')
        assert cmd == 'node /workspace/scripts/app.js'

    def test_build_entry_command_unsupported(self):
        from langbot.pkg.box.service import BoxService
        from langbot.pkg.box.errors import BoxValidationError

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        with pytest.raises(BoxValidationError, match='unsupported'):
            service._build_entry_command('scripts/run.rb')

    def test_build_entry_command_empty(self):
        from langbot.pkg.box.service import BoxService
        from langbot.pkg.box.errors import BoxValidationError

        ap = _make_ap()
        ap.instance_config = SimpleNamespace(data={})
        service = BoxService(ap, client=Mock())

        with pytest.raises(BoxValidationError, match='empty'):
            service._build_entry_command('')

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

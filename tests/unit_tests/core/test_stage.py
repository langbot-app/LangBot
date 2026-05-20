"""Tests for core boot stage registration and abstract classes."""

from __future__ import annotations

from unittest.mock import MagicMock
import pytest

from tests.utils.import_isolation import isolated_sys_modules


class TestStageClassDecorator:
    """Tests for @stage_class decorator."""

    def _make_stage_import_mocks(self):
        """Create mocks for stage import."""
        return {
            'langbot.pkg.core.app': MagicMock(),
        }

    def test_stage_class_registers_stage(self):
        """@stage_class registers stage in preregistered_stages."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import stage_class, preregistered_stages

            # Clear for clean test
            preregistered_stages.clear()

            @stage_class('TestStage')
            class TestStage:
                pass

            assert 'TestStage' in preregistered_stages
            assert preregistered_stages['TestStage'] == TestStage

    def test_stage_class_returns_original_class(self):
        """@stage_class returns the original class unchanged."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import stage_class

            @stage_class('TestStage')
            class TestStage:
                value = 42

            # Class attributes should be preserved
            assert TestStage.value == 42

    def test_stage_class_multiple_stages(self):
        """Multiple stages can be registered."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import stage_class, preregistered_stages

            preregistered_stages.clear()

            @stage_class('Stage1')
            class Stage1:
                pass

            @stage_class('Stage2')
            class Stage2:
                pass

            assert len(preregistered_stages) == 2
            assert preregistered_stages['Stage1'] == Stage1
            assert preregistered_stages['Stage2'] == Stage2


class TestBootingStageAbstract:
    """Tests for BootingStage abstract class."""

    def _make_stage_import_mocks(self):
        return {'langbot.pkg.core.app': MagicMock()}

    def test_booting_stage_is_abstract(self):
        """BootingStage is abstract and cannot be instantiated directly."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import BootingStage

            with pytest.raises(TypeError):
                BootingStage()

    def test_booting_stage_requires_run_method(self):
        """Subclass must implement run method."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import BootingStage

            class IncompleteStage(BootingStage):
                pass

            with pytest.raises(TypeError):
                IncompleteStage()

    def test_booting_stage_subclass_works(self):
        """Complete subclass can be instantiated."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import BootingStage

            class CompleteStage(BootingStage):
                name = 'CompleteStage'

                async def run(self, ap):
                    pass

            stage = CompleteStage()
            assert stage.name == 'CompleteStage'

    def test_booting_stage_name_attribute(self):
        """BootingStage has name attribute (None by default in abstract)."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import BootingStage

            # Abstract class has name attribute defined as None
            assert hasattr(BootingStage, 'name')

    @pytest.mark.asyncio
    async def test_booting_stage_run_signature(self):
        """run method receives Application parameter."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import BootingStage

            class TestStage(BootingStage):
                name = 'TestStage'

                async def run(self, ap):
                    self.ap_received = ap

            stage = TestStage()
            mock_ap = MagicMock()

            await stage.run(mock_ap)
            assert stage.ap_received == mock_ap


class TestPreregisteredStages:
    """Tests for preregistered_stages global registry."""

    def _make_stage_import_mocks(self):
        return {'langbot.pkg.core.app': MagicMock()}

    def test_preregistered_stages_is_dict(self):
        """preregistered_stages is a dictionary."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import preregistered_stages

            assert isinstance(preregistered_stages, dict)

    def test_preregistered_stages_key_is_string(self):
        """Registry keys are stage names (strings)."""
        mocks = self._make_stage_import_mocks()

        with isolated_sys_modules(mocks):
            from langbot.pkg.core.stage import stage_class, preregistered_stages

            preregistered_stages.clear()

            @stage_class('MyStage')
            class MyStage:
                pass

            for key in preregistered_stages:
                assert isinstance(key, str)
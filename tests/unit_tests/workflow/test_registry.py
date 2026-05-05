"""Tests for the node type registry."""

import sys
import os
import pytest

sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', '..', 'src'))

from langbot.pkg.workflow.node import WorkflowNode, NodePort
from langbot.pkg.workflow.registry import NodeTypeRegistry


class DummyNode(WorkflowNode):
    type_name = "dummy"
    category = "process"
    name = "dummy"
    description = "A dummy node"

    async def execute(self, inputs, context):
        return {"output": "ok"}


class TriggerNode(WorkflowNode):
    type_name = "my_trigger"
    category = "trigger"
    name = "my_trigger"

    async def execute(self, inputs, context):
        return {}


class TestRegistryBasics:
    def setup_method(self):
        self.reg = NodeTypeRegistry()

    def test_register_and_get(self):
        self.reg.register("process.dummy", DummyNode)
        assert self.reg.get("process.dummy") is DummyNode

    def test_get_missing_returns_none(self):
        assert self.reg.get("process.nonexistent") is None

    def test_has_type(self):
        self.reg.register("process.dummy", DummyNode)
        assert self.reg.has_type("process.dummy") is True
        assert self.reg.has_type("process.missing") is False

    def test_count(self):
        assert self.reg.count() == 0
        self.reg.register("process.dummy", DummyNode)
        assert self.reg.count() == 1

    def test_clear(self):
        self.reg.register("process.dummy", DummyNode)
        self.reg.clear()
        assert self.reg.count() == 0

    def test_unregister(self):
        self.reg.register("process.dummy", DummyNode)
        self.reg.unregister("process.dummy")
        assert self.reg.get("process.dummy") is None
        assert self.reg.count() == 0


class TestRegistryLookupFormats:
    """Test that both full and short name lookups work."""

    def setup_method(self):
        self.reg = NodeTypeRegistry()
        self.reg.register("process.dummy", DummyNode)

    def test_full_name_lookup(self):
        assert self.reg.get("process.dummy") is DummyNode

    def test_short_name_lookup(self):
        """Short name (type_name only) should also resolve."""
        assert self.reg.get("dummy") is DummyNode


class TestRegistryCategories:
    def setup_method(self):
        self.reg = NodeTypeRegistry()
        self.reg.register("process.dummy", DummyNode)
        self.reg.register("trigger.my_trigger", TriggerNode)

    def test_list_by_category(self):
        process_nodes = self.reg.list_by_category("process")
        assert len(process_nodes) == 1
        assert process_nodes[0]["type"] == "process.dummy"

    def test_list_by_category_empty(self):
        assert self.reg.list_by_category("action") == []

    def test_get_categories(self):
        cats = self.reg.get_categories()
        assert "process" in cats
        assert "trigger" in cats
        assert len(cats["process"]) == 1
        assert len(cats["trigger"]) == 1


class TestCreateInstance:
    def setup_method(self):
        self.reg = NodeTypeRegistry()
        self.reg.register("process.dummy", DummyNode)

    def test_create_instance(self):
        inst = self.reg.create_instance("process.dummy", "node-1", {"key": "val"})
        assert inst is not None
        assert inst.node_id == "node-1"
        assert inst.config == {"key": "val"}

    def test_create_instance_short_name(self):
        inst = self.reg.create_instance("dummy", "node-2", {})
        assert inst is not None

    def test_create_instance_missing(self):
        inst = self.reg.create_instance("process.nonexistent", "node-3", {})
        assert inst is None


class TestNodeSchema:
    """Test to_schema() output."""

    def test_schema_has_required_fields(self):
        schema = DummyNode.to_schema()
        assert schema["type"] == "process.dummy"
        assert schema["category"] == "process"
        assert "label" in schema
        assert "description" in schema
        assert "inputs" in schema
        assert "outputs" in schema
        assert "config_schema" in schema

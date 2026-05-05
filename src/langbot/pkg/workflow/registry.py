"""Node type registry"""
from __future__ import annotations

from typing import Any, Optional

from .node import WorkflowNode, get_pending_registrations, clear_pending_registrations


class NodeTypeRegistry:
    """
    Central registry for all workflow node types.
    Supports both built-in and plugin-provided nodes.
    """
    
    _instance: Optional['NodeTypeRegistry'] = None
    
    def __init__(self):
        self._nodes: dict[str, type[WorkflowNode]] = {}
        self._categories: dict[str, list[str]] = {
            'trigger': [],
            'process': [],
            'control': [],
            'action': [],
            'integration': [],
            'misc': [],
        }
    
    @classmethod
    def instance(cls) -> 'NodeTypeRegistry':
        """Get singleton instance"""
        if cls._instance is None:
            cls._instance = cls()
        return cls._instance
    
    def register(self, node_type: str, node_class: type[WorkflowNode]):
        """
        Register a node type.
        
        Args:
            node_type: Unique type identifier
            node_class: WorkflowNode subclass
        """
        self._nodes[node_type] = node_class
        
        # Add to category
        category = getattr(node_class, 'category', 'misc')
        if category not in self._categories:
            self._categories[category] = []
        if node_type not in self._categories[category]:
            self._categories[category].append(node_type)
    
    def unregister(self, node_type: str):
        """Unregister a node type"""
        if node_type in self._nodes:
            node_class = self._nodes[node_type]
            category = getattr(node_class, 'category', 'misc')
            if category in self._categories and node_type in self._categories[category]:
                self._categories[category].remove(node_type)
            del self._nodes[node_type]
    
    def get(self, node_type: str) -> Optional[type[WorkflowNode]]:
        """Get node class by type. Supports both 'category.type_name' and short 'type_name' formats."""
        # First try exact match (category.type_name format)
        if node_type in self._nodes:
            return self._nodes[node_type]
        
        # Try short name format (e.g., 'dify_workflow' -> 'integration.dify_workflow')
        # Search through all registered nodes for a matching type_name
        for registered_type, node_class in self._nodes.items():
            if node_class.type_name == node_type:
                return node_class

        # Lazy-process pending registrations so execution paths that didn't
        # explicitly warm the registry can still resolve newly imported nodes.
        if get_pending_registrations():
            self.process_pending_registrations()

            if node_type in self._nodes:
                return self._nodes[node_type]

            for registered_type, node_class in self._nodes.items():
                if node_class.type_name == node_type:
                    return node_class
        
        return None
    
    def create_instance(self, node_type: str, node_id: str, config: dict[str, Any], ap: Optional['app.Application'] = None) -> Optional[WorkflowNode]:
        """Create a node instance. Supports both 'category.type_name' and short 'type_name' formats."""
        node_class = self.get(node_type)
        if node_class:
            return node_class(node_id, config, ap=ap)
        return None
    
    def list_all(self) -> list[dict[str, Any]]:
        """
        Get all registered node types as schema list.
        
        Returns:
            List of node schemas
        """
        return [
            node_class.to_schema()
            for node_class in self._nodes.values()
        ]
    
    def list_by_category(self, category: str) -> list[dict[str, Any]]:
        """
        Get node types by category.
        
        Args:
            category: Category name (trigger, process, control, action, integration, misc)
            
        Returns:
            List of node schemas in the category
        """
        if category not in self._categories:
            return []
        return [
            self._nodes[node_type].to_schema()
            for node_type in self._categories[category]
            if node_type in self._nodes
        ]
    
    def get_categories(self) -> dict[str, list[dict[str, Any]]]:
        """
        Get all nodes organized by category.
        
        Returns:
            Dictionary mapping category names to lists of node schemas
        """
        return {
            category: self.list_by_category(category)
            for category in self._categories.keys()
        }
    
    def has_type(self, node_type: str) -> bool:
        """Check if a node type is registered. Supports both formats."""
        return self.get(node_type) is not None
    
    def process_pending_registrations(self):
        """Process all pending node registrations from decorators"""
        for node_type, node_class in get_pending_registrations():
            # Use category.type_name format for consistency with frontend
            category = getattr(node_class, 'category', 'misc')
            full_type = f'{category}.{node_type}'
            self.register(full_type, node_class)
        clear_pending_registrations()
    
    def count(self) -> int:
        """Get total number of registered node types"""
        return len(self._nodes)
    
    def clear(self):
        """Clear all registrations (for testing)"""
        self._nodes.clear()
        for category in self._categories:
            self._categories[category] = []


# Convenience functions for module-level access
def register_node(node_type: str, node_class: type[WorkflowNode]):
    """Register a node type to the global registry"""
    NodeTypeRegistry.instance().register(node_type, node_class)


def get_node_class(node_type: str) -> Optional[type[WorkflowNode]]:
    """Get a node class from the global registry"""
    return NodeTypeRegistry.instance().get(node_type)


def list_node_types() -> list[dict[str, Any]]:
    """List all registered node types"""
    return NodeTypeRegistry.instance().list_all()

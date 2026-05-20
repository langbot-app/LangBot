"""Unit tests for utils funcschema.

Tests cover:
- get_func_schema() function
- Docstring parsing
- Parameter type extraction
- Required parameter detection

Note: Do NOT use 'from __future__ import annotations' because
       funcschema.py expects actual type objects, not string annotations.
"""
import pytest
from importlib import import_module


def get_funcschema_module():
    """Lazy import to avoid circular import issues."""
    return import_module('langbot.pkg.utils.funcschema')


class TestGetFuncSchema:
    """Tests for get_func_schema function."""

    def test_simple_function_schema(self):
        """Test schema generation for simple function."""
        funcschema = get_funcschema_module()

        def simple_func(name: str, count: int):
            """Simple function description.

            Args:
                name: The name parameter.
                count: The count parameter.
            """
            pass

        result = funcschema.get_func_schema(simple_func)

        assert result['description'] == 'Simple function description.'
        assert result['parameters']['type'] == 'object'
        assert 'name' in result['parameters']['properties']
        assert 'count' in result['parameters']['properties']
        assert result['parameters']['properties']['name']['type'] == 'string'
        assert result['parameters']['properties']['count']['type'] == 'integer'

    def test_parameter_type_mapping(self):
        """Test that Python types are mapped to JSON schema types."""
        funcschema = get_funcschema_module()

        def typed_func(a: str, b: int, c: float, d: bool, e: list, f: dict):
            """Typed function.

            Args:
                a: String param.
                b: Int param.
                c: Float param.
                d: Bool param.
                e: List param.
                f: Dict param.
            """
            pass

        result = funcschema.get_func_schema(typed_func)

        props = result['parameters']['properties']
        assert props['a']['type'] == 'string'
        assert props['b']['type'] == 'integer'
        assert props['c']['type'] == 'number'
        assert props['d']['type'] == 'boolean'
        assert props['e']['type'] == 'array'
        assert props['f']['type'] == 'object'

    def test_required_parameters_detection(self):
        """Test that required parameters are detected correctly."""
        funcschema = get_funcschema_module()

        def func_with_defaults(name: str, optional: str = 'default'):
            """Function with default.

            Args:
                name: Required param.
                optional: Optional param.
            """
            pass

        result = funcschema.get_func_schema(func_with_defaults)

        assert 'name' in result['parameters']['required']
        assert 'optional' not in result['parameters']['required']

    def test_self_and_query_excluded(self):
        """Test that self and query parameters are excluded."""
        funcschema = get_funcschema_module()

        def method_func(self, query, other: str):
            """Method function.

            Args:
                self: Self parameter.
                query: Query parameter.
                other: Other parameter.
            """
            pass

        result = funcschema.get_func_schema(method_func)

        props = result['parameters']['properties']
        assert 'self' not in props
        assert 'query' not in props
        assert 'other' in props

    def test_array_type_extraction(self):
        """Test that list[T] types extract element type."""
        funcschema = get_funcschema_module()

        def list_func(items: list[str], numbers: list[int]):
            """List function.

            Args:
                items: List of strings.
                numbers: List of integers.
            """
            pass

        result = funcschema.get_func_schema(list_func)

        props = result['parameters']['properties']
        assert props['items']['type'] == 'array'
        assert props['items']['items']['type'] == 'string'
        assert props['numbers']['type'] == 'array'
        assert props['numbers']['items']['type'] == 'integer'

    def test_function_without_docstring_raises(self):
        """Test that function without docstring raises exception."""
        funcschema = get_funcschema_module()

        def no_doc_func(a: str):
            pass

        with pytest.raises(Exception) as exc_info:
            funcschema.get_func_schema(no_doc_func)

        assert 'has no docstring' in str(exc_info.value)

    def test_description_extraction(self):
        """Test that description is extracted from first paragraph."""
        funcschema = get_funcschema_module()

        def desc_func(a: str):
            """This is the description.

            Args:
                a: Param a.
            """
            pass

        result = funcschema.get_func_schema(desc_func)

        assert result['description'] == 'This is the description.'

    def test_function_reference_stored(self):
        """Test that function reference is stored in schema."""
        funcschema = get_funcschema_module()

        def stored_func(a: str):
            """Stored function.

            Args:
                a: Param a.
            """
            pass

        result = funcschema.get_func_schema(stored_func)

        assert result['function'] is stored_func

    def test_description_from_args_doc(self):
        """Test that arg description is extracted from docstring."""
        funcschema = get_funcschema_module()

        def doc_func(param_name: str):
            """Function with documented param.

            Args:
                param_name: This is the param description.
            """
            pass

        result = funcschema.get_func_schema(doc_func)

        assert result['parameters']['properties']['param_name']['description'] == 'This is the param description.'

    def test_missing_parameter_doc_uses_empty_description(self):
        """Undocumented parameters should not break schema generation."""
        funcschema = get_funcschema_module()

        def sample_function(documented: str, undocumented: int):
            """Sample function.

            Args:
                documented(str): documented parameter description
            """
            pass

        result = funcschema.get_func_schema(sample_function)

        assert result['parameters']['properties']['documented']['description'] == 'documented parameter description'
        assert result['parameters']['properties']['undocumented']['description'] == ''

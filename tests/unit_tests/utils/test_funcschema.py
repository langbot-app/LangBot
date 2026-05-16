from langbot.pkg.utils.funcschema import get_func_schema


def test_get_func_schema_uses_empty_description_for_undocumented_parameter():
    def sample_function(documented: str, undocumented: int):
        """Sample function.

        Args:
            documented(str): documented parameter description
        """

    schema = get_func_schema(sample_function)

    assert schema['parameters']['properties']['documented']['description'] == 'documented parameter description'
    assert schema['parameters']['properties']['undocumented']['description'] == ''

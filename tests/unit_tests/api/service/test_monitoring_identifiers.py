"""Identifier normalization must not rely on SQLite's permissive codecs."""

import pytest

from langbot.pkg.api.http.service import monitoring


@pytest.mark.parametrize(
    ('value', 'expected'),
    [(None, None), ('', ''), ('00123', '00123'), ('  用户  ', '  用户  '), (123, '123'), (-123, '-123'), (0, '0')],
)
def test_normalize_user_id_preserves_opaque_strings(value, expected):
    assert monitoring._normalize_user_id(value) == expected


@pytest.mark.parametrize('value', [True, False, 1.5, b'123', ['123'], {'id': 123}])
def test_normalize_user_id_rejects_unsupported_types(value):
    with pytest.raises(TypeError, match='user_id must be a string, integer, or None'):
        monitoring._normalize_user_id(value)

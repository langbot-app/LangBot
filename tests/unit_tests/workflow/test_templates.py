import pytest
from jinja2 import TemplateError

from langbot.pkg.workflow.templates import references, render


def test_loop_scope_and_mapping_keys():
    text = '{% for row in upstream.items %}{{ row.name }}{% endfor %}'
    assert references(text) == ({'upstream'}, [('upstream', 'items')])
    assert render(text, {'upstream': {'items': [{'name': '甲'}, {'name': '乙'}]}}, {}) == '甲乙'
    assert render('{{ memory.user.absent.deep }}', {}, {}) == ''


def test_render_limits():
    with pytest.raises(TemplateError, match='limit'):
        render('{% for item in step.rows %}{% endfor %}', {'step': {'rows': list(range(10001))}}, {})
    with pytest.raises(TemplateError, match='limit'):
        render('{{ step.text }}', {'step': {'text': 'a' * 100001}}, {})

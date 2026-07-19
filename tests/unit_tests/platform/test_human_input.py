from langbot.pkg.platform.human_input import format_human_input_text


def test_format_human_input_text_renders_fields_actions_and_strips_placeholders():
    result = format_human_input_text(
        'Approval',
        'Review this request\n{{#$output.choice#}}',
        [{'id': 'approve', 'title': 'Approve'}],
        [
            {
                'output_variable_name': 'choice',
                'type': 'select',
                'option_source': {'value': ['Yes', 'No']},
            }
        ],
    )

    assert result.startswith('[Human Input Required] Approval')
    assert '{{#$output.choice#}}' not in result
    assert 'choice (select): 1. Yes, 2. No' in result
    assert 'action: <number or title>' in result
    assert '1. Approve' in result


def test_format_human_input_text_supports_plain_action_prompt():
    result = format_human_input_text('', '', [{'id': 'continue'}])

    assert result == (
        '[Human Input Required]\n\n'
        'Reply with the number or title to continue:\n'
        '  1. continue'
    )

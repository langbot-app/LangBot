import sys
import types


logger_module = types.ModuleType('langbot.pkg.platform.logger')
logger_module.EventLogger = object
sys.modules.setdefault('langbot.pkg.platform.logger', logger_module)

from langbot.libs.wecom_ai_bot_api.api import (  # noqa: E402
    build_button_interaction_payload,
    build_button_interaction_update_card,
    extract_template_card_action,
)


def test_extract_template_card_action_supports_nested_button_key():
    task_id, event_key, card_type = extract_template_card_action(
        {
            'taskId': 'task-1',
            'cardType': 'button_interaction',
            'button': {'key': 'approve'},
        }
    )

    assert task_id == 'task-1'
    assert event_key == 'approve'
    assert card_type == 'button_interaction'


def test_build_button_interaction_update_card_marks_clicked_button():
    card = build_button_interaction_update_card(
        {
            'node_title': 'Manual Review',
            'form_content': 'Please choose one action.',
            'actions': [
                {'id': 'approve', 'title': 'Approve', 'button_style': 'primary'},
                {'id': 'reject', 'title': 'Reject', 'button_style': 'danger'},
            ],
        },
        task_id='task-1',
        action_id='reject',
        source={'desc': 'LangBot'},
    )

    assert card['main_title'] == {'title': 'Manual Review'}
    assert card['sub_title_text'] == 'Please choose one action.'
    assert card['button_list'][0] == {'text': 'Approve', 'style': 2, 'key': 'approve'}
    assert card['button_list'][1] == {
        'text': '已选择：Reject',
        'style': 1,
        'key': 'reject',
        'replace_text': '已选择：Reject',
    }
    assert card['source'] == {'desc': 'LangBot'}


def test_build_button_interaction_payload_uses_preselected_button_styles_before_click():
    payload = build_button_interaction_payload(
        {
            'node_title': 'Manual Review',
            'actions': [
                {'id': 'approve', 'title': 'Approve', 'button_style': 'primary'},
                {'id': 'reject', 'title': 'Reject', 'button_style': 'danger'},
            ],
        },
        task_id='task-1',
    )

    assert payload['template_card']['button_list'] == [
        {'text': 'Approve', 'style': 2, 'key': 'approve'},
        {'text': 'Reject', 'style': 2, 'key': 'reject'},
    ]

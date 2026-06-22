"""Generate the DingTalk human-input card template JSON.

The output is wrapped in the {editorData, widgetInfo, type, mode} envelope
the DingTalk card builder expects on import. editorData is itself a JSON
string (NOT a nested object), matching real exports from the builder.

Run from the repo root:  python scripts/build_dingtalk_card_template.py
"""

from __future__ import annotations

import json
from pathlib import Path

OUTPUT = Path('src/langbot/templates/dingtalk_human_input_card.json')


def markdown_block(node_id, variable='content'):
    """A MarkdownBlock whose content is bound to a global variable.

    Critical: `content.varType: "markdown"` must be set, otherwise DingTalk
    silently fails to render the bound variable (the card body stays blank
    even though the variable is supplied via cardParamMap). The working
    reference template in I:\\下载\\dingtalk_1782055283543.json confirms
    this — its MarkdownBlock has the same varType marker.

    isStreaming is left `false` because the adapter writes the variable via
    `update_card_data` (the full-card PUT endpoint), not the streaming
    `card/streaming` endpoint. Setting `isStreaming: true` here conflicts
    with that path and can suppress the rendered body.
    """
    return {
        'componentName': 'MarkdownBlock',
        'id': node_id,
        'props': {
            'mdVer': 0,
            'icon': {'type': 'icon', 'icon': '', 'iconType': 'emoji'},
            'content': {
                'variable': variable,
                'variableType': 'global',
                'type': 'variableValue',
                'varType': 'markdown',
            },
            'visible': {
                'type': 'dynamicVisible',
                'value': True,
                'valueType': 'fixed',
                'condition': {'op': 'and', 'conditions': []},
            },
            'isStreaming': False,
            'enableLinkStatPoint': False,
            'linkStatPoint': {
                'type': 'dynamicString',
                'content': 'Page_InteractiveCard__Click_markdownOpenlink',
                'i18n': False,
            },
            'linkStatPointParams': [],
            'marginTop': 6,
            'marginBottom': 6,
            'marginLeft': 12,
            'marginRight': 12,
        },
        'title': 'AI 流式富文本',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
    }


def text_block(
    node_id,
    text,
    *,
    bold=False,
    gravity='left',
    font_size=14,
    line_height=22,
    max_lines=20,
    ml=12,
    mr=12,
    mt=4,
    mb=4,
    color_token='common_level1_base_color',
    style_token='common_body_text_style',
):
    return {
        'componentName': 'BaseText',
        'id': node_id,
        'props': {
            'text': {'i18n': False, 'type': 'dynamicString', 'content': text},
            'hoverText': {'type': 'dynamicString', 'content': '', 'i18n': False},
            'iconType': 'iconCode',
            'iconFont': {'type': 'icon', 'icon': '', 'iconType': 'ddIcon'},
            'icon': {
                'type': 'dynamicLink',
                'value': '',
                'valueType': 'fixed',
                'variable': '',
                'variableType': 'global',
            },
            'darkIcon': {
                'type': 'dynamicLink',
                'value': '',
                'valueType': 'fixed',
                'variable': '',
                'variableType': 'global',
            },
            'autoWidth': False,
            'maxWidth': {
                'type': 'dynamicNumber',
                'valueType': 'fixed',
                'value': 0,
                'variable': '',
                'variableType': 'global',
            },
            'fixedWidth': {
                'type': 'dynamicNumber',
                'valueType': 'fixed',
                'value': 0,
                'variable': '',
                'variableType': 'global',
            },
            'marginLeft': ml,
            'marginRight': mr,
            'marginTop': mt,
            'marginBottom': mb,
            'fontColorType': 'Standard',
            'enableHighlight': False,
            'maxLine': {
                'type': 'dynamicNumber',
                'valueType': 'fixed',
                'value': max_lines,
                'variable': '',
                'variableType': 'global',
            },
            'color': {
                'type': 'dynamicColor',
                'valueType': 'fixed',
                'value': color_token,
                'variable': '',
                'variableType': 'global',
            },
            'customLightColor': {
                'type': 'dynamicColor',
                'valueType': 'fixed',
                'value': '#35404b',
                'variable': '',
                'variableType': 'global',
            },
            'customDarkColor': {
                'type': 'dynamicColor',
                'valueType': 'fixed',
                'value': '#f6f6f6',
                'variable': '',
                'variableType': 'global',
            },
            'gravity': gravity,
            'fontSizeType': 'Standard',
            'styleType': 'custom',
            'styleToken': style_token,
            'size': 'middle',
            'customFontSize': font_size,
            'customFontLineHeight': line_height,
            'bold': bold,
            'italic': False,
            'strikeThrough': False,
            'lineHeight': 'normal',
            'visible': {
                'type': 'dynamicVisible',
                'value': True,
                'valueType': 'fixed',
                'condition': {'op': 'and', 'conditions': []},
            },
            'autoMaxWidth': False,
            'innerOffset': 0,
            'enableIcon': False,
            'widthMode': 'match_parent',
            'margin': -2,
        },
        'title': '基础文本',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
    }


def button_group(node_id):
    return {
        'componentName': 'ButtonGroup',
        'id': node_id,
        'props': {
            'dynamicButtons': {'type': 'variableValue', 'variableType': 'global', 'variable': 'btns'},
            'marginLeft': 12,
            'marginRight': 12,
            'marginTop': 6,
            'marginBottom': 12,
            'visible': {
                'type': 'dynamicVisible',
                'value': True,
                'valueType': 'fixed',
                'condition': {'op': 'and', 'conditions': []},
            },
            'responsiveLayoutWidth': 350,
            'buttonsSource': 'variable',
            'fixedButtonIds': [],
            'fixedButtons': [],
            'enableResponsiveLayout': False,
            'matchContent': False,
            'buttonSpacing': 8,
            'margin': -2,
            'innerOffset': 0,
        },
        'title': '按钮组',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
    }


def avatar(node_id, *, name='LangBot', image_variable='bot_avatar'):
    """Avatar component in `userInfo` mode — renders the bot's avatar
    image and nickname as a header row above the response content.
    Mirrors the layout from `I:\\下载\\dingtalk_1782120006374.json` where
    Avatar sits at the top of the done-state AICardContent.

    `imageUrl` is bound to a global variable (default `bot_avatar`) so
    the adapter can populate it at runtime with a DingTalk media id
    (``@xxx``) obtained from the /media/upload endpoint. DingTalk's
    Avatar.imageUrl resolver rejects external URLs — it only accepts
    DingTalk-hosted media ids, so this binding is the only path to
    a custom avatar.
    """
    return {
        'componentName': 'Avatar',
        'id': node_id,
        'props': {
            'imageUrl': {
                'value': '',
                'valueType': 'variable',
                'type': 'dynamicImage',
                'variable': image_variable,
                'variableType': 'global',
            },
            'name': {'i18n': False, 'type': 'dynamicString', 'content': name},
            'sizeType': 'Standard',
            'size': 'extraSmall',
            'customSize': 48,
            'marginLeft': 12,
            'marginRight': 12,
            'marginTop': 6,
            'marginBottom': 6,
            'visible': {
                'type': 'dynamicVisible',
                'value': True,
                'valueType': 'fixed',
                'condition': {'op': 'and', 'conditions': []},
            },
            'mode': 'userInfo',
            'margin': -2,
            'innerOffset': 0,
        },
        'title': '头像',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
    }


def build_editor_data():
    component_names = [
        'AIPending',
        'AICardStatusContainer',
        'BaseText',
        'AICardContent',
        'AICardContainer',
        'ButtonGroup',
        'MarkdownBlock',
        'Avatar',
    ]
    components_map = [
        {
            'package': '@ali/dxComponent',
            'version': '1.0.0',
            'exportName': n,
            'main': './src/index.tsx',
            'destructuring': False,
            'subName': '',
            'componentName': n,
        }
        for n in component_names
    ]

    pending_state = {
        'componentName': 'AICardStatusContainer',
        'id': 'node_status_pending',
        'props': {
            'status': 1,
            'marginLeft': 0,
            'marginRight': 0,
            'marginTop': 0,
            'marginBottom': 0,
            'enableExtend': False,
            'autoFoldConfig': {
                'needFold': True,
                'heightLimit': 480,
                'foldStatusLocalDataKey': '_cardFoldStatusLocalDataKey',
            },
            'innerOffset': 0,
            'enableCollapse': False,
            'margin': -2,
        },
        'title': '处理中状态',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
        'children': [
            {
                'componentName': 'AIPending',
                'id': 'node_pending_inner',
                'props': {
                    'marginLeft': 0,
                    'marginRight': 0,
                    'marginTop': 0,
                    'marginBottom': 0,
                    'pendingTip': {'type': 'dynamicString', 'content': '处理中...', 'i18n': False},
                    'style': 'embed',
                    'hideIcon': False,
                },
                'hidden': False,
                'title': '',
                'isLocked': False,
                'condition': True,
                'conditionGroup': '',
            }
        ],
    }

    done_state = {
        'componentName': 'AICardStatusContainer',
        'id': 'node_status_done',
        'props': {
            'status': 3,
            'marginLeft': 0,
            'marginRight': 0,
            'marginTop': 0,
            'marginBottom': 0,
            'enableExtend': False,
            'autoFoldConfig': {
                'needFold': True,
                'heightLimit': 480,
                'foldStatusLocalDataKey': '_cardFoldStatusLocalDataKey',
            },
            'innerOffset': 0,
            'enableCollapse': False,
            'margin': -2,
        },
        'title': '完成状态',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
        'children': [
            {
                'componentName': 'AICardContent',
                'id': 'node_done_content',
                'props': {
                    'marginLeft': 0,
                    'marginRight': 0,
                    'marginTop': 0,
                    'marginBottom': 0,
                    'visible': {
                        'type': 'dynamicVisible',
                        'value': True,
                        'valueType': 'fixed',
                        'condition': {'op': 'and', 'conditions': []},
                    },
                    'innerOffset': 0,
                    'disabledWhileForward': False,
                    'statPoint': {'type': 'dynamicString', 'content': '', 'i18n': False},
                    'statPointParams': [
                        {'type': 'fixed', 'variable': '', 'value': '', 'name': '', 'variableType': 'global', 'id': '1'}
                    ],
                    'margin': -2,
                    'transformToEventChain': False,
                    'enableStatPoint': False,
                },
                'hidden': False,
                'title': '',
                'isLocked': False,
                'condition': True,
                'conditionGroup': '',
                'children': [
                    avatar('node_avatar', name='LangBot'),
                    markdown_block('node_text_content', variable='content'),
                    button_group('node_btn_group'),
                ],
            }
        ],
    }

    failed_state = {
        'componentName': 'AICardStatusContainer',
        'id': 'node_status_failed',
        'props': {
            'status': 5,
            'marginLeft': 0,
            'marginRight': 0,
            'marginTop': 0,
            'marginBottom': 0,
            'enableExtend': False,
            'autoFoldConfig': {
                'needFold': True,
                'heightLimit': 480,
                'foldStatusLocalDataKey': '_cardFoldStatusLocalDataKey',
            },
            'innerOffset': 0,
            'enableCollapse': False,
            'margin': -2,
        },
        'title': '失败状态',
        'hidden': False,
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
        'children': [
            {
                'componentName': 'AICardContent',
                'id': 'node_failed_content',
                'props': {
                    'visible': {
                        'type': 'dynamicVisible',
                        'value': True,
                        'valueType': 'fixed',
                        'condition': {'op': 'and', 'conditions': []},
                    },
                    'marginLeft': 0,
                    'marginRight': 0,
                    'marginTop': 0,
                    'marginBottom': 0,
                    'innerOffset': 0,
                    'disabledWhileForward': False,
                    'statPoint': {'type': 'dynamicString', 'content': '', 'i18n': False},
                    'statPointParams': [
                        {'type': 'fixed', 'variable': '', 'value': '', 'name': '', 'variableType': 'global', 'id': '1'}
                    ],
                    'margin': -2,
                    'transformToEventChain': False,
                    'enableStatPoint': False,
                },
                'hidden': False,
                'title': '',
                'isLocked': False,
                'condition': True,
                'conditionGroup': '',
                'children': [
                    text_block(
                        'node_failed_text',
                        '操作失败，请稍后重试。',
                        gravity='center',
                        mt=10,
                        mb=10,
                        ml=10,
                        mr=10,
                        max_lines=2,
                        font_size=15,
                    )
                ],
            }
        ],
    }

    # Empty containers for flowStatus=2 (writing) and flowStatus=4 (doing).
    # AICardContainer expects placeholders to exist for every enabled state;
    # without them, the renderer can refuse to advance to flowStatus=3 (done)
    # and the card body stays empty. They render nothing visible because
    # they have no content children, but their presence satisfies the
    # state-machine validation.
    def _empty_status_container(node_id, status):
        return {
            'componentName': 'AICardStatusContainer',
            'id': node_id,
            'props': {
                'status': status,
                'marginLeft': 0,
                'marginRight': 0,
                'marginTop': 0,
                'marginBottom': 0,
                'enableExtend': False,
                'autoFoldConfig': {
                    'needFold': True,
                    'heightLimit': 480,
                    'foldStatusLocalDataKey': '_cardFoldStatusLocalDataKey',
                },
                'innerOffset': 0,
                'enableCollapse': False,
                'margin': -2,
            },
            'title': f'状态{status}占位',
            'hidden': False,
            'isLocked': False,
            'condition': True,
            'conditionGroup': '',
            'children': [
                {
                    'componentName': 'AICardContent',
                    'id': f'{node_id}_content',
                    'props': {
                        'marginLeft': 0,
                        'marginRight': 0,
                        'marginTop': 0,
                        'marginBottom': 0,
                        'visible': {
                            'type': 'dynamicVisible',
                            'value': True,
                            'valueType': 'fixed',
                            'condition': {'op': 'and', 'conditions': []},
                        },
                        'innerOffset': 0,
                        'disabledWhileForward': False,
                        'statPoint': {'type': 'dynamicString', 'content': '', 'i18n': False},
                        'statPointParams': [
                            {
                                'type': 'fixed',
                                'variable': '',
                                'value': '',
                                'name': '',
                                'variableType': 'global',
                                'id': '1',
                            }
                        ],
                        'margin': -2,
                        'transformToEventChain': False,
                        'enableStatPoint': False,
                    },
                    'hidden': False,
                    'title': '',
                    'isLocked': False,
                    'condition': True,
                    'conditionGroup': '',
                    'children': [],
                }
            ],
        }

    writing_state = _empty_status_container('node_status_writing', 2)
    doing_state = _empty_status_container('node_status_doing', 4)

    root = {
        'componentName': 'AICardContainer',
        'id': 'node_root',
        'props': {
            'marginLeft': 0,
            'marginRight': 0,
            'marginTop': 0,
            'marginBottom': 0,
            'enablePending': True,
            # writing/doing must be enabled so AICardContainer recognises
            # flowStatus transitions through 2/4 — without this, the
            # working reference template (I:\\下载\\dingtalk_1782055283543.json)
            # never reaches the done state and the body stays empty.
            'enableWriting': True,
            'enableDoing': True,
            'enableFailed': True,
            'summaryContent': {'type': 'variableValue', 'variableType': 'global', 'variable': ''},
            'enableTitle': False,
            'flowStatusVar': {'type': 'variableValue', 'variableType': 'global', 'variable': 'flowStatus'},
            'operationPenalType': 'custom',
            'enableFlowAbort': True,
            'innerOffset': 0,
            'enableGradientBorder': True,
            'cardSizeMode': 'adaptive',
            'cardSizeHeightMode': 'adaptive',
            'cardSizeWidthMode': 'adaptive',
            'cardSizeHeight': {
                'type': 'dynamicNumber',
                'valueType': 'fixed',
                'value': 226,
                'variable': '',
                'variableType': 'global',
            },
            'hasBackground': False,
            'backgroundType': 'Standard',
            'standardBackgroundColor': 'gray',
            'backgroundColor': '#F6F6F6',
            'darkModeBackgroundColor': '#3C3C3C',
            'enableEngineUpgrade': False,
            'enableExposeStatPoint': False,
            'enableDebugTool': False,
        },
        'hidden': False,
        'title': '',
        'isLocked': False,
        'condition': True,
        'conditionGroup': '',
        'children': [pending_state, writing_state, doing_state, done_state, failed_state],
    }

    btns_var = {
        'name': 'btns',
        'private': False,
        'type': 'buttonGroup',
        'id': 'btns',
        'description': '动态按钮列表（Dify actions）',
        'editorVarType': 'variables',
        'disabled': False,
        'schema': [
            {
                'id': 'btns.text',
                'type': 'string',
                'name': 'text',
                'private': False,
                'editorVarType': 'variables',
                'disabled': True,
                'description': '按钮文案',
            },
            {
                'id': 'btns.color',
                'type': 'string',
                'name': 'color',
                'private': False,
                'editorVarType': 'variables',
                'disabled': True,
                'description': '按钮颜色',
            },
            {
                'id': 'btns.status',
                'type': 'string',
                'name': 'status',
                'private': False,
                'editorVarType': 'variables',
                'disabled': True,
                'description': '按钮状态',
            },
            {
                'id': 'btns.event',
                'type': 'dynamicEvent',
                'name': 'event',
                'private': False,
                'editorVarType': 'variables',
                'disabled': True,
                'description': '按钮点击事件',
                'schema': [
                    {
                        'id': 'btns.type',
                        'type': 'string',
                        'name': 'type',
                        'private': False,
                        'editorVarType': 'variables',
                        'disabled': True,
                        'description': '事件类型：openLink / sendCardRequest',
                    },
                    {
                        'id': 'btns.params',
                        'type': 'object',
                        'name': 'params',
                        'private': False,
                        'editorVarType': 'variables',
                        'disabled': True,
                        'description': '事件参数',
                        'schema': [
                            {
                                'id': 'btns.url',
                                'type': 'string',
                                'name': 'url',
                                'private': False,
                                'editorVarType': 'variables',
                                'disabled': True,
                                'description': '点击跳转链接（type=openLink）',
                            },
                            {
                                'id': 'btns.actionId',
                                'type': 'string',
                                'name': 'actionId',
                                'private': False,
                                'editorVarType': 'variables',
                                'disabled': True,
                                'description': '回传请求 id（type=sendCardRequest）',
                            },
                            {
                                'id': 'btns.params',
                                'type': 'object',
                                'name': 'params',
                                'private': False,
                                'editorVarType': 'variables',
                                'disabled': True,
                                'description': '回传请求参数（type=sendCardRequest）',
                            },
                        ],
                    },
                ],
            },
        ],
    }

    return {
        'schemaVersion': '3.0.0',
        'schema': {
            # Match the working reference template — leaving config null lets
            # DingTalk pick defaults. Explicit `streaming_mode: true` would
            # make the renderer wait for chunks on the streaming endpoint
            # (PUT /v1.0/card/streaming), which our adapter does NOT use —
            # it pushes content via update_card_data, so streaming_mode=true
            # leaves the body empty.
            'config': None,
            'componentsMap': components_map,
            'componentsTree': [root],
            'i18n': {},
            'version': '1.0.0',
        },
        'mockData': {
            'cardData': {
                'flowStatus': 3,
                'content': '请审核以下报销申请：\n\n- 申请人：张三\n- 金额：¥1,200\n- 类别：差旅',
                'btns': [
                    {
                        'text': '通过',
                        'color': 'blue',
                        'status': 'normal',
                        'event': {
                            'type': 'sendCardRequest',
                            'params': {'actionId': 'approve', 'params': {'action_id': 'approve'}},
                        },
                    },
                    {
                        'text': '驳回',
                        'color': 'gray',
                        'status': 'normal',
                        'event': {
                            'type': 'sendCardRequest',
                            'params': {'actionId': 'reject', 'params': {'action_id': 'reject'}},
                        },
                    },
                    {
                        'text': '补充资料',
                        'color': 'gray',
                        'status': 'normal',
                        'event': {
                            'type': 'sendCardRequest',
                            'params': {'actionId': 'more_info', 'params': {'action_id': 'more_info'}},
                        },
                    },
                ],
            },
            'cardPrivateData': {},
            'localData': {'flowStatus': '', '_cardFoldStatusLocalDataKey': ''},
            'richTextData': {},
        },
        'renderContext': {'regenerateEnabled': '1', 'regenerateIndex': '2', 'regenerateTotal': '5'},
        'editVersion': 0,
        'customWidgetInfo': '',
        'useCustomWidgetInfo': False,
        'variableList': [
            {
                'id': 'content',
                'type': 'markdown',
                'name': 'content',
                'description': '人工输入提示词（Dify form_content 含可选 node_title 前缀）',
                'private': False,
                'editorVarType': 'variables',
                'disabled': False,
            },
            {
                'id': 'flowStatus',
                'type': 'string',
                'name': 'flowStatus',
                'description': 'AI卡片状态：pending(1)、writing(2)、done(3)、failed(5)',
                'private': False,
                'editorVarType': 'variables',
                'disabled': True,
                'visible': False,
            },
            {
                'id': 'bot_avatar',
                'type': 'string',
                'name': 'bot_avatar',
                'description': '机器人头像 DingTalk 媒体 ID（@xxx 格式，启动时由 /media/upload 拿到）',
                'private': False,
                'editorVarType': 'variables',
                'disabled': False,
            },
            btns_var,
        ],
        'formList': [],
        'customContextList': [],
        'expList': [],
        'localList': [],
        'hsfList': [],
        'lwpList': [],
        'pageData': {},
        'extension': {
            'extendType': 'AI',
            # All 5 statuses listed — must mirror the enableX flags on
            # AICardContainer. The working reference template's extension
            # includes 2 (writing) and 4 (doing); omitting them while
            # enableWriting/enableDoing are true makes the renderer reject
            # transitions and leaves the card body empty.
            'aiStatusList': [3, 1, 5, 2, 4],
            'fileTypeList': [],
        },
    }


def main():
    editor_data = build_editor_data()
    wrapper = {
        'editorData': json.dumps(editor_data, ensure_ascii=False, separators=(',', ':')),
        'widgetInfo': '',
        'type': 'im',
        'mode': 'card',
    }
    OUTPUT.write_text(json.dumps(wrapper, ensure_ascii=False, indent=2), encoding='utf-8')
    print(f'wrote {OUTPUT}')


if __name__ == '__main__':
    main()

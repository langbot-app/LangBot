from __future__ import annotations

import copy

import pytest

from langbot.pkg.api.http.service.secrets import (
    contains_secret_placeholder,
    redact_secrets,
    restore_secret_placeholders,
)


RAW_CONFIG = {
    'apiKey': 'api-secret',
    'dify_apikey': 'dify-secret',
    'base_url': (
        'https://service-user:service-password@api.invalid/v1'
        '?api_key=query-secret&region=sg&X-Amz-Signature=signed-secret'
    ),
    'nested': {
        'headers': {
            'Authorization': 'Bearer nested-secret',
            'X-API-Key': 'header-secret',
            'Accept': 'application/json',
        },
        'webhook-url': 'https://hooks.invalid/path?token=secret',
        'public_key': 'public-material',
        'tokenizer': 'not-a-secret',
    },
    'credentials': {'username': 'service-user', 'password': 'service-password'},
    'secret_list': ['first-secret', {'value': 'second-secret'}],
    'empty_secret': '',
    'enabled': True,
}


def test_recursive_redaction_is_shape_preserving_and_does_not_mutate_source():
    source = copy.deepcopy(RAW_CONFIG)

    redacted = redact_secrets(source)

    assert redacted['apiKey'] == '***'
    assert redacted['dify_apikey'] == '***'
    assert redacted['base_url'] == ('https://***@api.invalid/v1?api_key=***&region=sg&X-Amz-Signature=***')
    assert redacted['nested']['headers'] == {
        'Authorization': '***',
        'X-API-Key': '***',
        'Accept': 'application/json',
    }
    assert redacted['nested']['webhook-url'] == '***'
    assert redacted['nested']['public_key'] == 'public-material'
    assert redacted['nested']['tokenizer'] == 'not-a-secret'
    assert redacted['credentials'] == {'username': '***', 'password': '***'}
    assert redacted['secret_list'] == ['***', {'value': '***'}]
    assert redacted['empty_secret'] == ''
    assert redacted['enabled'] is True
    assert source == RAW_CONFIG


def test_masked_roundtrip_preserves_existing_secrets_and_accepts_replace_and_clear():
    submitted = redact_secrets(RAW_CONFIG)
    submitted['enabled'] = False
    submitted['apiKey'] = 'replacement-secret'
    submitted['nested']['headers']['X-API-Key'] = ''

    restored = restore_secret_placeholders(submitted, RAW_CONFIG)

    assert restored['apiKey'] == 'replacement-secret'
    assert restored['dify_apikey'] == 'dify-secret'
    assert restored['nested']['headers']['Authorization'] == 'Bearer nested-secret'
    assert restored['nested']['headers']['X-API-Key'] == ''
    assert restored['nested']['webhook-url'] == RAW_CONFIG['nested']['webhook-url']
    assert restored['base_url'] == RAW_CONFIG['base_url']
    assert restored['enabled'] is False
    assert RAW_CONFIG['apiKey'] == 'api-secret'


def test_new_or_extra_masked_secret_fails_closed():
    assert contains_secret_placeholder({'headers': {'Authorization': '***'}})
    assert contains_secret_placeholder({'base_url': 'https://***@api.invalid?token=***'})
    with pytest.raises(ValueError, match='no existing value'):
        restore_secret_placeholders({'api_key': '***'})
    with pytest.raises(ValueError, match='no existing value'):
        restore_secret_placeholders(
            {'api_keys': ['***', '***']},
            {'api_keys': ['existing']},
        )

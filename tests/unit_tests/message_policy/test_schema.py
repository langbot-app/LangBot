"""Message policy shape and the legacy config conversion."""

from __future__ import annotations

import copy

import pytest

from langbot.pkg.message_policy import schema

LEGACY = {
    'trigger': {
        'group-respond-rules': {'at': True, 'prefix': ['ai'], 'regexp': [], 'random': 0.0},
        'access-control': {'mode': 'blacklist', 'blacklist': ['person_1'], 'whitelist': []},
        'ignore-rules': {'prefix': ['#'], 'regexp': []},
        'message-aggregation': {'enabled': True, 'delay': 2},
        'misc': {'combine-quote-message': True},
    },
    'safety': {
        'content-filter': {'scope': 'all', 'check-sensitive-words': True},
        'rate-limit': {'window-length': 60, 'limitation': 5, 'strategy': 'wait'},
    },
    'ai': {'runner': {'id': 'plugin:a/b/default', 'expire-time': 0}, 'runner_config': {}},
    'speech': {'speech-recognition': {'enable': False}},
    'output': {
        'long-text-processing': {'threshold': 300, 'strategy': 'forward', 'font-path': ''},
        'force-delay': {'min': 1, 'max': 2},
        'misc': {
            'exception-handling': 'show-error',
            'failure-hint': 'oops',
            'rate-limit-hint': 'slow down',
            'at-sender': True,
            'quote-origin': False,
            'track-function-calls': True,
            'remove-think': True,
            'tool-call-hint': 'calling {tools}',
        },
    },
}


def test_split_moves_trigger_safety_and_general_output_only():
    source = copy.deepcopy(LEGACY)

    messaging, policy = schema.split_legacy_config(source)

    assert source == LEGACY, 'the conversion must not mutate its input'
    assert messaging == {
        'ai': LEGACY['ai'],
        'speech': LEGACY['speech'],
        'output': {'misc': {'track-function-calls': True, 'remove-think': True, 'tool-call-hint': 'calling {tools}'}},
    }
    assert policy['trigger']['access-control'] == LEGACY['trigger']['access-control']
    assert policy['safety']['content-filter'] == LEGACY['safety']['content-filter']
    assert policy['output'] == {
        'long-text-processing': LEGACY['output']['long-text-processing'],
        'force-delay': LEGACY['output']['force-delay'],
        'misc': {
            'exception-handling': 'show-error',
            'failure-hint': 'oops',
            'rate-limit-hint': 'slow down',
            'at-sender': True,
            'quote-origin': False,
        },
    }


def test_split_states_that_formerly_unconditional_blocks_are_on():
    _, policy = schema.split_legacy_config(LEGACY)

    assert policy['trigger']['group-respond-rules'] == {**LEGACY['trigger']['group-respond-rules'], 'enabled': True}
    assert policy['safety']['rate-limit'] == {**LEGACY['safety']['rate-limit'], 'enabled': True}


def test_converted_override_over_a_neutral_bot_reproduces_the_legacy_settings():
    _, policy = schema.split_legacy_config(LEGACY)

    effective = schema.resolve_policy(schema.neutral_policy(), policy)

    for section in ('trigger', 'safety'):
        for block, value in LEGACY[section].items():
            assert {key: effective[section][block][key] for key in value} == value
    for key in ('exception-handling', 'failure-hint', 'rate-limit-hint', 'at-sender', 'quote-origin'):
        assert effective['output']['misc'][key] == LEGACY['output']['misc'][key]
    assert effective['trigger']['group-respond-rules']['enabled'] is True
    assert effective['safety']['rate-limit']['enabled'] is True


def test_split_is_idempotent_on_a_converted_config():
    messaging, _ = schema.split_legacy_config(LEGACY)

    again, policy = schema.split_legacy_config(messaging)

    assert again == messaging
    assert policy == {}


@pytest.mark.parametrize('config', [None, [], 'text', {}, {'output': 'broken'}, {'output': {'misc': 'broken'}}])
def test_split_tolerates_malformed_configs(config):
    messaging, policy = schema.split_legacy_config(config)

    assert isinstance(messaging, dict)
    assert policy == {}


def test_extract_and_restore_round_trip_exactly_including_unknown_leftovers():
    source = copy.deepcopy(LEGACY)
    source['trigger']['legacy-leftover'] = {'x': 1}
    source['output']['unknown-block'] = {'y': 2}

    remaining, moved = schema.extract_legacy_policy(source)

    assert 'enabled' not in moved['trigger']['group-respond-rules'], 'the backup is verbatim'
    assert remaining['output']['unknown-block'] == {'y': 2}
    assert schema.restore_legacy_config(remaining, moved) == source


def test_overlay_exposes_the_policy_under_the_legacy_keys_without_touching_ai_output():
    messaging, override = schema.split_legacy_config(LEGACY)
    policy = schema.resolve_policy(None, override)

    seen = schema.overlay_policy(messaging, policy)

    assert seen['ai'] is messaging['ai']
    assert seen['trigger']['group-respond-rules']['prefix'] == ['ai']
    assert seen['safety']['rate-limit']['limitation'] == 5
    assert seen['output']['long-text-processing']['threshold'] == 300
    assert seen['output']['misc']['track-function-calls'] is True
    assert seen['output']['misc']['at-sender'] is True
    assert 'trigger' not in messaging, 'the stored config is left alone'


def test_overlay_policy_wins_over_stale_legacy_keys_left_in_a_config():
    stale = {'trigger': {'access-control': {'mode': 'whitelist', 'whitelist': [], 'blacklist': []}}}

    seen = schema.overlay_policy(stale, schema.neutral_policy())

    assert seen['trigger']['access-control']['mode'] == 'blacklist'


def test_neutral_policy_admits_everything_and_changes_nothing():
    neutral = schema.neutral_policy()

    assert neutral['trigger']['group-respond-rules']['enabled'] is False
    assert neutral['trigger']['access-control'] == {'mode': 'blacklist', 'blacklist': [], 'whitelist': []}
    assert neutral['trigger']['message-aggregation']['enabled'] is False
    assert neutral['safety']['content-filter']['check-sensitive-words'] is False
    assert neutral['safety']['rate-limit']['enabled'] is False
    assert neutral['output']['long-text-processing']['strategy'] == 'none'
    assert neutral['output']['force-delay'] == {'min': 0, 'max': 0}
    assert neutral['output']['misc']['at-sender'] is False
    assert neutral['output']['misc']['quote-origin'] is False
    neutral['trigger']['access-control']['blacklist'].append('x')
    assert schema.neutral_policy()['trigger']['access-control']['blacklist'] == []


def test_default_policy_keeps_the_defaults_new_messaging_processors_used_to_get():
    default = schema.default_policy()

    assert default['trigger']['group-respond-rules'] == {
        'enabled': True,
        'at': True,
        'prefix': ['ai'],
        'regexp': [],
        'random': 0.0,
    }
    assert default['trigger']['misc']['combine-quote-message'] is True
    assert default['safety']['content-filter'] == {'scope': 'all', 'check-sensitive-words': True}
    assert default['safety']['rate-limit'] == {
        'enabled': True,
        'window-length': 60,
        'limitation': 60,
        'strategy': 'drop',
    }
    assert default['output']['long-text-processing'] == {'threshold': 1000, 'strategy': 'none', 'font-path': ''}
    assert default['output']['misc']['at-sender'] is True
    assert default['output']['misc']['quote-origin'] is True
    assert default['output']['misc']['exception-handling'] == 'show-hint'
    # Complete: every key of the schema is present.
    for section, blocks in schema.POLICY_SCHEMA.items():
        for block, keys in blocks.items():
            assert set(default[section][block]) == set(keys)


def test_route_override_replaces_single_keys_and_whole_lists():
    bot = schema.default_policy()
    override = {'trigger': {'group-respond-rules': {'prefix': ['bot']}}, 'output': {'misc': {'at-sender': False}}}

    effective = schema.resolve_policy(bot, override)

    assert effective['trigger']['group-respond-rules']['prefix'] == ['bot']
    assert effective['trigger']['group-respond-rules']['at'] is True
    assert effective['output']['misc']['at-sender'] is False
    assert effective['output']['misc']['quote-origin'] is True
    assert bot['trigger']['group-respond-rules']['prefix'] == ['ai']


def test_policy_to_legacy_expresses_switched_off_blocks_in_legacy_terms():
    legacy = schema.policy_to_legacy(schema.neutral_policy())

    rules = legacy['trigger']['group-respond-rules']
    assert 'enabled' not in rules and rules['random'] == 1.0
    rate_limit = legacy['safety']['rate-limit']
    assert 'enabled' not in rate_limit and rate_limit['limitation'] >= 2**31 - 1

    enabled = schema.policy_to_legacy(schema.default_policy())
    assert enabled['trigger']['group-respond-rules']['random'] == 0.0
    assert enabled['safety']['rate-limit']['limitation'] == 60


def test_validate_accepts_partial_policies_and_coerces_form_values():
    cleaned = schema.validate_policy(
        {
            'trigger': {'group-respond-rules': {'at': 'true', 'random': '0.5'}},
            'safety': {'rate-limit': {'window-length': '30', 'limitation': 3.0}},
        }
    )

    assert cleaned == {
        'trigger': {'group-respond-rules': {'at': True, 'random': 0.5}},
        'safety': {'rate-limit': {'window-length': 30, 'limitation': 3}},
    }
    assert schema.validate_policy(None) == {}
    assert schema.validate_policy(schema.default_policy()) == schema.default_policy()


@pytest.mark.parametrize(
    ('policy', 'message'),
    [
        ([], 'message_policy must be an object'),
        ({'ai': {}}, 'message_policy.ai is not a message policy section'),
        ({'trigger': []}, 'message_policy.trigger must be an object'),
        ({'trigger': {'nope': {}}}, 'message_policy.trigger.nope is not a message policy setting'),
        ({'output': {'misc': {'remove-think': True}}}, 'message_policy.output.misc.remove-think is not'),
        ({'trigger': {'access-control': {'mode': 'greylist'}}}, 'mode must be one of blacklist, whitelist'),
        ({'trigger': {'group-respond-rules': {'prefix': 'ai'}}}, 'prefix must be a list of strings'),
        ({'trigger': {'group-respond-rules': {'at': 1}}}, 'at must be a boolean'),
        ({'trigger': {'group-respond-rules': {'random': 1.5}}}, 'random must be between 0 and 1'),
        ({'safety': {'rate-limit': {'window-length': 0}}}, 'window-length must be at least 1'),
        ({'safety': {'rate-limit': {'limitation': True}}}, 'limitation must be an integer'),
        ({'output': {'force-delay': {'min': 3, 'max': 1}}}, 'force-delay.min must not exceed max'),
        ({'output': {'long-text-processing': {'threshold': -1}}}, 'threshold must not be negative'),
    ],
)
def test_validate_rejects_what_would_silently_do_nothing_or_break(policy, message):
    with pytest.raises(ValueError, match=message):
        schema.validate_policy(policy)


def test_coerce_keeps_unconvertible_stored_values_instead_of_failing():
    policy = schema.neutral_policy()
    policy['safety']['rate-limit']['window-length'] = '120'
    policy['safety']['rate-limit']['limitation'] = 'many'

    schema.coerce_policy(policy)

    assert policy['safety']['rate-limit']['window-length'] == 120
    assert policy['safety']['rate-limit']['limitation'] == 'many'

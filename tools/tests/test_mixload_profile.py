from pathlib import Path
import tempfile
import unittest

from tools.regression.mixload_profile import compile_mixload, load_mixload, parse_mixload


def phase(name='normal', **updates):
    return {'name': name, 'duration_seconds': 20, 'rps': 3, 'workers': 4, **updates}


def catalogue(*names, group=False):
    return [
        {
            'name': name,
            'expect': name + ' OK',
            **(
                {'http_group': {'url': '${endpoint}', 'secret_env': 'LANGBOT_QA_GROUP_SECRET', 'message': name}}
                if group
                else {'args': ['pipeline', 'run', '${id}', '-m', name]}
            ),
        }
        for name in names
    ]


def select(phase_plan):
    return [(case['name'], case['weight']) for case in phase_plan.cases]


class MixloadProfileTests(unittest.TestCase):
    def test_defaults_follow_unmodified_catalogue_order_and_weights(self):
        catalog = catalogue('chat', 'box', 'rag')
        catalog[0]['weight'] = 2
        default_phases = [phase(duration_seconds=4 * 3600, cooldown_seconds=60)]
        config = parse_mixload({'version': 1})

        (plan,) = compile_mixload(catalog, config, default_phases=default_phases)

        self.assertEqual(select(plan), [('chat', 2), ('box', 1), ('rag', 1)])
        self.assertEqual(plan.phase, default_phases[0])
        self.assertIsNone(plan.min_delivery_ratio)
        plan.cases[0]['args'].append('discard')
        self.assertNotIn('discard', catalog[0]['args'])
        self.assertNotIn('weight', catalog[1])
        plan.phase['workers'] = 5
        self.assertEqual(default_phases[0]['workers'], 4)

    def test_global_selection_and_local_weights_precedence(self):
        catalog = catalogue('chat', 'box', 'rag', 'other', group=True)
        config = parse_mixload(
            {
                'version': 1,
                'exclude': ['other'],
                'weights': {'chat': 2},
                'phases': [
                    phase('baseline', groups=8, cooldown_seconds=0, members_per_group=3, max_requests=20),
                    phase('phase-two', groups=8, weights={'chat': 0, 'box': 4}, min_delivery_ratio=0.85),
                ],
            }
        )

        first, second = compile_mixload(catalog, config)

        self.assertEqual(select(first), [('chat', 2), ('box', 1), ('rag', 1)])
        self.assertEqual(select(second), [('box', 4), ('rag', 1)])
        self.assertEqual(first.phase['max_requests'], 20)
        self.assertEqual(first.phase['groups'], 8)
        self.assertNotIn('weights', second.phase)
        self.assertNotIn('min_delivery_ratio', second.phase)
        self.assertEqual(second.min_delivery_ratio, 0.85)

    def test_explicit_include_and_optional_phase_fallback(self):
        plan = compile_mixload(
            catalogue('chat', 'box', 'rag'),
            parse_mixload({'version': 1, 'include': ['rag', 'chat'], 'exclude': ['box']}),
            default_phases=[phase()],
        )
        self.assertEqual(select(plan[0]), [('chat', 1), ('rag', 1)])

    def test_seed_is_repeatable_without_changing_membership(self):
        catalog = catalogue('chat', 'box', 'rag', 'attachment', 'long', 'management')

        def make_config(seed):
            return parse_mixload({'version': 1, 'seed': seed, 'phases': [phase()]})

        a = select(compile_mixload(catalog, make_config(239))[0])
        b = select(compile_mixload(catalog, make_config(239))[0])
        c = select(compile_mixload(catalog, make_config(123))[0])
        self.assertEqual(a, b)
        self.assertNotEqual(a, c)
        self.assertCountEqual(a, [(case['name'], 1) for case in catalog])

    def test_invalid_objects_are_rejected_early(self):
        for value, error in (
            ([], 'must be an object'),
            ({}, 'missing required fields: version'),
            ({'version': True}, 'version must be 1'),
            ({'version': 1.0}, 'version must be 1'),
            ({'version': 1, 'endpoint': 'https://invalid.example'}, 'unknown fields: endpoint'),
            ({'version': 1, 'include': ['chat', 'chat']}, 'repeats a scenario'),
            ({'version': 1, 'include': ['chat'], 'exclude': ['chat']}, 'both included and excluded'),
            ({'version': 1, 'include': ['https://invalid.example']}, 'simple scenario name'),
            ({'version': 1, 'seed': True}, 'seed must be an integer'),
            ({'version': 1, 'weights': {'chat': 0}}, 'weights.chat'),
            ({'version': 1, 'phases': []}, 'non-empty array'),
            ({'version': 1, 'phases': [{'name': 'small'}]}, 'missing required fields'),
            ({'version': 1, 'phases': [phase(), phase()]}, 'duplicate phase name'),
            ({'version': 1, 'phases': [phase(name='../test')]}, 'simple scenario name'),
            ({'version': 1, 'phases': [phase(endpoint='https://invalid.example')]}, 'unknown fields: endpoint'),
            ({'version': 1, 'phases': [phase(workers=33)]}, 'workers'),
            ({'version': 1, 'phases': [phase(groups=True)]}, 'groups must be an integer'),
            ({'version': 1, 'phases': [phase(rps=float('inf'))]}, 'rps'),
            ({'version': 1, 'phases': [phase(rps=10**400)]}, 'rps'),
            ({'version': 1, 'phases': [phase(duration_seconds=1e200, rps=1e200)]}, 'must be finite'),
            ({'version': 1, 'phases': [phase(duration_seconds=4 * 3600, rps=1000)]}, 'planned request slots'),
            ({'version': 1, 'phases': [phase(cooldown_seconds=-1)]}, 'cooldown_seconds'),
            ({'version': 1, 'phases': [phase(max_requests=1.0)]}, 'max_requests must be an integer'),
            ({'version': 1, 'phases': [phase(min_delivery_ratio=1.1)]}, 'min_delivery_ratio'),
            ({'version': 1, 'phases': [phase(min_delivery_ratio=False)]}, 'min_delivery_ratio'),
            ({'version': 1, 'phases': [phase(weights={'chat': -1})]}, 'weights.chat'),
        ):
            with self.subTest(value=value), self.assertRaisesRegex(ValueError, error):
                parse_mixload(value)

    def test_large_nominal_slot_count_can_be_explicitly_capped(self):
        config = parse_mixload({'version': 1, 'phases': [phase(duration_seconds=4 * 3600, rps=1000, max_requests=20)]})
        plan = compile_mixload(catalogue('chat'), config)
        self.assertEqual(plan[0].phase['max_requests'], 20)

    def test_strict_json_duplicate_keys_are_not_silently_overwritten(self):
        with tempfile.TemporaryDirectory() as temp:
            path = Path(temp) / 'profile.json'
            for text, expected in (
                ('{"version": 1}', None),
                ('{"version": 1, "weights": {"chat": 2, "chat": 0}}', 'duplicate JSON key: chat'),
                ('{"version": 1, "seed": NaN}', 'non-finite JSON number'),
                ('{"version": 1, "seed": Infinity}', 'non-finite JSON number'),
            ):
                with self.subTest(text=text):
                    path.write_text(text)
                    if expected:
                        with self.assertRaisesRegex(ValueError, expected):
                            load_mixload(path)
                    else:
                        self.assertIsNone(load_mixload(path).include)

    def test_incompatible_or_unknown_configurations_fail(self):
        cases = [
            ({'include': ['missing']}, 'include references unknown'),
            ({'exclude': ['missing']}, 'exclude references unknown'),
            ({'exclude': ['chat', 'box']}, 'selects no scenarios'),
            ({'include': []}, 'selects no scenarios'),
            ({'include': ['chat'], 'weights': {'box': 1}}, 'selected scenarios only'),
            ({'phases': [phase(weights={'missing': 0})]}, 'references unknown'),
            ({'phases': [phase(weights={'chat': 0, 'box': 0})]}, 'selects no scenarios'),
            ({'phases': [phase(weights={'chat': 1000, 'box': 1})]}, 'total case weight'),
            ({'phases': [phase(groups=2)]}, 'groups require only http_group cases'),
            ({'phases': [phase(members_per_group=2)]}, 'members_per_group requires group traffic'),
        ]
        catalog = catalogue('chat', 'box')
        for overrides, error in cases:
            value = {'version': 1, 'phases': [phase()], **overrides}
            with self.subTest(overrides=overrides), self.assertRaisesRegex(ValueError, error):
                compile_mixload(catalog, parse_mixload(value))
        with self.assertRaisesRegex(ValueError, 'phases must be a non-empty array'):
            compile_mixload(catalog, parse_mixload({'version': 1}))

    def test_group_phase_needs_a_compatible_complete_weighted_sequence(self):
        group = catalogue('chat', 'box', group=True)
        finite = catalogue('provider-admin')
        finite[0]['scenario'] = 'api_llm'
        for catalog, options, error in (
            (group, phase(), 'requires groups'),
            (group, phase(groups=2, weights={'box': 2}), 'complete weighted case sequence'),
            ([group[0], *catalogue('normal-cli')], phase(groups=2), 'cannot mix'),
            (finite, phase(), 'finite/control scenarios'),
            ([group[0], group[0]], phase(groups=2), 'duplicate catalogue case'),
        ):
            with self.subTest(options=options), self.assertRaisesRegex(ValueError, error):
                compile_mixload(catalog, parse_mixload({'version': 1, 'phases': [options]}))

import unittest

from app.agent_fallback import validate_plan
from app.agent_policy import button_kind, field_is_sensitive, resolve_value_ref
from app.ats_boards import parse_board_configs
from app.profile_store import default_profile, runtime_profile
from app.smart_fields import fuzzy_score


class AgentPolicyTests(unittest.TestCase):
    def test_submit_is_never_next(self):
        self.assertEqual(button_kind('Submit application'), 'submit')
        self.assertEqual(button_kind('Envoyer ma candidature'), 'submit')
        self.assertEqual(button_kind('Suivant'), 'next')
        self.assertEqual(button_kind('Create account'), 'account')

    def test_sensitive_and_work_auth_questions_are_blocked(self):
        self.assertTrue(field_is_sensitive({'label': 'Do you require visa sponsorship?'}))
        self.assertTrue(field_is_sensitive({'label': 'Êtes-vous en situation de handicap ?'}))
        self.assertTrue(field_is_sensitive({'label': 'I certify that this information is true'}))
        self.assertFalse(field_is_sensitive({'label': 'What is your city?'}))

    def test_only_whitelisted_value_refs_resolve(self):
        p = runtime_profile(default_profile())
        p['first_name'] = 'Ada'
        p['email'] = 'ada@example.test'
        self.assertEqual(resolve_value_ref('profile.first_name', p), 'Ada')
        self.assertEqual(resolve_value_ref('profile.email', p), 'ada@example.test')
        self.assertIsNone(resolve_value_ref('profile.secret_token', p))

    def test_plan_validator_drops_unapproved_operations(self):
        plan = validate_plan({
            'status': 'CONTINUE',
            'actions': [
                {'op': 'fill', 'field_id': 'field-1', 'value_ref': 'profile.email', 'confidence': 95},
                {'op': 'submit', 'button_id': 'button-9', 'confidence': 100},
                {'op': 'execute_js', 'confidence': 100},
            ],
        })
        self.assertEqual([a['op'] for a in plan['actions']], ['fill'])

    def test_fuzzy_option_matching(self):
        self.assertGreater(fuzzy_score('France', 'France'), 0.99)
        self.assertGreater(fuzzy_score('Île-de-France', 'Ile de France'), fuzzy_score('Île-de-France', 'Germany'))

    def test_board_parser(self):
        rows = parse_board_configs([
            'greenhouse:acme:Acme Corp',
            'ashby:example:Example',
            {'ats': 'lever', 'board': 'foo', 'company': 'Foo'},
            'invalid:thing:Nope',
        ])
        self.assertEqual(len(rows), 3)
        self.assertEqual(rows[0].board, 'acme')
        self.assertEqual(rows[2].ats, 'lever')


if __name__ == '__main__':
    unittest.main()

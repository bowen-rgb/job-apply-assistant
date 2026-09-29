import unittest

from app.chatgpt_bridge import _extract_json_for_purpose


class ChatGPTBridgeTests(unittest.TestCase):
    def test_final_review_ignores_prompt_schema_example(self):
        text = '''
Return ONLY JSON:
{"verdict":"APPLY|SKIP|HUMAN_REVIEW","confidence":0}
Model answer:
{"verdict":"SKIP","confidence":99,"summary":"CDD trop long","reasons":[],"risks":[],"manual_questions":[],"facts":{}}
'''
        obj = _extract_json_for_purpose(text, 'final-review')
        self.assertIsNotNone(obj)
        self.assertEqual(obj['verdict'], 'SKIP')
        self.assertEqual(obj['confidence'], 99)

    def test_agent_extracts_typed_plan(self):
        text = '''
{"status":"CONTINUE|HANDOFF|DONE","actions":[]}
{"status":"HANDOFF","reason":"question requiert une personne","actions":[],"manual_questions":["x"]}
'''
        obj = _extract_json_for_purpose(text, 'job-agent')
        self.assertIsNotNone(obj)
        self.assertEqual(obj['status'], 'HANDOFF')


if __name__ == '__main__':
    unittest.main()

import unittest

from app.chatgpt_bridge import _extract_json_for_purpose, _page_json, _is_generating
from playwright.sync_api import sync_playwright


class ChatGPTBridgeTests(unittest.TestCase):
    def test_current_speaker_layout_reads_only_assistant_response(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<main>
                    <article><h6>你说：</h6><div>{"letter":"User example must not be accepted"}</div></article>
                    <section><div><h6>ChatGPT 说：</h6></div><div>{"letter":"Madame, Monsieur, candidature adaptée à votre établissement."}</div></section>
                    <button aria-label="停止流式传输">Stop</button>
                </main>''')
                self.assertEqual(_page_json(page, 'cover-letter')['letter'],
                                 'Madame, Monsieur, candidature adaptée à votre établissement.')
                self.assertTrue(_is_generating(page))
                page.set_content('<main><article><h6>你说：</h6>{"verdict":"APPLY"}</article></main>')
                self.assertIsNone(_page_json(page, 'final-review'))
            finally:
                browser.close()

    def test_letter_prompt_cannot_be_mistaken_for_response(self):
        self.assertIsNone(_extract_json_for_purpose('Schéma {"letter":""}', 'cover-letter'))
        response = _extract_json_for_purpose('Schéma {"letter":""}\n{"letter":"Madame, Monsieur, voici ma candidature."}', 'cover-letter')
        self.assertTrue(response['letter'].startswith('Madame'))

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

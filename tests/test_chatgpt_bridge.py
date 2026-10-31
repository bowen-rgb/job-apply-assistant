import unittest

from app.chatgpt_bridge import _extract_json_for_purpose, _page_json, _is_generating
from playwright.sync_api import sync_playwright


class ChatGPTBridgeTests(unittest.TestCase):
    def test_new_assistant_markup_and_loading_error_are_separate_from_user_text(self):
        from app.chatgpt_bridge import _response_failure
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.set_content('<article data-message-author-role="user">无法加载此回复</article><div data-markdown-text-style="assistant-message">{"verdict":"APPLY","confidence":95,"summary":"Verified"}</div>')
                self.assertIsNone(_response_failure(page))
                self.assertEqual(_page_json(page,'final-review')['verdict'],'APPLY')
                page.set_content('<div data-markdown-text-style="assistant-message"><div role="status">无法加载此回复</div></div>')
                self.assertIn('could not load',_response_failure(page))
                self.assertIsNone(_page_json(page,'final-review'))
            finally:browser.close()

    def test_loading_failure_retries_only_one_worker_owned_tab(self):
        from unittest.mock import MagicMock,patch
        from app import chatgpt_bridge as bridge
        first,second=MagicMock(),MagicMock()
        context=MagicMock();context.new_page.side_effect=[first,second]
        expected={'verdict':'APPLY','confidence':95,'summary':'Verified'}
        with patch.object(bridge,'CHATGPT_LOCK'),patch.object(bridge,'_find_prompt'),patch.object(bridge,'_set_prompt'),patch.object(bridge,'_assistant_messages',return_value=[]),patch.object(bridge,'_diagnostic'),patch.object(bridge,'_wait_response',side_effect=[bridge.ChatGPTResponseError('load failed'),expected]) as wait:
            self.assertEqual(bridge.ask_chatgpt_json(context,'same review',{},purpose='final-review'),expected)
            self.assertEqual(wait.call_count,2)
            self.assertEqual(context.new_page.call_count,2)
            first.close.assert_called_once();second.close.assert_called_once()
            context.close.assert_not_called()
            first.reload.assert_not_called();second.reload.assert_not_called()

    def test_repeated_loading_failure_stops_after_one_retry_and_keeps_evidence(self):
        from unittest.mock import MagicMock,patch
        from app import chatgpt_bridge as bridge
        first,second=MagicMock(),MagicMock()
        context=MagicMock();context.new_page.side_effect=[first,second]
        with patch.object(bridge,'CHATGPT_LOCK'),patch.object(bridge,'_find_prompt'),patch.object(bridge,'_set_prompt'),patch.object(bridge,'_assistant_messages',return_value=[]),patch.object(bridge,'_diagnostic') as diagnostic,patch.object(bridge,'_wait_response',side_effect=bridge.ChatGPTResponseError('load failed')):
            with self.assertRaises(bridge.ChatGPTResponseError):bridge.ask_chatgpt_json(context,'same review',{},purpose='final-review')
            self.assertEqual(context.new_page.call_count,2)
            self.assertEqual(diagnostic.call_count,2)
            second.close.assert_not_called()

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

    def test_new_career_tasks_keep_whole_response_instead_of_last_nested_object(self):
        import json
        examples={
            'cv-tailor':{'sections':[{'heading':'Projects','lines':[{'text':'Actual work','source_quote':'Observed quote'}]}]},
            'cv-review':{'checks':{'factual_support':True},'issues':[]},
            'interview-pack':{'likely_questions':[{'question':'How?'}],'star_examples':[{'outline':'Evidence'}]},
            'mock-interview':{'feedback':'Use evidence','next_question':'How?','details':{'score':2}},
            'upskill':{'gaps':[{'skill':'Python'}],'plan':[{'week':1}]},
            'profile-expand':{'facts':[{'text':'Actual work'}],'questions':[]},
            'search_plan':{'roles':['Engineer'],'queries':['stage'],'details':{'x':1}},
            'calibration':{'lessons':[{'text':'Check conditions'}],'suggested_rules':[]},
            'followup-draft':{'subject':'Follow-up','body':'Thank you.','details':{'x':1}},
            'linkedin-triage':{'opportunities':[{'company':'Lab'}],'questions':[]},
            'portal-analyze':{'url':'https://jobs.test/','label':'Lab','item_selector':'.job','details':{'x':1}},
            'model-check':{'ok':True},
            'job-agent-step-1':{'status':'CONTINUE','actions':[{'op':'fill','args':{'value':'x'}}]},
        }
        for purpose,expected in examples.items():
            with self.subTest(purpose=purpose):
                self.assertEqual(_extract_json_for_purpose(json.dumps(expected),purpose),expected)
                self.assertIsNone(_extract_json_for_purpose('{"unrelated":{}}',purpose))
        generic={'unknown_future_task':{'nested':1}}
        self.assertEqual(_extract_json_for_purpose(json.dumps(generic),'future-task'),generic)

    def test_new_task_browser_response_ignores_user_schema_and_nested_fields(self):
        with sync_playwright() as pw:
            browser=pw.chromium.launch(headless=True)
            try:
                page=browser.new_page();page.set_content('''<article data-message-author-role="user">{"sections":[]}</article>
                    <article data-message-author-role="assistant">{"sections":[{"heading":"Projects","lines":[{"text":"Actual work","source":"cv"}]}],"gaps":[]}</article>''')
                result=_page_json(page,'cv-tailor')
                self.assertEqual(result['sections'][0]['lines'][0]['text'],'Actual work')
                self.assertIsNone(_page_json(page,'cv-tailor',[result]))
            finally:browser.close()


if __name__ == '__main__':
    unittest.main()

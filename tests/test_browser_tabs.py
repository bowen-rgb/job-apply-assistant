import unittest
from unittest.mock import MagicMock
from app.browser_tabs import application_page
from app.apply_worker import _open_browser


class StableTabTests(unittest.TestCase):
    def context(self):
        context = MagicMock()
        page = MagicMock(url='https://accounts.google.com/signin/challenge')
        page.is_closed.return_value = False
        context.pages = [page]
        context.new_cdp_session.return_value.send.return_value = {'targetInfo': {'targetId': 'login'}}
        return context, page

    def test_redirect_keeps_human_input_and_never_navigates(self):
        context, page = self.context()
        job = {'url': 'https://docs.google.com/forms/entry', 'application_tab_id': 'login'}
        for _ in range(3):
            self.assertIs(application_page(context, job), page)
        page.goto.assert_not_called()
        page.reload.assert_not_called()
        context.new_page.assert_not_called()

    def test_closed_target_does_not_reopen_or_create_context(self):
        context, _ = self.context()
        with self.assertRaises(ValueError):
            application_page(context, {'url': 'https://example.test', 'application_tab_id': 'gone'})
        context.new_page.assert_not_called()
        p = MagicMock()
        browser = p.chromium.connect_over_cdp.return_value
        browser.contexts = [context]
        with self.assertRaises(ValueError):
            _open_browser(p, {}, {'application_tab_id': 'gone'})
        browser.new_context.assert_not_called()

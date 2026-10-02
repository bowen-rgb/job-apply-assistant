import tempfile
import unittest
from pathlib import Path
from playwright.sync_api import sync_playwright
from app.application_form import find_form_scope, consent_pending, build_application_packet
from app.form_engine import generic_fill, generic_click_apply


class EmbeddedApplicationTests(unittest.TestCase):
    def test_packet_contains_original_cv_then_letter_without_modifying_sources(self):
        from reportlab.pdfgen.canvas import Canvas
        from pypdf import PdfReader
        with tempfile.TemporaryDirectory() as folder:
            root = Path(folder)
            cv, letter, result = root/'cv.pdf', root/'letter.pdf', root/'packet.pdf'
            for path, text in ((cv, 'Original CV'), (letter, 'Motivation for THE ROYAL PUB')):
                canvas = Canvas(str(path)); canvas.drawString(40, 700, text); canvas.save()
            original = cv.read_bytes()
            metadata = build_application_packet(cv, letter, result)
            pages = PdfReader(result).pages
            self.assertEqual(metadata['cv_pages'], 1)
            self.assertEqual(metadata['pages'], 2)
            self.assertIn('Original CV', pages[0].extract_text())
            self.assertIn('THE ROYAL PUB', pages[1].extract_text())
            self.assertEqual(cv.read_bytes(), original)

    def test_embedded_form_receives_both_documents_without_submission(self):
        with tempfile.TemporaryDirectory() as folder, sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<input type=email aria-label="Newsletter email">
                    <iframe srcdoc="<form onsubmit='window.submitted=true;return false'>
                    <input name=firstname><input name=lastname><input type=email>
                    <label>CV<input type=file name=cv></label>
                    <label>Lettre de motivation<input type=file name=letter></label>
                    <button type=submit>Postuler</button></form>"></iframe>''')
                frame = page.frames[1]
                frame.locator('input[name=cv]').wait_for()
                scope = find_form_scope(page)
                self.assertEqual(scope, frame)
                cv, letter = Path(folder)/'cv.pdf', Path(folder)/'letter.pdf'
                cv.write_bytes(b'%PDF-test CV'); letter.write_bytes(b'%PDF-test Letter')
                report = generic_fill(scope, {'first_name':'Lili','last_name':'Vionnet','email':'test@example.test',
                                              'cover_letter_path':str(letter)}, cv)
                self.assertIn('resume', report['filled'])
                self.assertIn('cover_letter_file', report['filled'])
                self.assertEqual(frame.locator('[name=cv]').evaluate('(e)=>e.files[0].name'), 'cv.pdf')
                self.assertEqual(frame.locator('[name=letter]').evaluate('(e)=>e.files[0].name'), 'letter.pdf')
                self.assertFalse(frame.evaluate('Boolean(window.submitted)'))
                self.assertEqual(page.locator('input').input_value(), '')
            finally:
                browser.close()

    def test_cookie_rejection_and_consent_gate_remains_unchecked(self):
        with sync_playwright() as pw:
            browser = pw.chromium.launch(headless=True)
            try:
                page = browser.new_page()
                page.set_content('''<button onclick="this.remove()">Continuer sans accepter</button>
                  <button onclick="document.querySelector('iframe').hidden=false">Postuler</button>
                  <iframe hidden srcdoc="<label><input type=checkbox id=acceptRgpd>J'accepte la charte</label>"></iframe>''')
                self.assertTrue(generic_click_apply(page))
                self.assertTrue(consent_pending(page))
                self.assertIsNone(find_form_scope(page))
                self.assertFalse(page.frames[1].locator('#acceptRgpd').is_checked())
            finally:
                browser.close()

import unittest
from playwright.sync_api import sync_playwright
from app.form_engine import generic_fill
from app.profile_store import default_profile, runtime_profile


class ResearchEducationTests(unittest.TestCase):
    def test_completed_and_prepared_degrees_are_separate_and_explicit(self):
        profile=default_profile()
        profile['background'].update(degree='Bachelor of Engineering',education_level='Bac+4',prepared_degree_level='Bac+5 - Diplôme École d’ingénieurs',prepared_degree='Ingénieur en mécanique',graduation_year='2024')
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.set_content('''<form>
                  <label>Diplôme obtenu<input id=completed></label>
                  <label>Niveau d'études<select id=level><option value="">Veuillez sélectionner une valeur</option><option value=4>Bac+4</option><option value=5>Bac+5</option></select></label>
                  <label>Diplôme préparé<select id=prepared><option value="">Veuillez sélectionner une valeur</option><option value=engineer>Bac+5 - Diplôme École d’ingénieurs</option></select></label>
                  <label>Intitulé du diplôme préparé<input id=preparedTitle></label>
                  <label>Année de diplôme<input id=year></label>
                  <label>Niveau<select id=language><option value="">Veuillez sélectionner une valeur</option><option value=b2>B2</option></select></label>
                  <label>Situation actuelle<select id=status><option value="">Veuillez sélectionner une valeur</option><option value=stage>Stage</option></select></label>
                </form>''')
                generic_fill(page,runtime_profile(profile))
                self.assertEqual(page.locator('#completed').input_value(),'Bachelor of Engineering')
                self.assertEqual(page.locator('#preparedTitle').input_value(),'Ingénieur en mécanique')
                self.assertEqual(page.locator('#level').input_value(),'4')
                self.assertEqual(page.locator('#prepared').input_value(),'engineer')
                self.assertEqual(page.locator('#year').input_value(),'2024')
                self.assertEqual(page.locator('#language').input_value(),'')
                self.assertEqual(page.locator('#status').input_value(),'')
            finally:browser.close()

    def test_unknown_repeated_and_preselected_education_is_not_guessed(self):
        with sync_playwright() as p:
            browser=p.chromium.launch(headless=True)
            try:
                page=browser.new_page()
                page.set_content('''<label>Diplôme préparé<input id=prepared></label><label>Niveau d'études<select id=first><option value="">Choose</option><option value=4>Bac+4</option></select></label><label>Niveau d'études<select id=second><option value="">Choose</option><option value=4>Bac+4</option></select></label>''')
                generic_fill(page,{'degree':'Existing completed degree','education_level':'Bac+4'})
                self.assertEqual(page.locator('#prepared').input_value(),'')
                self.assertEqual(page.locator('#first').input_value(),'')
                self.assertEqual(page.locator('#second').input_value(),'')
                page.set_content('''<label>Niveau d'études<select id=selected><option value=4>Bac+4</option><option value=5 selected>Bac+5</option></select></label>''')
                generic_fill(page,{'education_level':'Bac+4'})
                self.assertEqual(page.locator('#selected').input_value(),'5')
            finally:browser.close()

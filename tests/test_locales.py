import json
import unittest
import re
from pathlib import Path


class LocaleCatalogTests(unittest.TestCase):
    def test_all_six_languages_cover_the_interface(self):
        folder = Path(__file__).resolve().parents[1] / 'static' / 'locales'
        catalogs = {code: json.loads((folder / f'{code}.json').read_text(encoding='utf-8'))
                    for code in ('zh', 'fr', 'en', 'de', 'es', 'pt')}
        keys = set(catalogs['fr'])
        self.assertGreater(len(keys), 250)
        for code, translations in catalogs.items():
            with self.subTest(language=code):
                self.assertEqual(set(translations), keys)
                self.assertTrue(all(isinstance(value, str) and value for value in translations.values()))
                self.assertIn('Langue de l’interface', translations)
                self.assertIn('Pipeline & file', translations)
                self.assertIn('Ouvrir l’offre ↗', translations)
        self.assertEqual(catalogs['zh']['Offres'], '岗位')
        self.assertEqual(catalogs['en']['Offres'], 'Jobs')
        self.assertFalse(any(re.search('[\u4e00-\u9fff]', value) for value in catalogs['fr'].values()))
        self.assertEqual(catalogs['fr']['+ File'], 'Ajouter à la file')
        self.assertEqual(catalogs['zh']['À écarter'], '建议跳过')
        self.assertEqual(catalogs['zh']['Lettre de motivation'], '求职信')
        self.assertEqual(catalogs['zh']['En cours'], '处理中')
        self.assertEqual(catalogs['zh']['File:'], '队列：')


if __name__ == '__main__':
    unittest.main()

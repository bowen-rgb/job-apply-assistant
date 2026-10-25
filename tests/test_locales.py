import json
import unittest
import re
import subprocess
from pathlib import Path


class LocaleCatalogTests(unittest.TestCase):
    def test_translation_export_and_qr_contracts_accept_only_chinese_french(self):
        from pydantic import ValidationError
        from app.contracts import ReviewExport, TitleTranslationRequest
        from app.qr_routes import Analysis
        for model,extra in [(ReviewExport,{}),(TitleTranslationRequest,{'job_ids':[1]}),(Analysis,{})]:
            for language in ['zh','fr']:
                self.assertEqual(model(language=language,**extra).language,language)
            for language in ['en','de','es','pt']:
                with self.assertRaises(ValidationError):model(language=language,**extra)

    def test_only_chinese_french_are_offered_and_legacy_preference_falls_back(self):
        root=Path(__file__).resolve().parents[1]
        self.assertEqual({p.stem for p in (root/'static/locales').glob('*.json')},{'zh','fr'})
        source=(root/'static/index.html').read_text(encoding='utf-8')
        for identifier in ['languageSelect','reviewExportLanguage']:
            options=re.search(r'<select[^>]*id="'+identifier+r'"[^>]*>(.*?)</select>',source,re.S).group(1)
            self.assertEqual(re.findall(r'value="([^"]+)"',options),['zh','fr'])
        script=r'''const vm=require('vm'),fs=require('fs');const calls=[],saved=new Map([['jaa-ui-language','de']]);
const body={querySelectorAll:()=>[]};const context={navigator:{language:'en-US'},localStorage:{getItem:k=>saved.get(k),setItem:(k,v)=>saved.set(k,v)},fetch:async u=>{calls.push(u);return {ok:true,json:async()=>({})}},document:{body,documentElement:{},getElementById:()=>null,createTreeWalker:()=>({nextNode:()=>false}),dispatchEvent:()=>{}},Node:{ELEMENT_NODE:1},NodeFilter:{SHOW_TEXT:4},MutationObserver:class{observe(){}},CustomEvent:class{},console,queueMicrotask};
vm.createContext(context);vm.runInContext(fs.readFileSync('static/locale.js','utf8')+';globalThis.locale=Locale;',context);
context.locale.ready.then(()=>{const initial=context.locale.language;context.locale.setLanguage('en');const rejected=context.locale.language;context.locale.setLanguage('zh');console.log(JSON.stringify({initial,rejected,final:context.locale.language,calls,saved:saved.get('jaa-ui-language')}));});'''
        result=json.loads(subprocess.check_output(['node','-e',script],cwd=root,text=True))
        self.assertEqual(result['initial'],'fr');self.assertEqual(result['rejected'],'fr')
        self.assertEqual(result['final'],'zh');self.assertEqual(result['saved'],'zh')
        self.assertEqual(set(result['calls']),{'/static/locales/zh.json','/static/locales/fr.json'})

    def test_all_two_languages_cover_the_interface(self):
        folder = Path(__file__).resolve().parents[1] / 'static' / 'locales'
        catalogs = {code: json.loads((folder / f'{code}.json').read_text(encoding='utf-8'))
                    for code in ('zh', 'fr')}
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
        self.assertFalse(any(re.search('[\u4e00-\u9fff]', value) for value in catalogs['fr'].values()))
        self.assertEqual(catalogs['fr']['+ File'], 'Ajouter à la file')
        self.assertEqual(catalogs['zh']['À écarter'], '建议跳过')
        self.assertEqual(catalogs['zh']['Lettre de motivation'], '求职信')
        self.assertEqual(catalogs['zh']['En cours'], '处理中')
        self.assertEqual(catalogs['zh']['File:'], '队列：')
        self.assertEqual(catalogs['zh']['Utiliser ce CV'], '使用这份简历')
        self.assertEqual(catalogs['zh']['CV utilisé'], '当前使用')
        self.assertEqual(catalogs['zh']['Enregistrer le nom et les tags'], '保存名称和标签')
        self.assertEqual(catalogs['zh']['auto'], '自动')
        for mistranslation in ('使能够', '积极的', '节省', '工作间谍', '确实国家', '本地图书馆', '工人开始了', '主动 CV', '自动布线'):
            self.assertFalse(any(mistranslation in value for value in catalogs['zh'].values()),mistranslation)


if __name__ == '__main__':
    unittest.main()

"""Standalone HTML and XLSX snapshots for an external human reviewer.

Uses the filtered, explicit-column export pattern of Odoo, independently
implemented. XlsxWriter tables provide filtering and editable review columns.
https://github.com/odoo/odoo/blob/19.0/addons/web/controllers/export.py
https://xlsxwriter.readthedocs.io/worksheet.html#worksheet-add-table
"""
import html
import io
import json
from pathlib import Path
from urllib.parse import urlparse

ROOT = Path(__file__).resolve().parent.parent
NOTE = 'Ce fichier est un instantané pour lecture et commentaires. Aucun avis ne soumet une candidature ni ne modifie le suivi local.'
TRANSLATION_NOTE = 'Les traductions automatiques sont des aides à la lecture. Les originaux sont conservés pour vérification.'
FIELDS = ('id', 'title', 'company', 'location', 'url', 'source', 'employment_type',
          'start_date', 'end_date', 'valid_through', 'salary', 'review_verdict',
          'review_confidence', 'review_summary', 'review_json', 'reviewed_at',
          'human_review_status', 'human_reviewed_at')


def labels(language):
    return json.loads((ROOT / 'static' / 'locales' / f'{language}.json').read_text(encoding='utf-8'))


def safe_url(value):
    try:
        parsed = urlparse(str(value or ''))
        return str(value) if parsed.scheme in {'http', 'https'} and parsed.hostname and not parsed.username else ''
    except ValueError:
        return ''


def strings(value):
    return [str(x) for x in value if isinstance(x, (str, int, float))] if isinstance(value, list) else []


def report_row(job):
    job = {k: job.get(k) for k in FIELDS}
    try:
        review = json.loads(job.get('review_json') or '{}')
    except (ValueError, TypeError):
        review = {}
    if not isinstance(review, dict):
        review = {}
    facts = review.get('facts') if isinstance(review.get('facts'), dict) else {}
    original = dict(title=str(job.get('title') or ''), summary=str(job.get('review_summary') or review.get('summary') or ''),
                    reasons=strings(review.get('reasons')), risks=strings(review.get('risks')),
                    questions=strings(review.get('manual_questions')),
                    facts={k: str(facts[k]) for k in ('contract', 'start_date', 'end_date', 'location', 'schedule', 'salary') if facts.get(k)})
    return {**job, 'url': safe_url(job.get('url')), 'original': original, 'display': dict(original), 'translation': 'original'}


def render_html(rows, metadata):
    t = lambda key: labels_map.get(key, key)
    labels_map = labels(metadata['language'])
    e = lambda value: html.escape(str(value or ''), quote=True)
    listing = lambda values: '<ul>' + ''.join(f'<li>{e(v)}</li>' for v in values) + '</ul>' if values else f'<p>{e(t("Non renseigné"))}</p>'
    verdict = {'APPLY': 'Candidature conseillée', 'HUMAN_REVIEW': 'À vérifier', 'SKIP': 'À écarter'}
    states = {'pending': 'À confirmer par vous', 'approved': 'Confirmée par vous', 'declined': 'Écartée par vous', 'not_required': 'Non renseigné'}
    content = []
    for row in rows:
        d, original = row['display'], row['original']
        facts = {t('Contrat'): row.get('employment_type'), t('Début'): row.get('start_date'), t('Fin'): row.get('end_date'),
                 t('Date limite'): row.get('valid_through'), t('Salaire'): row.get('salary'), t('Revue IA du'): row.get('reviewed_at')}
        facts.update({t({'contract':'Contrat', 'start_date':'Début', 'end_date':'Fin', 'location':'Lieu', 'schedule':'Horaires', 'salary':'Salaire'}[k]): v for k,v in d['facts'].items()})
        sections = ''.join(f'<section><h3>{e(t(key))}</h3>{listing(d[field])}</section>' for key,field in [('Raisons','reasons'),('Risques','risks'),('Questions à vérifier','questions')])
        originals = f'<details><summary>{e(t("Textes originaux"))}</summary><h3>{e(original["title"])}</h3><p>{e(original["summary"])}</p>' + ''.join(f'<h4>{e(t(key))}</h4>{listing(original[field])}' for key,field in [('Raisons','reasons'),('Risques','risks'),('Questions à vérifier','questions')]) + listing([f'{k}: {v}' for k,v in original['facts'].items()]) + '</details>'
        status = 'good' if row.get('review_verdict') == 'APPLY' else 'warn'
        content.append(f'''<article><header><h2>{e(d['title'])}</h2><p>{e(row.get('company'))} · {e(row.get('location'))}</p></header>
        <p><span class="badge {status}">AI · {e(t(verdict.get(row.get('review_verdict'),row.get('review_verdict') or 'Non renseigné')))}</span>
        <span class="badge">{e(t(states.get(row.get('human_review_status'),'Non renseigné')))}</span> · #{row['id']}</p>
        <p class="small">{e(t('Source'))}: {e(row.get('source'))} · {e(t('Traduction'))}: {e(t({'translated':'Traduction automatique','original':'Texte original','unavailable':'Traduction indisponible'}.get(row['translation'],'Texte original')))}</p>
        <dl>{''.join(f'<dt>{e(k)}</dt><dd>{e(v)}</dd>' for k,v in facts.items() if v)}</dl>
        <h3>{e(t('Résumé IA'))}</h3><p>{e(d['summary']) or e(t('Non renseigné'))}</p>{sections}
        {f'<p><a href="{e(row["url"])}" target="_blank" rel="noopener noreferrer">{e(t("Ouvrir l’offre ↗"))}</a></p>' if row['url'] else ''}
        {originals}<section class="notes"><h3>{e(t('Avis du vérificateur'))}</h3><p>☐ {e(t('À préparer'))}　☐ {e(t('Ne pas préparer ce poste'))}　☐ {e(t('Informations à compléter'))}</p><p>{e(t('Commentaire du vérificateur'))}: ____________________________</p></section></article>''')
    warnings = f'<p class="warning">{e(t("Certaines traductions sont indisponibles ; les textes originaux sont affichés."))}</p>' if any(r['translation']=='unavailable' for r in rows) else ''
    title=e(t('Revue des postes'))
    return f'''<!doctype html><html lang="{e(metadata['language'])}"><head><meta charset="utf-8"><meta name="viewport" content="width=device-width,initial-scale=1"><meta name="referrer" content="no-referrer"><title>{title}</title>
    <style>body{{font:16px/1.65 system-ui,sans-serif;background:#f6f5f0;color:#26342e;margin:0}}main{{max-width:1100px;margin:auto;padding:28px}}h1,h2,h3,p{{overflow-wrap:anywhere}}h2{{line-height:1.35;font-size:24px}}h3{{font-size:17px}}article{{background:white;padding:26px;margin:22px 0;border:1px solid #dce3d8;border-radius:12px;break-inside:avoid}}.badge{{display:inline-block;padding:4px 9px;border-radius:6px;background:#e7ecdf;font-size:14px}}.good{{background:#dfeddf}}.warn,.warning{{background:#f5ebd7;padding:10px}}.small,details{{font-size:14px;color:#576760}}dl{{display:grid;grid-template-columns:130px 1fr;gap:6px}}dd{{margin:0}}dt{{font-weight:600}}.notes{{border-top:1px solid #dce3d8;margin-top:20px}}a{{color:#245f41}}@media print{{body{{background:white}}main{{padding:0}}article{{border:0;border-bottom:1px solid #aaa;border-radius:0;break-inside:auto}}details{{display:none}}a{{color:black}}}}</style></head>
    <body><main><h1>{title}</h1><p>{len(rows)} {e(t('offres affichées'))} · {e(metadata['created_at'])} · {e(t('Instantané'))}</p><p>{e(t(NOTE))}</p><p>{e(t(TRANSLATION_NOTE))}</p>{warnings}{''.join(content)}</main></body></html>'''


def render_xlsx(rows, metadata):
    import xlsxwriter
    catalog=labels(metadata['language'])
    t=lambda key:catalog.get(key,key)
    output=io.BytesIO()
    # Never turn untrusted titles/comments into formulas or automatic links.
    # https://xlsxwriter.readthedocs.io/workbook.html#constructor
    book=xlsxwriter.Workbook(output,{'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
    sheet=book.add_worksheet(t('Revue des postes')[:31])
    wrap=book.add_format({'text_wrap':True,'valign':'top'})
    header=book.add_format({'bold':True,'bg_color':'#315c46','font_color':'white','text_wrap':True})
    names=['ID','Poste','Titre original :','Entreprise','Lieu','Lien du poste','Verdict IA','Confiance IA','Confirmation humaine','Résumé IA','Raisons','Risques','Questions à vérifier','Contrat','Début','Fin','Date limite','Revue IA du','Textes originaux','Traduction','Avis du vérificateur','Commentaire du vérificateur','Informations du reviewer','Salaire']
    data=[]
    verdict={'APPLY':'Candidature conseillée','HUMAN_REVIEW':'À vérifier','SKIP':'À écarter'}
    states={'pending':'À confirmer par vous','approved':'Confirmée par vous','declined':'Écartée par vous'}
    for row in rows:
        d=row['display']
        original=row['original']
        text='\n\n'.join([original['summary'],*original['reasons'],*original['risks'],*original['questions'],*[f'{k}: {v}' for k,v in original['facts'].items()]])
        data.append([row['id'],d['title'],original['title'],row.get('company') or '',row.get('location') or '',row['url'],t(verdict.get(row.get('review_verdict'),row.get('review_verdict') or 'Non renseigné')),row.get('review_confidence') or 0,t(states.get(row.get('human_review_status'),'Non renseigné')),d['summary'],'\n'.join(d['reasons']),'\n'.join(d['risks']),'\n'.join(d['questions']),row.get('employment_type') or '',row.get('start_date') or '',row.get('end_date') or '',row.get('valid_through') or '',row.get('reviewed_at') or '',text,t({'translated':'Traduction automatique','unavailable':'Traduction indisponible','original':'Texte original'}[row['translation']]),'',''])
        data[-1].extend(['\n'.join(f'{t({"contract":"Contrat","start_date":"Début","end_date":"Fin","location":"Lieu","schedule":"Horaires","salary":"Salaire"}[k])}: {v}' for k,v in d['facts'].items()),row.get('salary') or ''])
    too_long=any(isinstance(value,str) and len(value)>32767 for line in data for value in line)
    marker='\n… '+t('Texte trop long : utilisez HTML pour le lire intégralement.')
    data=[[value if not isinstance(value,str) or len(value)<=32767 else value[:32767-len(marker)]+marker for value in line] for line in data]
    sheet.add_table(0,0,len(data),len(names)-1,{'data':data,'columns':[{'header':t(n),'format':wrap,'header_format':header} for n in names],'style':'Table Style Medium 4'})
    sheet.freeze_panes(1,3)
    sheet.set_row(0,40)
    sheet.set_column(0,0,8)
    sheet.set_column(1,len(names)-1,28,wrap)
    sheet.set_column(9,12,48,wrap)
    sheet.set_column(18,18,60,wrap)
    sheet.set_column(20,21,36,wrap)
    for index,row in enumerate(rows,1):
        sheet.set_row(index,100)
        if row['url']:sheet.write_url(index,5,row['url'],wrap,row['url'])
    sheet.data_validation(1,20,len(data),20,{'validate':'list','source':[t('À préparer'),t('Ne pas préparer ce poste'),t('Informations à compléter')]})
    guide=book.add_worksheet(t('Guide'))
    guide.set_column(0,0,26)
    guide.set_column(1,1,100,wrap)
    for index,line in enumerate([(t('Revue des postes'),metadata['created_at']),(t('Instantané'),str(len(rows))),(t('Avis du vérificateur'),t(NOTE)),(t('Traduction'),t(TRANSLATION_NOTE)),(t('Traduction indisponible'),t('Certaines traductions sont indisponibles ; les textes originaux sont affichés.') if any(r['translation']=='unavailable' for r in rows) else '')]):
        guide.write_row(index,0,line,wrap)
        guide.set_row(index,60)
    if too_long:guide.write(5,1,t('Texte trop long : utilisez HTML pour le lire intégralement.'),wrap)
    book.close()
    return output.getvalue()

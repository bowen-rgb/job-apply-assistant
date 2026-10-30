"""Import/export existing application ledgers into the single native job store.

Column/status aliases and preview-first append-only policy adapted from
Apply-Pilot src/importer.mjs (MIT). Source uploads are never executed or modified.
"""
import csv
import hashlib
import io
import json
import re
import zipfile
from datetime import date, timedelta
from xml.etree import ElementTree as ET
import posixpath
from difflib import SequenceMatcher
from urllib.parse import urlsplit
from .application_intelligence import fold, parsed_date
from .db import connect
from .extractor import canonicalize_url
from .job_identity import build_job_dedupe_key

ALIASES = {
    'company': ['company', 'employer', 'entreprise', 'societe', 'laboratoire', '公司', '雇主'],
    'title': ['title', 'role', 'position', 'poste', 'intitule', '岗位', '职位'],
    'url': ['url', 'link', 'lien', '链接', '网址'],
    'stage': ['status', 'stage', 'statut', 'etat', '状态', '结果'],
    'date': ['date', 'applied on', 'date applied', 'application date', '投递日期', '日期'],
    'note': ['note', 'notes', 'comment', 'remarques', '备注'],
    'location': ['location', 'city', 'lieu', 'ville', '地点', '城市'],
}


def read_xlsx(content):
    """Read values from the first sheet with the standard library, never formulas/macros."""
    ns = {'s': 'http://schemas.openxmlformats.org/spreadsheetml/2006/main'}
    with zipfile.ZipFile(io.BytesIO(content)) as archive:
        if sum(info.file_size for info in archive.infolist()) > 32_000_000 or len(archive.infolist()) > 10000:
            raise ValueError('Workbook too large')
        strings = []
        if 'xl/sharedStrings.xml' in archive.namelist():
            root = ET.fromstring(archive.read('xl/sharedStrings.xml'))
            strings = [''.join(node.itertext()) for node in root.findall('s:si', ns)]
        root = ET.fromstring(archive.read('xl/workbook.xml'))
        properties = root.find('s:workbookPr', ns)
        epoch = date(1904,1,1) if properties is not None and properties.attrib.get('date1904') in {'1','true'} else date(1899,12,30)
        first = root.find('s:sheets/s:sheet', ns)
        if first is None:
            return []
        relation = first.attrib['{http://schemas.openxmlformats.org/officeDocument/2006/relationships}id']
        relations = ET.fromstring(archive.read('xl/_rels/workbook.xml.rels'))
        target = next(node.attrib['Target'] for node in relations if node.attrib['Id'] == relation and node.attrib.get('TargetMode') != 'External')
        path = posixpath.normpath(target.lstrip('/') if target.startswith('/') else 'xl/'+target)
        if not path.startswith('xl/worksheets/'):
            raise ValueError('Unsupported workbook sheet')
        date_styles = set()
        if 'xl/styles.xml' in archive.namelist():
            styles = ET.fromstring(archive.read('xl/styles.xml'))
            custom = {node.attrib['numFmtId']:node.attrib.get('formatCode','') for node in styles.findall('s:numFmts/s:numFmt', ns)}
            for index, node in enumerate(styles.findall('s:cellXfs/s:xf', ns)):
                fmt = node.attrib.get('numFmtId', '0')
                if 14 <= int(fmt) <= 22 or re.search(r'[yd]', custom.get(fmt, ''), re.I):
                    date_styles.add(str(index))
        sheet = ET.fromstring(archive.read(path))
        matrix = []
        for row in sheet.findall('s:sheetData/s:row', ns):
            values = {}
            for cell in row.findall('s:c', ns):
                column = re.match(r'[A-Z]+', cell.attrib.get('r', 'A1'))[0]
                index = 0
                for char in column:
                    index = index*26 + ord(char)-64
                if index > 100:
                    raise ValueError('Workbook has too many columns')
                text = cell.findtext('s:v', '', ns)
                kind = cell.attrib.get('t', '')
                if kind == 's': text = strings[int(text)]
                elif kind == 'inlineStr': text = ''.join(cell.find('s:is', ns).itertext())
                elif cell.attrib.get('s') in date_styles and text:
                    text = (epoch+timedelta(days=float(text))).isoformat()
                values[index-1] = text
            matrix.append([values.get(index, '') for index in range(max(values, default=-1)+1)])
            if len(matrix) > 1001:
                raise ValueError('Import at most 1000 rows at a time')
        return [dict(zip(matrix[0], row)) for row in matrix[1:]] if matrix else []


def stage(raw):
    text = fold(raw).strip()
    if re.search(r'reject|refus|non retenu|pas retenu|未录用|拒绝|not selected', text):
        return 'rejected'
    if re.search(r'offer|录用|embauche', text):
        return 'offer'
    if re.search(r'interview|entretien|面试', text):
        return 'interview'
    if re.search(r'respond|screening|reponse|回复|筛选', text):
        return 'screening'
    if re.search(r'withdrawn|retire|撤回', text):
        return 'withdrawn'
    if text in {'applied', 'submitted', 'envoye', '已投递', '已申请', '已发送'}:
        return 'submitted'
    return 'saved'


def parse_upload(name, content):
    if len(content) > 2_000_000:
        raise ValueError('Maximum import size is 2 MB')
    extension = name.lower().rsplit('.', 1)[-1]
    if extension == 'xlsx':
        return read_xlsx(content)
    text = content.decode('utf-8-sig')
    if extension == 'json':
        rows = json.loads(text)
        if isinstance(rows, dict):
            rows = rows.get('applications', rows.get('jobs', []))
    elif extension in {'md', 'markdown'}:
        lines = [line.strip().strip('|') for line in text.splitlines() if line.strip().startswith('|')]
        lines = [line for line in lines if not re.fullmatch(r'[\s|:-]+', line)]
        headers = [cell.strip() for cell in lines.pop(0).split('|')] if lines else []
        rows = [dict(zip(headers, [cell.strip() for cell in line.split('|')])) for line in lines]
    elif extension in {'csv', 'tsv'}:
        delimiter = '\t' if extension == 'tsv' else csv.Sniffer().sniff(text[:4096], delimiters=',;\t').delimiter
        rows = list(csv.DictReader(io.StringIO(text), delimiter=delimiter))
    else:
        raise ValueError('Use CSV, TSV, JSON, Markdown or XLSX')
    if not isinstance(rows, list) or len(rows) > 1000 or any(not isinstance(row, dict) for row in rows):
        raise ValueError('Expected at most 1000 application rows')
    return rows


def normalize(rows):
    result = []
    for index, source in enumerate(rows):
        values = {fold(key).strip(): value for key, value in source.items()}
        item = {key: str(next((values[alias] for alias in aliases if alias in values), '') or '').strip()[:4000]
                for key, aliases in ALIASES.items()}
        # Accept our native exports as well as Apply-Pilot's Markdown ledger.
        for key, native in [('stage', 'tracker_stage'), ('date', 'last_application_at'), ('note', 'tracker_note')]:
            if native in values:
                item[key] = str(values[native] or '')[:4000]
        item['stage'] = stage(item['stage'])
        item['row'] = index+1
        item['errors'] = []
        if not item['company'] or not item['title']:
            item['errors'].append('company_and_role_required')
        parsed = urlsplit(item['url'])
        internal_record = bool(re.fullmatch(r'ledger:[0-9a-f]{24}', item['url']))
        if item['url'] and not internal_record and (parsed.scheme != 'https' or not parsed.hostname or parsed.username or parsed.password):
            item['errors'].append('invalid_https_url')
        if item['stage'] != 'saved' and (not parsed_date(item['date']) or parsed_date(item['date']) > date.today()):
            item['errors'].append('submission_date_required')
        if not item['url']:
            key = hashlib.sha256((fold(item['company'])+'|'+fold(item['title'])).encode()).hexdigest()[:24]
            item['url'] = 'ledger:'+key  # Record identity, never a fake clickable job URL.
        result.append(item)
    return result


def preview(rows, existing=None):
    if existing is None:
        with connect() as conn:
            existing = [dict(row) for row in conn.execute('SELECT company,title,url FROM jobs')]
    known = list(existing)
    result = []
    for item in normalize(rows):
        duplicate = any(canonicalize_url(item['url']) == canonicalize_url(row.get('url') or '')
                        or (fold(item['company']) == fold(row.get('company')) and
                            SequenceMatcher(None, fold(item['title']), fold(row.get('title'))).ratio() >= .92)
                        for row in known)
        item['duplicate'] = duplicate
        if not item['errors'] and not duplicate:
            known.append(item)
        result.append(item)
    return result


def import_rows(rows):
    # Re-evaluate duplicates while holding the write transaction; no preview token races.
    from .repositories.jobs import JobRepository
    with connect() as conn:
        conn.execute('BEGIN IMMEDIATE')
        existing = [dict(row) for row in conn.execute('SELECT company,title,url FROM jobs')]
        items = preview(rows, existing)
        added = 0
        for item in items:
            if item['errors'] or item['duplicate']:
                continue
            key = build_job_dedupe_key(title=item['title'], company=item['company'], location=item['location'])
            job_id = conn.execute('''INSERT INTO jobs(url,canonical_url,dedupe_key,title,company,location,provider_key,source,
                      tracker_stage,tracker_source,tracker_note) VALUES(?,?,?,?,?,?,'ledger_import','Imported ledger','saved','manual',?)''',
                      (item['url'], canonicalize_url(item['url']), key, item['title'], item['company'], item['location'], item['note'])).lastrowid
            if item['stage'] != 'saved':
                note = 'Imported record: '+item['date']+' · '+item['note']
                repo = JobRepository()
                repo.track_in(conn, job_id, 'submitted', note, source='manual')
                if item['stage'] != 'submitted':
                    repo.track_in(conn, job_id, item['stage'], note, source='manual')
                conn.execute('UPDATE jobs SET last_application_at=? WHERE id=?', (item['date'], job_id))
            added += 1
    return {'added': added, 'duplicates': sum(row['duplicate'] for row in items),
            'invalid': sum(bool(row['errors']) for row in items)}


def export_rows(rows, format):
    columns = ['company', 'title', 'location', 'url', 'tracker_stage', 'last_application_at', 'tracker_note']
    def safe(value):
        value = str(value or '')
        return "'"+value if value.lstrip().startswith(('=', '+', '-', '@')) else value
    if format == 'json':
        return json.dumps([{key: row.get(key, '') for key in columns} for row in rows], ensure_ascii=False, indent=2).encode(), 'application/json'
    if format == 'xlsx':
        import xlsxwriter
        output = io.BytesIO()
        workbook = xlsxwriter.Workbook(output, {'in_memory':True,'strings_to_formulas':False,'strings_to_urls':False})
        sheet = workbook.add_worksheet('Candidatures')
        sheet.write_row(0,0,columns)
        for index,row in enumerate(rows,1):
            sheet.write_row(index,0,[str(row.get(key) or '') for key in columns])
        sheet.autofilter(0,0,len(rows),len(columns)-1)
        sheet.freeze_panes(1,0)
        sheet.set_column(0,len(columns)-1,28)
        workbook.close()
        return output.getvalue(), 'application/vnd.openxmlformats-officedocument.spreadsheetml.sheet'
    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(columns)
    writer.writerows([safe(row.get(key, '')) for key in columns] for row in rows)
    return ('\ufeff'+output.getvalue()).encode(), 'text/csv; charset=utf-8'

"""Native document tools, with Apply-Pilot's byte-preserving DOCX algorithm.

Templates and rendered versions are private candidate artifacts. Original CVs
are never edited. Compilation uses fixed toolchains, never a user shell command.
"""
from copy import deepcopy,copy
import hashlib
import html
import io
import json
import os
from pathlib import Path
import re
import shutil
import subprocess
import uuid
import zipfile
from . import capability_store as store


def archive_parts(content):
    if len(content)>8_000_000:raise ValueError('Template exceeds 8 MB')
    archive=zipfile.ZipFile(io.BytesIO(content))
    if len(archive.infolist())>300 or sum(x.file_size for x in archive.infolist())>32_000_000:
        archive.close();raise ValueError('Template archive too large')
    for entry in archive.infolist():
        path=Path(entry.filename)
        if path.is_absolute() or '..' in path.parts or ':' in entry.filename or '\\' in entry.filename or (entry.external_attr>>16)&0o170000==0o120000:
            archive.close();raise ValueError('Unsafe archive path')
    return archive


def paragraph_spans(xml):
    spans=[];stack=[]
    for match in re.finditer(r'<w:p(?=[\s>/])|</w:p>',xml):
        if match.group()=='</w:p>':
            if not stack:raise ValueError('Malformed DOCX paragraphs')
            stack.pop()['end']=match.end();continue
        close=xml.index('>',match.start())+1
        span={'start':match.start(),'end':close if xml[close-2:close]=='/>' else None}
        spans.append(span)
        if span['end'] is None:stack.append(span)
    if stack:raise ValueError('Malformed DOCX paragraphs')
    return spans


TEXT=re.compile(r'<w:t(?:\s[^>]*)?>(.*?)</w:t>|<w:t(?:\s[^>]*)?/>',re.S)


def docx_paragraphs(content):
    with archive_parts(content) as archive:xml=archive.read('word/document.xml').decode('utf-8')
    return [{'index':i,'text':''.join(html.unescape(m.group(1) or '') for m in TEXT.finditer(xml[span['start']:span['end']]))}
            for i,span in enumerate(paragraph_spans(xml))]


def build_docx(content,changes):
    with archive_parts(content) as source:
        xml=source.read('word/document.xml').decode('utf-8');spans=paragraph_spans(xml)
        indexes=sorted([int(key) for key in changes],reverse=True)
        if any(i<0 or i>=len(spans) for i in indexes):raise ValueError('Paragraph does not exist')
        selected=[spans[i] for i in indexes]
        if any(a['start']<b['start']<a['end'] or b['start']<a['start']<b['end'] for n,a in enumerate(selected) for b in selected[n+1:]):
            raise ValueError('Nested paragraph replacements overlap')
        for index in indexes:
            span=spans[index];segment=xml[span['start']:span['end']]
            values=changes.get(str(index),changes.get(index));values=values if isinstance(values,list) else [values]
            pieces=[]
            for number,value in enumerate(values):
                if not isinstance(value,str) or len(value)>20000:raise ValueError('Paragraph must contain bounded text')
                count=0
                def replace(match):
                    nonlocal count
                    count+=1
                    if count>1:return '<w:t></w:t>'
                    return '<w:br/>'.join('<w:t xml:space="preserve">'+html.escape(line,quote=False)+'</w:t>' for line in value.split('\n'))
                changed=TEXT.sub(replace,segment)
                if not count:raise ValueError('Paragraph has no text run')
                if number:changed=re.sub(r'\sw14:(?:paraId|textId)="[0-9a-fA-F]+"','',changed)
                pieces.append(changed)
            xml=xml[:span['start']]+''.join(pieces)+xml[span['end']:]
        output=io.BytesIO()
        with zipfile.ZipFile(output,'w') as target:
            for info in source.infolist():
                target.writestr(copy(info),xml.encode() if info.filename=='word/document.xml' else source.read(info.filename))
        result=output.getvalue()
        with zipfile.ZipFile(io.BytesIO(result)) as verify:
            for info in source.infolist():
                if info.filename!='word/document.xml' and source.read(info.filename)!=verify.read(info.filename):raise ValueError('An untouched DOCX part changed')
        return result


def register(name,content,label=''):
    if len(content)>8_000_000:raise ValueError('Template exceeds 8 MB')
    extension=Path(name).suffix.lower()
    if extension not in {'.docx','.tex','.typ','.zip','.pdf'}:raise ValueError('Use DOCX, TeX, Typst, ZIP or PDF')
    identifier=uuid.uuid4().hex[:16];directory=store.safe_file('templates/'+identifier);directory.mkdir(parents=True)
    metadata={'label':label or Path(name).stem,'original_name':Path(name).name,'tested':False,'sha256':hashlib.sha256(content).hexdigest()}
    if extension=='.zip':
        with archive_parts(content) as archive:
            for entry in archive.infolist():
                target=directory/entry.filename
                if entry.is_dir():target.mkdir(parents=True,exist_ok=True)
                else:target.parent.mkdir(parents=True,exist_ok=True);target.write_bytes(archive.read(entry.filename))
        manifest=directory/'template.json'
        custom=json.loads(manifest.read_text(encoding='utf-8')) if manifest.is_file() else {}
        candidates=[path for path in directory.rglob('*') if path.suffix in {'.tex','.typ'}]
        main=next((path for path in candidates if path.name in {'main.tex','main.typ'}),None)
        if custom:
            main=(directory/str(custom.get('entrypoint',''))).resolve()
            if not main.is_relative_to(directory.resolve()) or not main.is_file():raise ValueError('Invalid template entrypoint')
            command=custom.get('command')
            if not isinstance(command,list) or not 2<=len(command)<=30 or any(not isinstance(v,str) or len(v)>500 for v in command):raise ValueError('Template command must be a bounded argument list')
            if command[0] not in {'pandoc','tectonic','quarto','wkhtmltopdf'} or not any('{output}' in x for x in command):raise ValueError('Custom compiler must be pandoc, tectonic, quarto or wkhtmltopdf, with {output}')
            metadata.update(engine='custom',command=command,instructions=str(custom.get('instructions',''))[:4000],max_pages=max(1,min(2,int(custom.get('max_pages',2)))))
        if not main and len(candidates)==1:main=candidates[0]
        if not main:raise ValueError('Choose a single main.tex or main.typ in the template archive')
    else:
        main=directory/('template'+extension);main.write_bytes(content)
    metadata.update(path=str(main.relative_to(store.folder())),root=str(directory.relative_to(store.folder())),engine=metadata.get('engine') or {'.tex':'latex','.typ':'typst','.docx':'docx','.pdf':'pdf'}[main.suffix])
    if main.suffix=='.docx':docx_paragraphs(main.read_bytes());metadata['tested']=True
    if main.suffix=='.pdf':
        from pypdf import PdfReader
        PdfReader(main);metadata['tested']=True
    store.save_item(identifier,'template',metadata)
    return {'id':identifier,**metadata}


def template_root(metadata):
    source=store.safe_file(metadata['path'])
    relative=source.relative_to(store.folder())
    root=store.safe_file(metadata.get('root') or str(Path(*relative.parts[:2])))
    if root.parent!=(store.folder()/'templates').resolve() or not source.is_relative_to(root):raise ValueError('Invalid registered template root')
    return root


def compile_template(template_id,output,values=None):
    from .worker_runtime import check_cancelled
    metadata=store.item(template_id,'template')
    if not metadata:raise KeyError(template_id)
    original=store.safe_file(metadata['path'])
    root=template_root(metadata)
    output=Path(output);output.parent.mkdir(parents=True,exist_ok=True)
    if metadata['engine']=='pdf':shutil.copy2(original,output);return output
    if metadata['engine']=='docx':raise ValueError('Use paragraph replacement to build this DOCX template')
    build=output.parent/'compile';build.mkdir(exist_ok=True)
    if build.resolve().is_relative_to(root):raise ValueError('Compile into a separate task folder')
    shutil.copytree(root,build,dirs_exist_ok=True)
    main=build/original.relative_to(root);text=main.read_text(encoding='utf-8')
    for key,value in (values or {}).items():
        if not re.fullmatch('[A-Z_]{1,30}',key):raise ValueError('Invalid template field')
        if metadata['engine']=='latex':
            replacements={'\\':r'\textbackslash{}','&':r'\&','%':r'\%','$':r'\$','#':r'\#','_':r'\_','{':r'\{','}':r'\}','~':r'\textasciitilde{}','^':r'\textasciicircum{}'}
            escaped=''.join(replacements.get(char,char) for char in str(value))
        elif metadata['engine']=='typst':escaped='#text('+json.dumps(str(value),ensure_ascii=False)+')'
        else:escaped=str(value)
        text=text.replace('['+key+']',escaped)
    main.write_text(text,encoding='utf-8')
    if metadata['engine']=='custom':
        exe=shutil.which(metadata['command'][0])
        if not exe:raise ValueError('Install '+metadata['command'][0]+' before compiling this template')
        if Path(exe).suffix.lower() in {'.cmd','.bat'}:raise ValueError('Use the native compiler executable, not a shell wrapper')
        result_file=build/'result.pdf'
        command=[exe]+[value.replace('{source}',str(main)).replace('{output}',str(result_file)).replace('{root}',str(build))
                       for value in metadata['command'][1:]]
    elif metadata['engine']=='typst':
        exe=shutil.which('typst')
        if not exe:raise ValueError('Install Typst, then test this template again')
        command=[exe,'compile','--root',str(build),str(main),str(build/'result.pdf')]
        result_file=build/'result.pdf'
    else:
        exe=next((shutil.which(name) for name in ('xelatex','lualatex','pdflatex') if shutil.which(name)),None)
        if not exe:raise ValueError('Install a LaTeX compiler, then test this template again')
        command=[exe,'-no-shell-escape','-interaction=nonstopmode','-halt-on-error',str(main.relative_to(build))]
        result_file=build/(main.stem+'.pdf')
    check_cancelled()
    result=subprocess.run(command,cwd=build,env={**os.environ,'openin_any':'p','openout_any':'p'},capture_output=True,timeout=45,
                          creationflags=subprocess.CREATE_NO_WINDOW if os.name=='nt' else 0)
    (build/'compile.log.txt').write_bytes(result.stdout[-100000:]+result.stderr[-100000:])
    if result.returncode or not result_file.exists():raise ValueError('Template compilation failed; see its local compile log')
    shutil.copy2(result_file,output)
    metadata['tested']=True;store.save_item(template_id,'template',{key:value for key,value in metadata.items() if key!='id'})
    return output


def pdf_report(path,required=(),max_pages=2):
    from .vendor.job_search.verify_pdf import verify_pdf,normalize_text
    from pypdf import PdfReader
    engine,text,count=verify_pdf(path,min_chars=20,required_text=required)
    warnings=[];pages=[]
    from .vendor.job_search import verify_layout
    advanced={'available':bool(verify_layout.find_pdftotext()),'warnings':[]}
    if advanced['available']:
        try:
            import contextlib
            with contextlib.redirect_stdout(io.StringIO()):advanced['warnings']=verify_layout.report(Path(path),verify_layout.parse_pdf(Path(path)))
            warnings.extend(advanced['warnings'])
        except Exception as exc:advanced['error']=type(exc).__name__
    for number,page in enumerate(PdfReader(path).pages,1):
        rows=[]
        def visit(value,cm,tm,font,size):
            if value.strip():rows.append({'text':value.strip(),'x':tm[4]*cm[0]+tm[5]*cm[2]+cm[4],
                                         'y':tm[4]*cm[1]+tm[5]*cm[3]+cm[5],'size':size})
        page.extract_text(visitor_text=visit)
        height=float(page.mediabox.height)
        if any(row['size']<8 for row in rows):warnings.append(f'page {number}: small font')
        if any(row['y']<18 or row['y']>height-10 for row in rows):warnings.append(f'page {number}: text near page edge')
        ys=sorted({round(row['y']) for row in rows if 35<row['y']<height-35},reverse=True)
        if any(a-b>150 for a,b in zip(ys,ys[1:])):warnings.append(f'page {number}: large blank gap')
        pages.append({'page':number,'text_rows':len(rows),'lowest_y':min(ys) if ys else None})
    if count>max_pages:warnings.append('page limit exceeded')
    return {'pages':count,'text_characters':len(text),'extractor':engine,'warnings':warnings,'layout':pages,'advanced_layout':advanced,
            'text':text,'passed':count<=max_pages and not any('small font' in x or 'page edge' in x for x in warnings)}


def render_cv(document,path,job=None,letter=''):
    from reportlab.platypus import SimpleDocTemplate,Paragraph,Spacer,KeepTogether
    from reportlab.lib.styles import getSampleStyleSheet,ParagraphStyle
    from reportlab.lib.pagesizes import A4
    from .resume_matcher import tokens
    styles=getSampleStyleSheet();styles.add(ParagraphStyle(name='CVText',fontName='Helvetica',fontSize=10.5,leading=14,spaceAfter=5))
    sections=deepcopy(document.get('sections',[]));removed=[]
    if not sections:raise ValueError('CV requires sections')
    def build():
        flow=[Paragraph(html.escape(str(document.get('name',''))),styles['Title'])]
        if document.get('contact'):flow.append(Paragraph(html.escape(str(document['contact'])),styles['CVText']))
        for section in sections:
            entries=section.get('lines',[])
            if not entries:continue
            heading=Paragraph(html.escape(str(section.get('heading',''))),styles['Heading2'])
            flow.append(KeepTogether([heading,Paragraph(html.escape(str(entries[0]['text'])),styles['CVText'])]))
            flow.extend(Paragraph(html.escape(str(entry['text'])),styles['CVText']) for entry in entries[1:])
        SimpleDocTemplate(str(path),pagesize=A4,leftMargin=42,rightMargin=42,topMargin=36,bottomMargin=36).build(flow)
    target=tokens(' '.join(str((job or {}).get(key) or '') for key in ('title','body')))
    for attempt in range(35):
        build();report=pdf_report(path,[document.get('name','')],2)
        if report['pages']<=2:return {**report,'removed_lines':removed}
        candidates=[]
        for section in sections:
            for index,line in enumerate(section.get('lines',[])):
                if line.get('protected') or len(section['lines'])<=1:continue
                content=tokens(line['text']);relevance=len(content&target)
                uniqueness=1/(1+sum(line['text']==other['text'] for group in sections for other in group.get('lines',[])))
                dependency=5 if line['text'] and line['text'] in letter else 0
                candidates.append((relevance+uniqueness+dependency,section,index,line))
        if not candidates:break
        _,section,index,line=min(candidates,key=lambda row:row[0]);removed.append(line);section['lines'].pop(index)
    raise ValueError('CV cannot fit two pages without removing protected facts; revise the content')

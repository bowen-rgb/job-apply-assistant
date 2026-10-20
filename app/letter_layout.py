"""Fixed, readable French A4 correspondence; overflow is an error, never a smaller font."""
from datetime import datetime
from pathlib import Path
from xml.sax.saxutils import escape
from zoneinfo import ZoneInfo

from reportlab.lib import colors
from reportlab.lib.enums import TA_RIGHT
from reportlab.lib.pagesizes import A4
from reportlab.lib.styles import ParagraphStyle
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from pypdf import PdfReader


def correspondence(job, raw, body, today=None):
    identity = raw.get('identity', {})
    name = ' '.join(str(identity.get(k) or '').strip() for k in ('first_name', 'last_name')).strip()
    if not name:
        raise ValueError('Complétez le nom du candidat avant de générer la lettre.')
    city = str(identity.get('city') or '').strip()
    sender = [name, str(identity.get('address_line1') or '').strip(),
              ' '.join(str(identity.get(k) or '').strip() for k in ('postal_code', 'city')).strip(),
              str(identity.get('country') or '').strip(), str(identity.get('phone') or '').strip(),
              str(identity.get('email') or '').strip()]
    # Vacancy location is not a confirmed postal address of the employer.
    recipient = ['À l’attention de l’équipe de recrutement', str(job.get('company') or '').strip()]
    stamp = (today or datetime.now(ZoneInfo('Europe/Paris')).date()).strftime('%d/%m/%Y')
    dateline = f'{city}, le {stamp}' if city else f'Le {stamp}'
    title = str(job.get('title') or '').strip()
    if not title:
        raise ValueError('Le poste doit être identifié avant de générer la lettre.')
    subject = 'Objet : Candidature — ' + title
    greeting = 'Madame, Monsieur,'
    closing = 'Je vous remercie de l’attention portée à ma candidature et vous prie d’agréer, Madame, Monsieur, mes salutations distinguées.'
    return {'sender': [s for s in sender if s], 'recipient': [r for r in recipient if r],
            'date': dateline, 'subject': subject, 'greeting': greeting, 'body': body,
            'closing': closing, 'signature': name, 'attachment': 'Pièce jointe : CV',
            'inline': '\n\n'.join([subject, greeting, body, closing, name])}


def render_pdf(path, document):
    normal = ParagraphStyle('LetterBody', fontName='Helvetica', fontSize=11, leading=15,
                            spaceAfter=10, firstLineIndent=0, textColor=colors.HexColor('#202020'))
    contact = ParagraphStyle('Contact', parent=normal, fontSize=10, leading=13, spaceAfter=0)
    right = ParagraphStyle('Right', parent=contact, alignment=TA_RIGHT)
    subject = ParagraphStyle('Subject', parent=normal, fontName='Helvetica-Bold')
    def paragraph(text, style=normal):
        return Paragraph(escape(text), style)
    def lines(items, style):
        return Paragraph('<br/>'.join(escape(text) for text in items), style)
    width = A4[0] - 104
    header = Table([[lines(document['sender'], contact), lines(document['recipient'], right)]],
                   colWidths=[width * .52, width * .48])
    header.setStyle(TableStyle([('VALIGN',(0,0),(-1,-1),'TOP'),
                               ('LEFTPADDING',(0,0),(-1,-1),0), ('RIGHTPADDING',(0,0),(-1,-1),0),
                               ('TOPPADDING',(0,0),(-1,-1),0), ('BOTTOMPADDING',(0,0),(-1,-1),0)]))
    story = [header, Spacer(1,12), paragraph(document['date'],right), Spacer(1,16),
             paragraph(document['subject'], subject), Spacer(1,3), paragraph(document['greeting'])]
    story += [paragraph(part.strip()) for part in document['body'].split('\n\n') if part.strip()]
    story += [paragraph(document['closing']), paragraph(document['signature'],right),
              Spacer(1,8), paragraph(document['attachment'],contact)]
    SimpleDocTemplate(str(path), pagesize=A4, leftMargin=52, rightMargin=52,
                      topMargin=44, bottomMargin=44, title=document['subject'],
                      author=document['signature']).build(story)
    if len(PdfReader(path).pages) != 1:
        Path(path).unlink(missing_ok=True)
        raise ValueError('La lettre dépasse une page A4. Raccourcissez le texte ; la taille de police reste inchangée.')

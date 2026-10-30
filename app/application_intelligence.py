"""Application bookkeeping, adapted from Apply-Pilot's MIT algorithms.

See docs/third-party/INTEGRATION.md for pinned sources and intentional changes.
These diagnostics never send applications, infer skills or edit a CV.
"""
from datetime import date, datetime, timedelta, timezone
import math
import re
import unicodedata


def fold(value):
    return ''.join(c for c in unicodedata.normalize('NFKD', str(value or ''))
                   if not unicodedata.combining(c)).casefold()


def has_term(text, term):
    term = fold(term).strip()
    return bool(term and re.search(r'(?<!\w)' + re.escape(term) + r'(?!\w)', fold(text)))


# Apply-Pilot events.mjs: distinguish receipts, real responses, and preparation.
# French rules are stricter than broad "regret" / "another candidate" matches.
SIGNALS = (
    ('rejected', r'not (?:been )?(?:selected|retained)|not (?:be )?moving forward|moving forward with other candidates|unable to (?:offer|proceed)|application.{0,35}unsuccessful|candidature.{0,60}(?:pas (?:ete )?retenue|non retenue|suite defavorable)|ne (?:pouvons|donnerons).{0,35}suite (?:favorable|a votre candidature)|position has been filled|poste (?:a ete )?pourvu|未录用|未被录用|未进入下一轮|拒绝.*申请'),
    ('offer', r'pleased to offer you|extend (?:you )?an offer|offer letter|proposition d.embauche|proposons.{0,30}(?:poste|contrat)|录用通知|收到.?offer'),
    ('interview', r'(?:invite|schedule|arrange|confirm).{0,50}(?:interview|call)|(?:invitation|convocation).{0,40}entretien|(?:proposons|invitons).{0,40}entretien|online assessment|coding challenge|面试邀请|邀请.{0,10}面试'),
    ('screening', r'(?:request|provide|send).{0,35}(?:transcript|additional information|availability)|(?:merci de|pourriez.vous).{0,35}(?:transmettre|fournir|disponibilites)|要求补充|补充材料'),
    ('ack', r'(?:received|receiving) your application|application (?:received|confirmation)|accuse de reception|merci (?:pour|de).{0,12}(?:candidature|postule)|candidature.{0,30}(?:bien recue|prise en compte)|收件确认|已收到.{0,12}申请'),
)


def new_message_text(text):
    return re.split(r'(?im)^\s*(?:On .+wrote:|Le .+ecrit\s*:|From:|De\s*:|>{1,})', str(text))[0][:9000]


def classify_response(text):
    """Classify the new message only. Conflicting signals always need a person."""
    opening = new_message_text(text)
    if re.search(r'out of (?:the )?office|absence du bureau|reponse automatique|automatic reply', fold(opening)):
        return {'signal': 'autoreply', 'evidence': ''}
    hits = []
    for signal, pattern in SIGNALS:
        match = re.search(pattern, fold(opening), re.S)
        if match:
            prefix = fold(opening)[max(0, match.start()-35):match.start()]
            if re.search(r'\b(?:if|unless|not|never)\s*$', prefix):
                continue
            hits.append((signal, match.group(0)[:240]))
    strong = [hit for hit in hits if hit[0] not in {'ack', 'screening'}]
    if len(strong) > 1:
        return {'signal': 'conflict', 'evidence': ' / '.join(hit[1] for hit in strong)}
    signal, evidence = (strong or hits or [('unknown', '')])[0]
    return {'signal': signal, 'evidence': evidence}


def parsed_date(value):
    try:
        return datetime.fromisoformat(str(value).replace('Z', '+00:00')).date()
    except (ValueError, TypeError):
        return None


def followup_status(job, events, rules=None, today=None):
    """Port of followups.mjs, using structured events rather than note inference."""
    rules = rules or {}
    today = today or date.today()
    if job.get('application_status') not in {'submitted', 'submitted_verified'}:
        return None
    if job.get('tracker_stage') in {'rejected', 'withdrawn', 'offer', 'interview'}:
        return None
    sent = sum(event.get('kind') == 'followup_sent' for event in events)
    dates = [parsed_date(job.get('last_application_at'))]
    dates += [parsed_date(event.get('occurred_at') or event.get('created_at')) for event in events
              if event.get('kind') in {'followup_sent', 'response', 'ack'} or event.get('source') in {'email', 'phone', 'recruiter_portal'}]
    dates = [value for value in dates if value]
    if not dates:
        return {'job_id': job['id'], 'due': False, 'reason': 'missing_submission_date'}
    last = max(dates)
    explicit = parsed_date(job.get('next_followup_at'))
    delay = max(1, min(90, int(rules.get('after_days', 14))))
    limit = max(0, min(10, int(rules.get('max_followups', 1))))
    due_at = explicit or last + timedelta(days=delay)
    return {'job_id': job['id'], 'due': today >= due_at and sent < limit,
            'due_at': due_at.isoformat(), 'last_activity': last.isoformat(),
            'silent_days': max(0, (today-last).days), 'sent_count': sent,
            'channel': 'email' if job.get('tracker_source') == 'email' else 'portal'}


def score_evaluation(dimensions, ratings, thresholds=None):
    """Apply-Pilot scoring.mjs: deterministic weighted 0–5 rubric, strict input."""
    if not dimensions or len(dimensions) > 20:
        raise ValueError('Configure 1–20 scoring dimensions')
    total = weights = 0
    parts = []
    seen = set()
    for dim in dimensions:
        key = str(dim['id'])
        if key in seen:
            raise ValueError('Duplicate dimension')
        seen.add(key)
        raw = ratings.get(key)
        value = raw.get('score') if isinstance(raw, dict) else raw
        weight = dim.get('weight')
        if (isinstance(value, bool) or not isinstance(value, (int, float)) or not math.isfinite(value)
                or not 0 <= value <= 5 or isinstance(weight, bool) or not isinstance(weight, (int, float))
                or not math.isfinite(weight) or weight < 0):
            raise ValueError('Every rating must be 0–5 and weights must be finite and nonnegative')
        total += value / 5 * weight
        weights += weight
        parts.append({'id': key, 'label': dim.get('label', key), 'weight': weight,
                      'rating': value, 'reason': str(raw.get('reason', ''))[:1000] if isinstance(raw, dict) else ''})
    if weights <= 0:
        raise ValueError('Weights must total more than zero')
    score = math.floor(total / weights * 100 + .5)
    thresholds = thresholds or {'apply': 80, 'consider': 65}
    apply, consider = thresholds.get('apply', 80), thresholds.get('consider', 65)
    if not 0 <= consider <= apply <= 100:
        raise ValueError('Invalid score thresholds')
    return {'score': score, 'decision': 'apply' if score >= apply else 'consider' if score >= consider else 'skip', 'parts': parts}


def keyword_coverage(keywords, text):
    """Port of keywords.mjs; a diagnostic, never permission to invent experience."""
    present, thin, missing = [], [], []
    for term in dict.fromkeys(str(x).strip() for x in keywords if str(x).strip()):
        pattern = re.escape(fold(term))
        pattern = re.sub(r'(?:\\ |\-)+', r'[\\s-]+', pattern)
        count = len(re.findall(r'(?<!\w)' + pattern + r'(?:s|es)?(?!\w)', fold(text)))
        if count:
            present.append(term)
            if count == 1:
                thin.append(term)
        else:
            missing.append(term)
    total = len(present) + len(missing)
    return {'total': total, 'coverage_pct': math.floor(len(present)/total*100+.5) if total else 0,
            'present': present, 'thin': thin, 'missing': missing}


def interview_pack(job, profile, evidence):
    """Grounded preparation framework inspired by /interview, without invented answers."""
    return {'company': job.get('company', ''), 'role': job.get('title', ''), 'source': job.get('url', ''),
            'role_text': (job.get('body') or job.get('snippet') or '')[:16000],
            'candidate_evidence': evidence[:6],
            'questions': [
                'Quelle mission du poste vous intéresse et pourquoi ?',
                'Quel projet réel montre votre contribution personnelle ? Décrivez situation, tâche, action et résultat.',
                'Quelle limite ou difficulté avez-vous rencontrée et comment l’avez-vous vérifiée ?',
                'Quelles compétences devez-vous encore approfondir ?',
            ],
            'ask_employer': ['Quelles seront les missions des premières semaines ?',
                             'Qui encadrera le stage et comment seront évalués les résultats ?',
                             'Les dates, la durée et le lieu correspondent-ils à mes contraintes ?'],
            'availability': profile.get('availability', {}),
            'instruction': 'Préparez vos réponses à partir des faits ci-dessus. Ne transformez pas les questions en expériences acquises.'}

"""Review strong matches before enqueueing; never opens application forms."""
import json
import hashlib
import sys
from contextlib import nullcontext
from datetime import datetime, timezone
from filelock import FileLock, Timeout

from .db import connect
from .workspaces import data_dir
from .profile_store import load_profile_raw
from .human_review import automatic_ready, automatic_token
from .automatic_review import CONTENT
from .reviewer import review_via_chatgpt_web

MODULE = 'app.match_review'


def candidates(include_skip=False, *, connection=None):
    with nullcontext(connection) if connection is not None else connect() as conn:
        return [dict(row) for row in conn.execute("""SELECT j.* FROM jobs j
            WHERE decision='keep' AND user_action<>'skipped' AND human_review_status<>'declined'
            AND application_status NOT IN ('submitted','submitted_verified','withdrawn','opening','preparing','preparing_letter')
            AND tracker_stage NOT IN ('rejected','withdrawn','hired','offer_declined','no_response')
            AND availability_status<>'expired' AND review_verdict NOT IN ('QUEUED','RUNNING')
            AND (? OR review_verdict<>'SKIP')
            AND NOT EXISTS (SELECT 1 FROM application_queue q WHERE q.job_id=j.id)
            ORDER BY score DESC,id""", (int(include_skip),))]


def save(state):
    path=data_dir()/'match-review.json';path.parent.mkdir(parents=True,exist_ok=True)
    state['updated_at']=datetime.now(timezone.utc).isoformat()
    temporary=path.with_suffix('.tmp')
    temporary.write_text(json.dumps(state,ensure_ascii=False),encoding='utf-8')
    temporary.replace(path)


def saved_state():
    path=data_dir()/'match-review.json'
    return json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'phase':'idle'}


def scope_token():
    return hashlib.sha256(json.dumps(load_profile_raw(),sort_keys=True,ensure_ascii=False).encode()).hexdigest()


def action_candidates(mode, rows=None, *, actions=None):
    rows = candidates() if rows is None else rows
    if mode == 'clarify':  # Compatibility with a previous Dashboard still open.
        return [row for row in rows if row['review_verdict'] == 'HUMAN_REVIEW']
    from .review_gaps import snapshot
    actions = snapshot()['actions'] if actions is None else actions
    if mode in {'research', 'rereview'}:
        key = 'public_research' if mode == 'research' else 'rereview'
        ids = set(actions[key]['job_ids'])
        return [row for row in rows if row['id'] in ids]
    ready = set(actions['rereview']['job_ids'])
    return [row for row in rows if row['review_verdict'] != 'HUMAN_REVIEW' or row['id'] in ready]


def status():
    state=saved_state()
    from .worker_runtime import is_running
    if state['phase'] in {'running','starting'} and not is_running(MODULE,0):
        state={**state,'phase':'interrupted'}
    from .review_inventory import snapshot
    from .review_gaps import snapshot as gap_snapshot
    # Stage cards, lifetime totals, gap lists and action targets share one SQLite read snapshot.
    with connect() as conn:
        conn.execute('BEGIN')
        rows=candidates(connection=conn)
        inventory=snapshot(connection=conn)
        gaps=gap_snapshot(connection=conn)
    actions = gaps['actions']
    snapshot_id=hashlib.sha256(json.dumps([inventory,gaps],sort_keys=True,ensure_ascii=False).encode()).hexdigest()
    return {**{k:v for k,v in state.items() if k not in {'processed','scope','targets'}},'eligible':len(rows),
            'unresolved_available':inventory['counts']['needs_information'],'inventory':inventory,
            'actions':actions,'gaps':gaps,'snapshot_id':snapshot_id,
            'review_available':len(action_candidates('strong',rows,actions=actions))}


def start(unresolved_only=False, *, mode=None):
    from .worker_runtime import launch, any_running, is_running
    from .browser_control import require_connection, status as browser_status, start as start_browser
    from .profile_store import runtime_profile
    from .workspaces import LOCK
    with LOCK:
        if is_running(MODULE,0):return status()
        from .scan_manager import status as scan_status
        if scan_status().get('running'):
            raise ValueError('Wait for the current scan to finish before reviewing matches')
        if any_running(include_handoffs=False):
            raise ValueError('Une tâche est déjà en cours. Attendez sa fin avant de lancer la revue.')
        mode=mode or ('clarify' if unresolved_only else 'strong')
        if mode not in {'strong','clarify','research','rereview'}:
            raise ValueError('Unknown review action')
        previous=saved_state()
        # No worker owns this state (checked above). A host exit may leave RUNNING
        # on disk after approval but before queue admission; preserve its targets.
        if previous.get('phase') in {'running','starting'}:
            previous={**previous,'phase':'interrupted'}
        resume=(previous.get('scope')==scope_token() and previous.get('mode','strong')==mode
                and previous.get('phase') in {'blocked','stopped','interrupted'})
        rows=candidates()
        if mode != 'strong' and resume:
            rows=[row for row in rows if row['id'] in previous.get('targets',[])]
        else:
            rows=action_candidates(mode,rows)
        if not rows:
            save({'phase':'done','mode':mode,'total':0,'completed':0,'enqueued':0,'skipped':0,'unresolved':0})
            return status()
        profile=runtime_profile()
        if profile.get('chatgpt_web_reviewer',{}).get('enabled') is False:
            raise ValueError('Enable the ChatGPT reviewer before starting automatic review')
        if profile.get('chatgpt_web_reviewer',{}).get('backend','chatgpt')=='chatgpt':
            if not browser_status(profile).get('ready'):start_browser(profile)
            require_connection(profile)
        if resume:
            previous.update(phase='starting');previous.pop('error',None);save(previous)
        else:
            save({'phase':'starting','mode':mode,'targets':[row['id'] for row in rows] if mode != 'strong' else [],
                  'total':len(rows),'completed':0,'enqueued':0,'skipped':0,'unresolved':0})
        launch(MODULE,0)
        return status()


def review_one(job):
    from .worker_runtime import check_cancelled
    if automatic_ready(job):
        return 'APPLY'
    profile=load_profile_raw()
    content=[job.get(key) for key in CONTENT]
    for attempt in range(2):
        check_cancelled()
        if attempt:
            # Repeating the identical packet cannot resolve missing public facts.
            from .review_research import collect
            collect(job)
        result=review_via_chatgpt_web(job['id'])
        if result['verdict']!='HUMAN_REVIEW':break
        blockers = result.get('blockers') or []
        if blockers and all(b.get('kind') in {'candidate','form'} for b in blockers):
            # Public research cannot invent a personal fact or legal declaration.
            break
    check_cancelled()
    with connect() as conn:
        current=dict(conn.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone())
        eligible=any(row['id']==job['id'] for row in candidates(include_skip=True))
        if (not eligible or content!=[current.get(key) for key in CONTENT]
                or profile!=load_profile_raw()):
            raise ValueError('Posting, profile or application state changed during review')
        if result['verdict']=='APPLY' and current['review_verdict']=='APPLY':
            conn.execute('UPDATE jobs SET automatic_review_token=? WHERE id=?',(automatic_token(current),job['id']))
            return 'APPLY'
    return result['verdict']


def run():
    from .worker_runtime import check_cancelled, Cancelled
    from .queue_manager import enqueue
    previous=saved_state()
    scope=scope_token()
    resume=previous.get('scope')==scope and previous.get('phase') in {'starting','blocked','stopped','interrupted'}
    processed=previous.get('processed',{}) if resume else {}
    mode=previous.get('mode','strong')
    rows=[job for job in candidates() if processed.get(str(job['id']))!=automatic_token(job)]
    if mode in {'clarify','research','rereview'}:
        rows=[job for job in rows if job['id'] in previous.get('targets',[])]
    else:
        rows=action_candidates(mode,rows)
    counts={key:previous.get(key,0) if resume else 0 for key in ['completed','enqueued','skipped','unresolved']}
    state={'phase':'running','mode':previous.get('mode','strong'),'targets':previous.get('targets',[]),
           'continued_from_clarify':previous.get('continued_from_clarify',False),
           'total':counts['completed']+len(rows),**counts,'processed':processed,'scope':scope}
    save(state)
    try:
        for job in rows:
            check_cancelled()
            state.update(current_job_id=job['id'],current_title=job['title'],company=job['company'])
            save(state)
            verdict=review_one(job)
            if verdict=='APPLY':
                enqueue([job['id']])
                with connect() as conn:
                    queued=conn.execute('SELECT 1 FROM application_queue WHERE job_id=?',(job['id'],)).fetchone()
                state['enqueued']+=int(bool(queued))
            elif verdict=='SKIP':state['skipped']+=1
            else:state['unresolved']+=1
            with connect() as conn:
                current=dict(conn.execute('SELECT * FROM jobs WHERE id=?',(job['id'],)).fetchone())
            processed[str(job['id'])]=automatic_token(current)
            state['completed']+=1;save(state)
            if state['mode']=='clarify' and job is rows[-1]:
                # Clarifying twenty old records must not strand the unreviewed remainder.
                remaining=[row for row in candidates() if row['review_verdict'] in {'','ERROR'}
                           and str(row['id']) not in processed]
                if remaining:
                    state.update(mode='strong',continued_from_clarify=True,targets=[],
                                 total=state['completed']+len(remaining))
                    rows.extend(remaining);save(state)
        state['phase']='done'
    except Cancelled:
        state['phase']='stopped'
    except Exception as exc:
        # Login / transport / parsing failure pauses the batch once, not 110 retries.
        state.update(phase='blocked',error=str(exc)[:1000])
        with connect() as conn:
            conn.execute("UPDATE jobs SET review_verdict='ERROR',review_summary=? WHERE id=? AND review_verdict IN ('QUEUED','RUNNING')",
                         (state['error'],state.get('current_job_id')))
    finally:
        if state['phase']=='stopped':
            with connect() as conn:
                conn.execute("UPDATE jobs SET review_verdict='ERROR',review_summary='Automatic review stopped; retry to continue' WHERE id=? AND review_verdict IN ('QUEUED','RUNNING')",(state.get('current_job_id'),))
        state.pop('current_job_id',None);save(state)


def after_scan(profile):
    if not profile.get('review_and_queue_strong'):return
    try:start()
    except ValueError as exc:save({'phase':'blocked','error':str(exc)[:1000]})


if __name__=='__main__':
    try:
        with FileLock(str(data_dir()/'strong-review.lock'),timeout=0):run()
    except Timeout:sys.exit(0)

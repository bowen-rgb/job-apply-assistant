"""Review strong matches before enqueueing; never opens application forms."""
import json
import sys
from datetime import datetime, timezone
from filelock import FileLock, Timeout

from .db import connect
from .workspaces import data_dir
from .profile_store import load_profile_raw
from .human_review import automatic_ready, automatic_token
from .automatic_review import CONTENT
from .reviewer import review_via_chatgpt_web

MODULE = 'app.match_review'


def candidates(include_skip=False):
    with connect() as conn:
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


def status():
    path=data_dir()/'match-review.json'
    state=json.loads(path.read_text(encoding='utf-8')) if path.exists() else {'phase':'idle'}
    from .worker_runtime import is_running
    if state['phase'] in {'running','starting'} and not is_running(MODULE,0):
        state={**state,'phase':'interrupted'}
    return {**state,'eligible':len(candidates())}


def start():
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
        rows=candidates()
        if not rows:
            save({'phase':'done','total':0,'completed':0,'enqueued':0,'skipped':0,'unresolved':0})
            return status()
        profile=runtime_profile()
        if profile.get('chatgpt_web_reviewer',{}).get('enabled') is False:
            raise ValueError('Enable the ChatGPT reviewer before starting automatic review')
        if profile.get('chatgpt_web_reviewer',{}).get('backend','chatgpt')=='chatgpt':
            if not browser_status(profile).get('ready'):start_browser(profile)
            require_connection(profile)
        save({'phase':'starting','total':len(rows),'completed':0,'enqueued':0,'skipped':0,'unresolved':0})
        launch(MODULE,0)
        return status()


def review_one(job):
    from .worker_runtime import check_cancelled
    if automatic_ready(job):
        return 'APPLY'
    profile=load_profile_raw()
    content=[job.get(key) for key in CONTENT]
    for _ in range(2):
        check_cancelled()
        result=review_via_chatgpt_web(job['id'])
        if result['verdict']!='HUMAN_REVIEW':break
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
    rows=candidates()
    state={'phase':'running','total':len(rows),'completed':0,'enqueued':0,'skipped':0,'unresolved':0}
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
            state['completed']+=1;save(state)
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

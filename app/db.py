import sqlite3
from pathlib import Path
from contextlib import contextmanager

DB_PATH = Path(__file__).resolve().parent.parent / 'data' / 'jobs.db'

SCHEMA = '''
CREATE TABLE IF NOT EXISTS jobs (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  url TEXT UNIQUE,
  canonical_url TEXT DEFAULT '',
  fingerprint TEXT DEFAULT '',
  dedupe_key TEXT DEFAULT '',
  source_variants_json TEXT DEFAULT '[]',
  search_profile_id TEXT DEFAULT '',
  search_profile_label TEXT DEFAULT '',
  title TEXT,
  company TEXT,
  location TEXT,
  source TEXT,
  provider_key TEXT DEFAULT '',
  ats TEXT DEFAULT '',
  snippet TEXT,
  body TEXT,
  employment_type TEXT DEFAULT '',
  start_date TEXT DEFAULT '',
  end_date TEXT DEFAULT '',
  date_posted TEXT DEFAULT '',
  valid_through TEXT DEFAULT '',
  salary TEXT DEFAULT '',
  structured_json TEXT DEFAULT '',
  fetch_mode TEXT DEFAULT '',
  availability_status TEXT DEFAULT 'unknown',
  decision TEXT DEFAULT 'new',
  user_action TEXT DEFAULT '',
  application_status TEXT DEFAULT '',
  apply_adapter TEXT DEFAULT '',
  fill_audit_path TEXT DEFAULT '',
  agent_status TEXT DEFAULT '',
  agent_steps INTEGER DEFAULT 0,
  agent_trace_path TEXT DEFAULT '',
  last_application_at TEXT DEFAULT '',
  tracker_stage TEXT DEFAULT '',
  tracker_note TEXT DEFAULT '',
  next_followup_at TEXT DEFAULT '',
  score INTEGER DEFAULT 0,
  reason TEXT DEFAULT '',
  review_verdict TEXT DEFAULT '',
  review_confidence INTEGER DEFAULT 0,
  review_summary TEXT DEFAULT '',
  review_json TEXT DEFAULT '',
  reviewed_at TEXT DEFAULT '',
  discovered_at TEXT DEFAULT CURRENT_TIMESTAMP,
  first_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_seen_at TEXT DEFAULT CURRENT_TIMESTAMP,
  last_checked_at TEXT DEFAULT CURRENT_TIMESTAMP,
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP
);
CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint);
CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key);
CREATE INDEX IF NOT EXISTS idx_jobs_canonical_url ON jobs(canonical_url);
CREATE INDEX IF NOT EXISTS idx_jobs_decision ON jobs(decision);
CREATE INDEX IF NOT EXISTS idx_jobs_review ON jobs(review_verdict);
CREATE INDEX IF NOT EXISTS idx_jobs_tracker_stage ON jobs(tracker_stage);
CREATE INDEX IF NOT EXISTS idx_jobs_search_profile ON jobs(search_profile_id);

CREATE TABLE IF NOT EXISTS applications (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER,
  status TEXT,
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(job_id) REFERENCES jobs(id)
);

CREATE TABLE IF NOT EXISTS application_queue (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER UNIQUE,
  status TEXT DEFAULT 'queued',
  priority INTEGER DEFAULT 100,
  attempts INTEGER DEFAULT 0,
  resume_id TEXT DEFAULT '',
  note TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  started_at TEXT DEFAULT '',
  finished_at TEXT DEFAULT '',
  updated_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE INDEX IF NOT EXISTS idx_application_queue_status ON application_queue(status,priority,id);

CREATE TABLE IF NOT EXISTS application_stage_events (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  job_id INTEGER,
  stage TEXT NOT NULL,
  note TEXT DEFAULT '',
  followup_at TEXT DEFAULT '',
  created_at TEXT DEFAULT CURRENT_TIMESTAMP,
  FOREIGN KEY(job_id) REFERENCES jobs(id)
);
CREATE INDEX IF NOT EXISTS idx_stage_events_job ON application_stage_events(job_id,id);

CREATE TABLE IF NOT EXISTS field_learnings (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  ats TEXT DEFAULT 'generic',
  label_norm TEXT NOT NULL,
  field_type TEXT DEFAULT '',
  value_ref TEXT DEFAULT '',
  strategy TEXT DEFAULT '',
  resolved_option TEXT DEFAULT '',
  success_count INTEGER DEFAULT 0,
  failure_count INTEGER DEFAULT 0,
  note TEXT DEFAULT '',
  last_seen TEXT DEFAULT CURRENT_TIMESTAMP,
  UNIQUE(ats,label_norm,field_type,value_ref)
);
CREATE INDEX IF NOT EXISTS idx_field_learnings_lookup ON field_learnings(ats,label_norm,value_ref);

CREATE TABLE IF NOT EXISTS scans (
  id INTEGER PRIMARY KEY AUTOINCREMENT,
  status TEXT DEFAULT 'running',
  found INTEGER DEFAULT 0,
  fetched INTEGER DEFAULT 0,
  inserted INTEGER DEFAULT 0,
  updated INTEGER DEFAULT 0,
  errors INTEGER DEFAULT 0,
  diagnostics_json TEXT DEFAULT '[]',
  note TEXT DEFAULT '',
  started_at TEXT DEFAULT CURRENT_TIMESTAMP,
  finished_at TEXT DEFAULT ''
);
'''


@contextmanager
def connect():
    DB_PATH.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(DB_PATH, timeout=30)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    finally:
        conn.close()


def _ensure_columns(conn):
    cols = {row['name'] for row in conn.execute('PRAGMA table_info(jobs)').fetchall()}
    had_user_action = 'user_action' in cols
    had_application_status = 'application_status' in cols
    wanted = {
        'canonical_url': "TEXT DEFAULT ''",
        'fingerprint': "TEXT DEFAULT ''",
        'dedupe_key': "TEXT DEFAULT ''",
        'source_variants_json': "TEXT DEFAULT '[]'",
        'search_profile_id': "TEXT DEFAULT ''",
        'search_profile_label': "TEXT DEFAULT ''",
        'provider_key': "TEXT DEFAULT ''",
        'ats': "TEXT DEFAULT ''",
        'employment_type': "TEXT DEFAULT ''",
        'start_date': "TEXT DEFAULT ''",
        'end_date': "TEXT DEFAULT ''",
        'date_posted': "TEXT DEFAULT ''",
        'valid_through': "TEXT DEFAULT ''",
        'salary': "TEXT DEFAULT ''",
        'structured_json': "TEXT DEFAULT ''",
        'fetch_mode': "TEXT DEFAULT ''",
        'availability_status': "TEXT DEFAULT 'unknown'",
        'last_checked_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
        'first_seen_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
        'last_seen_at': 'TEXT DEFAULT CURRENT_TIMESTAMP',
        'user_action': "TEXT DEFAULT ''",
        'application_status': "TEXT DEFAULT ''",
        'apply_adapter': "TEXT DEFAULT ''",
        'fill_audit_path': "TEXT DEFAULT ''",
        'agent_status': "TEXT DEFAULT ''",
        'agent_steps': 'INTEGER DEFAULT 0',
        'agent_trace_path': "TEXT DEFAULT ''",
        'last_application_at': "TEXT DEFAULT ''",
        'tracker_stage': "TEXT DEFAULT ''",
        'tracker_note': "TEXT DEFAULT ''",
        'tracker_source': "TEXT DEFAULT ''",
        'next_followup_at': "TEXT DEFAULT ''",
        'review_verdict': "TEXT DEFAULT ''",
        'review_confidence': 'INTEGER DEFAULT 0',
        'review_summary': "TEXT DEFAULT ''",
        'review_json': "TEXT DEFAULT ''",
        'reviewed_at': "TEXT DEFAULT ''",
    }
    for name, decl in wanted.items():
        if name not in cols:
            conn.execute(f'ALTER TABLE jobs ADD COLUMN {name} {decl}')

    if not had_user_action:
        conn.execute("UPDATE jobs SET user_action=decision WHERE decision IN ('liked','skipped')")
        conn.execute("""UPDATE jobs SET decision=CASE WHEN score>=65 THEN 'keep' WHEN score>=38 THEN 'review' ELSE 'low' END WHERE decision IN ('liked','skipped')""")
    if not had_application_status:
        conn.execute("UPDATE jobs SET application_status='prefilled' WHERE decision='opened'")
        conn.execute("""UPDATE jobs SET decision=CASE WHEN score>=65 THEN 'keep' WHEN score>=38 THEN 'review' ELSE 'low' END WHERE decision='opened'""")

    # Backfill tracker stage from already-known application state without
    # overwriting any explicit stage a user may have set.
    conn.execute("""UPDATE jobs SET tracker_stage='submitted' WHERE tracker_stage='' AND application_status IN ('submitted','submitted_verified')""")
    conn.execute("""UPDATE jobs SET tracker_stage='prepared' WHERE tracker_stage='' AND application_status IN ('prefilled','needs_human')""")


def init_db():
    with connect() as c:
        c.executescript(SCHEMA)
        _ensure_columns(c)
        event_cols = {r['name'] for r in c.execute('PRAGMA table_info(application_stage_events)').fetchall()}
        if 'source' not in event_cols:
            c.execute("ALTER TABLE application_stage_events ADD COLUMN source TEXT DEFAULT ''")
        scan_cols = {r['name'] for r in c.execute('PRAGMA table_info(scans)').fetchall()}
        if 'diagnostics_json' not in scan_cols:
            c.execute("ALTER TABLE scans ADD COLUMN diagnostics_json TEXT DEFAULT '[]'")
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_fingerprint ON jobs(fingerprint)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_dedupe_key ON jobs(dedupe_key)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_canonical_url ON jobs(canonical_url)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_user_action ON jobs(user_action)')
        c.execute('CREATE INDEX IF NOT EXISTS idx_jobs_tracker_stage ON jobs(tracker_stage)')

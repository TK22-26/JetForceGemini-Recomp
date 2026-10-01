"""Supervisor-owned investigation budgets, independent of worker job identities.

Passed jobs are not progress. Only registered, host-verified outcomes can earn
credit. This is an execution guard, never a parity or integration approval.
"""
import hashlib
import json
import math
import re
import time

ID = re.compile(r'[A-Za-z0-9][A-Za-z0-9._:-]{0,127}\Z')
DEFAULT_LIMITS = {'max_attempts':12, 'max_seconds':1800, 'max_no_progress':2,
                  'max_activity':6, 'review_seconds':300, 'alternative_seconds':600}


def install(db):
    db.execute('CREATE TABLE guard_meta (key TEXT PRIMARY KEY, value TEXT NOT NULL)')
    db.execute('''CREATE TABLE investigations (
        problem_id TEXT PRIMARY KEY, definition TEXT NOT NULL, state TEXT NOT NULL,
        reason TEXT NOT NULL, attempts INTEGER NOT NULL DEFAULT 0,
        spent REAL NOT NULL DEFAULT 0, no_progress INTEGER NOT NULL DEFAULT 0,
        activity INTEGER NOT NULL DEFAULT 0, reviews INTEGER NOT NULL DEFAULT 0,
        alternatives INTEGER NOT NULL DEFAULT 0)''')
    db.execute('''CREATE TABLE problem_jobs (
        job_id TEXT PRIMARY KEY REFERENCES jobs(job_id),
        problem_id TEXT NOT NULL REFERENCES investigations(problem_id),
        role TEXT NOT NULL CHECK(role IN ('work','review','alternative')))''')
    db.execute('''CREATE TABLE problem_runs (
        token TEXT PRIMARY KEY REFERENCES attempts(token), problem_id TEXT NOT NULL,
        job_id TEXT NOT NULL, role TEXT NOT NULL, started REAL NOT NULL,
        deadline REAL NOT NULL, ended REAL, outcome TEXT, receipt TEXT)''')
    db.execute('''CREATE TABLE problem_credits (
        problem_id TEXT NOT NULL, fingerprint TEXT NOT NULL, token TEXT NOT NULL,
        PRIMARY KEY(problem_id,fingerprint))''')
    db.execute('CREATE TABLE guard_denials (job_id TEXT PRIMARY KEY, reason TEXT NOT NULL)')


def enabled(db):
    return db.execute("SELECT 1 FROM guard_meta WHERE key='enabled' AND value='1'").fetchone() is not None


def install_continuations(db):
    """Additive v3 migration; no existing job, receipt or allowance is rewritten."""
    db.execute('''CREATE TABLE problem_continuations (
        predecessor_token TEXT PRIMARY KEY REFERENCES problem_runs(token),
        predecessor_job_id TEXT NOT NULL REFERENCES jobs(job_id),
        job_id TEXT NOT NULL UNIQUE REFERENCES jobs(job_id),
        problem_id TEXT NOT NULL REFERENCES investigations(problem_id),
        reason TEXT NOT NULL CHECK(length(reason) BETWEEN 1 AND 500),
        admitted_at REAL NOT NULL,
        CHECK(predecessor_job_id != job_id))''')


def enable(store):
    with store._write() as db:
        if db.execute("SELECT 1 FROM jobs WHERE state IN ('leased','running','verifying')").fetchone():
            raise ValueError('cannot enable progress guard while jobs are active')
        db.execute("INSERT OR IGNORE INTO guard_meta VALUES ('enabled','1')")


def register(store, problem_id, *, roots, limits=None, verifier='none', recovery=None):
    """Trusted host admission. Workers cannot create/reset their own problem."""
    limits = dict(DEFAULT_LIMITS if limits is None else limits)
    recovery = dict(recovery or {})
    if (not isinstance(problem_id,str) or not ID.fullmatch(problem_id) or
            not isinstance(roots,list) or not 1 <= len(roots) <= 32 or len(set(roots)) != len(roots) or
            any(not isinstance(v,str) or not ID.fullmatch(v) for v in roots) or
            set(limits) != set(DEFAULT_LIMITS) or any(type(v) is not int or not 1 <= v <= 86400 for v in limits.values()) or
            limits['max_attempts'] > 100 or limits['max_activity'] > 100 or limits['max_no_progress'] > 10 or
            verifier not in ('none','candidate-frontier') or set(recovery) - {'review','alternative'} or
            ('alternative' in recovery and 'review' not in recovery) or
            any(not isinstance(v,str) or not ID.fullmatch(v) for v in recovery.values()) or
            len(set([*roots,*recovery.values()])) != len(roots)+len(recovery)):
        raise ValueError('invalid investigation contract')
    definition = json.dumps({'roots':sorted(roots),'limits':limits,'verifier':verifier,
                             'recovery':recovery},sort_keys=True,separators=(',',':'))
    with store._write() as db:
        old = db.execute('SELECT definition FROM investigations WHERE problem_id=?',(problem_id,)).fetchone()
        if old:
            if old['definition'] != definition: raise ValueError('investigation budgets and roots are immutable')
            return
        for job_id in [*roots,*recovery.values()]:
            job = db.execute('SELECT state,attempts FROM jobs WHERE job_id=?',(job_id,)).fetchone()
            if job is None or job['state'] in ('leased','running','verifying'):
                raise ValueError('investigation root is missing or active')
            if job_id in recovery.values() and (job['attempts'] or job['state'] != 'queued'):
                raise ValueError('recovery must use a fresh, unstarted job')
            if db.execute('SELECT 1 FROM problem_jobs WHERE job_id=?',(job_id,)).fetchone():
                raise ValueError('job already belongs to an investigation')
        if 'review' in recovery:
            from pathlib import Path
            packet_path = store.db_path.parent/'packets'/(recovery['review']+'.json')
            packet = json.loads(packet_path.read_text())
            if (packet.get('kind') != 'diagnose' or packet.get('allowed_paths') != [] or
                    packet.get('max_changed_files') != 0 or packet.get('validation') != []):
                raise ValueError('recovery review must be a fresh read-only diagnosis')
        db.execute('INSERT INTO investigations(problem_id,definition,state,reason) VALUES (?,?,?,?)',
                   (problem_id,definition,'active','initial bounded investigation'))
        for job_id in roots:
            db.execute('INSERT INTO problem_jobs VALUES (?,?,?)',(job_id,problem_id,'work'))
        for role,job_id in recovery.items():
            db.execute('INSERT INTO problem_jobs VALUES (?,?,?)',(job_id,problem_id,role))


def membership(db,job_id,seen=()):
    if job_id in seen or len(seen) >= 256: raise ValueError('cyclic or excessive investigation ancestry')
    found = db.execute('SELECT problem_id,role FROM problem_jobs WHERE job_id=?',(job_id,)).fetchone()
    if found: return dict(found)
    job = db.execute('SELECT spec_json FROM jobs WHERE job_id=?',(job_id,)).fetchone()
    if not job: return None
    parents = [membership(db,p,(*seen,job_id)) for p in json.loads(job['spec_json'])['prerequisites']]
    # A renamed child inherits; crossing unrelated or unregistered roots is not silently approved.
    if not parents or any(p is None for p in parents) or len({p['problem_id'] for p in parents}) != 1:
        return None
    problem_id = parents[0]['problem_id']
    db.execute('INSERT INTO problem_jobs VALUES (?,?,?)',(job_id,problem_id,'work'))
    return {'problem_id':problem_id,'role':'work'}


def _continuation_dependency(db,job_id,problem_id,seen=(),checked=None):
    """Read-only ancestry check, including dependencies of explicitly assigned jobs."""
    if checked is None: checked = set()
    if job_id in seen or len(seen) >= 256:
        raise ValueError('cyclic or excessive investigation ancestry')
    if job_id in checked: return
    job = db.execute('SELECT spec_json FROM jobs WHERE job_id=?',(job_id,)).fetchone()
    member = db.execute('SELECT problem_id FROM problem_jobs WHERE job_id=?',(job_id,)).fetchone()
    if job is None or (member and member['problem_id'] != problem_id):
        raise ValueError('unknown or cross-problem dependency ancestry')
    parents = json.loads(job['spec_json'])['prerequisites']
    if not member and not parents:
        raise ValueError('unregistered dependency ancestry')
    for parent in parents:
        _continuation_dependency(db,parent,problem_id,(*seen,job_id),checked)
    checked.add(job_id)


def admit_continuation(store,problem_id,*,predecessor_job_id,job_id,reason,now=None):
    """Trusted host admission of accounting ancestry, never a success dependency.

    Returns the immutable admission receipt. Workers must not be given this API
    or write access to the ledger. Replays still require an active allowance.
    """
    timestamp = time.time() if now is None else now
    if (any(not isinstance(v,str) or not ID.fullmatch(v)
            for v in (problem_id,predecessor_job_id,job_id)) or predecessor_job_id == job_id or
            not isinstance(reason,str) or not 1 <= len(reason) <= 500 or
            reason != reason.strip() or not reason.isprintable() or
            type(timestamp) not in (int,float) or not math.isfinite(timestamp) or timestamp < 0):
        raise ValueError('invalid continuation identifiers, reason or timestamp')
    # BEGIN IMMEDIATE serializes admission with other admissions, leases and grades.
    # All rejection paths roll back, including any future changes to validation.
    with store._write() as db:
        if not enabled(db): raise ValueError('continuation requires an enabled progress guard')
        p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(problem_id,)).fetchone()
        if p is None or p['state'] != 'active':
            raise ValueError('continuation requires an existing active investigation')
        limits = json.loads(p['definition'])['limits']
        if any(not 0 <= p[column] < limits[limit] for column,limit in (
                ('attempts','max_attempts'),('spent','max_seconds'),
                ('no_progress','max_no_progress'),('activity','max_activity'))):
            raise ValueError('continuation investigation allowance exhausted')
        if (db.execute('''SELECT 1 FROM problem_runs WHERE problem_id=?
                          AND (ended IS NULL OR outcome IS NULL)''',(problem_id,)).fetchone() or
                db.execute('''SELECT 1 FROM problem_jobs m JOIN jobs j ON j.job_id=m.job_id
                              WHERE m.problem_id=? AND j.state IN ('leased','running','verifying')''',
                           (problem_id,)).fetchone()):
            raise ValueError('investigation has a live or ungraded attempt')
        predecessor = db.execute('SELECT * FROM jobs WHERE job_id=?',(predecessor_job_id,)).fetchone()
        member = db.execute('SELECT * FROM problem_jobs WHERE job_id=?',(predecessor_job_id,)).fetchone()
        if (predecessor is None or predecessor['state'] not in ('failed','blocked') or
                member is None or member['problem_id'] != problem_id or member['role'] != 'work'):
            raise ValueError('predecessor must be failed or blocked normal work in the same investigation')
        attempt = db.execute('SELECT * FROM attempts WHERE job_id=? ORDER BY number DESC LIMIT 1',
                             (predecessor_job_id,)).fetchone()
        if (attempt is None or attempt['number'] != predecessor['attempts'] or
                attempt['ended_at'] is None or attempt['outcome'] not in ('failed','blocked','expired')):
            raise ValueError('predecessor latest attempt must be completed')
        run = db.execute('SELECT * FROM problem_runs WHERE token=?',(attempt['token'],)).fetchone()
        if (run is None or run['problem_id'] != problem_id or run['job_id'] != predecessor_job_id or
                run['role'] != 'work' or run['ended'] is None or
                run['outcome'] is None or run['receipt'] is None):
            raise ValueError('predecessor latest attempt must be independently graded normal work')
        if timestamp < max(attempt['ended_at'],run['ended']):
            raise ValueError('continuation timestamp precedes completed attempt')
        old = db.execute('''SELECT * FROM problem_continuations
                            WHERE predecessor_token=? OR job_id=?''',(attempt['token'],job_id)).fetchall()
        if old:
            if (len(old) == 1 and old[0]['problem_id'] == problem_id and
                    old[0]['predecessor_job_id'] == predecessor_job_id and
                    old[0]['predecessor_token'] == attempt['token'] and
                    old[0]['job_id'] == job_id and old[0]['reason'] == reason):
                return dict(old[0])
            raise ValueError('continuation is immutable; predecessor attempt or child already admitted')
        child = db.execute('SELECT * FROM jobs WHERE job_id=?',(job_id,)).fetchone()
        assigned = db.execute('SELECT * FROM problem_jobs WHERE job_id=?',(job_id,)).fetchone()
        if (child is None or child['state'] != 'queued' or child['attempts'] or
                db.execute('SELECT 1 FROM attempts WHERE job_id=?',(job_id,)).fetchone()):
            raise ValueError('continuation child must be a fresh queued unattempted job')
        if assigned and (assigned['problem_id'] != problem_id or assigned['role'] != 'work'):
            raise ValueError('continuation child has conflicting investigation membership')
        checked = set()
        for parent in json.loads(child['spec_json'])['prerequisites']:
            _continuation_dependency(db,parent,problem_id,(job_id,),checked)
        db.execute('INSERT INTO problem_continuations VALUES (?,?,?,?,?,?)',
                   (attempt['token'],predecessor_job_id,job_id,problem_id,reason,timestamp))
        if not assigned:
            db.execute('INSERT INTO problem_jobs VALUES (?,?,?)',(job_id,problem_id,'work'))
        return dict(db.execute('SELECT * FROM problem_continuations WHERE job_id=?',(job_id,)).fetchone())


def _transition(db,problem_id,state,reason):
    db.execute('UPDATE investigations SET state=?,reason=? WHERE problem_id=?',(state,reason,problem_id))


def _stall(db,p,reason):
    recovery = json.loads(p['definition'])['recovery']
    state = 'review-needed' if not p['reviews'] and 'review' in recovery else 'shelved'
    _transition(db,p['problem_id'],state,reason)


def permit(db,job_id,now):
    if not enabled(db): return True
    member = membership(db,job_id)
    reason = 'unregistered investigation; trusted root admission required'
    if member:
        p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(member['problem_id'],)).fetchone()
        limits = json.loads(p['definition'])['limits']
        # Serialize each investigation through independent result grading.
        pending = db.execute('SELECT 1 FROM problem_runs WHERE problem_id=? AND outcome IS NULL',
                             (p['problem_id'],)).fetchone()
        if pending: reason = 'investigation has a running or ungraded attempt'
        else:
            if p['state'] == 'active' and (p['attempts'] >= limits['max_attempts'] or p['spent'] >= limits['max_seconds']):
                _stall(db,p,'cumulative investigation budget exhausted')
                p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(p['problem_id'],)).fetchone()
            allowed = {'work':'active','review':'review-needed','alternative':'alternative-ready'}
            if p['state'] == allowed[member['role']]:
                db.execute('DELETE FROM guard_denials WHERE job_id=?',(job_id,))
                return True
            reason = p['state']+': '+p['reason']
    db.execute('INSERT OR REPLACE INTO guard_denials VALUES (?,?)',(job_id,reason))
    return False


def started(db,job_id,token,now):
    if not enabled(db): return
    member = membership(db,job_id)
    if member is None: raise ValueError('cannot charge an unregistered investigation')
    p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(member['problem_id'],)).fetchone()
    limits = json.loads(p['definition'])['limits']; role = member['role']
    seconds = max(0,limits['max_seconds']-p['spent']) if role == 'work' else limits[role+'_seconds']
    db.execute('INSERT INTO problem_runs(token,problem_id,job_id,role,started,deadline) VALUES (?,?,?,?,?,?)',
               (token,p['problem_id'],job_id,role,now,now+seconds))
    db.execute('UPDATE investigations SET attempts=attempts+1 WHERE problem_id=?',(p['problem_id'],))
    if role != 'work':
        column = 'reviews' if role == 'review' else 'alternatives'
        db.execute(f'UPDATE investigations SET {column}={column}+1 WHERE problem_id=?',(p['problem_id'],))
        _transition(db,p['problem_id'],role+'-running','bounded recovery attempt')


def heartbeat(db,token,now):
    row = db.execute('SELECT deadline FROM problem_runs WHERE token=?',(token,)).fetchone()
    if row and now >= row['deadline']:
        raise ValueError('investigation execution budget exhausted')


def finish(db,token,now):
    row = db.execute('SELECT * FROM problem_runs WHERE token=?',(token,)).fetchone()
    if row and row['ended'] is None:
        elapsed = max(0,now-row['started'])
        db.execute('UPDATE problem_runs SET ended=? WHERE token=?',(now,token))
        db.execute('UPDATE investigations SET spent=spent+? WHERE problem_id=?',(elapsed,row['problem_id']))


def decide(store,token,receipt):
    """Host verifier result; never deserialize a worker 'progress' flag here."""
    if (not isinstance(receipt,dict) or set(receipt) - {'decision','fingerprint','reason','metric'} or
            not {'decision','fingerprint','reason'} <= set(receipt) or
            receipt['decision'] not in ('progress','no-progress','activity','review-complete') or
            not isinstance(receipt['reason'],str) or not 1 <= len(receipt['reason']) <= 500 or
            (receipt['fingerprint'] is not None and
             (not isinstance(receipt['fingerprint'],str) or not re.fullmatch('[0-9a-f]{64}',receipt['fingerprint']))) or
            (receipt['decision'] == 'progress' and receipt['fingerprint'] is None)):
        raise ValueError('invalid independently verified progress receipt')
    metric = receipt.get('metric')
    if metric is not None and (not isinstance(metric,dict) or set(metric) != {'name','value'} or
            metric['name'] != 'selected-update-prefix' or type(metric['value']) is not int or
            not 0 <= metric['value'] <= 1000000):
        raise ValueError('invalid independently measured progress metric')
    with store._write() as db:
        run = db.execute('SELECT * FROM problem_runs WHERE token=?',(token,)).fetchone()
        if run is None or run['ended'] is None: raise ValueError('attempt has not finished')
        encoded = json.dumps(receipt,sort_keys=True)
        if run['outcome'] is not None:
            if run['receipt'] != encoded: raise ValueError('progress decision is immutable')
            return
        p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(run['problem_id'],)).fetchone()
        definition = json.loads(p['definition']); limits = definition['limits']
        decision = receipt['decision']
        if decision == 'progress':
            duplicate = db.execute('SELECT 1 FROM problem_credits WHERE problem_id=? AND fingerprint=?',
                                   (p['problem_id'],receipt['fingerprint'])).fetchone()
            history = [json.loads(r[0]).get('metric') for r in db.execute(
                "SELECT receipt FROM problem_runs WHERE problem_id=? AND outcome='progress'",(p['problem_id'],))]
            high_water = max((m['value'] for m in history if m is not None),default=-1)
            if duplicate or (metric is not None and metric['value'] <= high_water): decision = 'no-progress'
            else: db.execute('INSERT INTO problem_credits VALUES (?,?,?)',(p['problem_id'],receipt['fingerprint'],token))
        db.execute('UPDATE problem_runs SET outcome=?,receipt=? WHERE token=?',(decision,encoded,token))
        if run['role'] == 'review':
            state = 'alternative-ready' if decision == 'review-complete' and 'alternative' in definition['recovery'] else 'shelved'
            _transition(db,p['problem_id'],state,'review finished; '+receipt['reason'])
        elif run['role'] == 'alternative':
            # One alternative is not a fresh unlimited allowance.
            _transition(db,p['problem_id'],'shelved','bounded alternative finished; '+receipt['reason'])
        elif decision == 'progress':
            db.execute('UPDATE investigations SET no_progress=0,activity=0 WHERE problem_id=?',(p['problem_id'],))
        else:
            column = 'no_progress' if decision == 'no-progress' else 'activity'
            db.execute(f'UPDATE investigations SET {column}={column}+1 WHERE problem_id=?',(p['problem_id'],))
            p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(p['problem_id'],)).fetchone()
            if p['no_progress'] >= limits['max_no_progress'] or p['activity'] >= limits['max_activity']:
                _stall(db,p,'no verified progress within the investigation allowance')
        p = db.execute('SELECT * FROM investigations WHERE problem_id=?',(run['problem_id'],)).fetchone()
        if p['state'] == 'active' and (p['attempts'] >= limits['max_attempts'] or p['spent'] >= limits['max_seconds']):
            _stall(db,p,'cumulative investigation budget exhausted')


def classify(store,repo,state,run):
    """Supported evidence adapters run in the supervisor, outside the worker."""
    job = store.job(run['job_id'])
    result = {'decision':'no-progress','fingerprint':None,'reason':'attempt failed or expired'}
    if job['state'] != 'passed': return result
    # A read-only review is only a recovery proposal, never progress credit.
    if run['role'] == 'review':
        from scripts.autonomy.supervisor import read_packet, read_diagnosis, file_sha256
        from pathlib import Path
        packet = read_packet(state/'packets'/(run['job_id']+'.json'),repo)
        seal = Path(job['sealed_artifact'])
        report = json.loads(seal.read_text())
        answer = seal.parent/'last-message.txt'
        if (packet['kind'] != 'diagnose' or packet['allowed_paths'] or
                packet['max_changed_files'] != 0 or file_sha256(seal) != job['sealed_sha256'] or
                report.get('diagnosis_sha256') != file_sha256(answer)):
            raise ValueError('recovery review is not a sealed read-only diagnosis')
        diagnosis = read_diagnosis(answer)
        return {'decision':'review-complete','fingerprint':None,
                'reason':'fresh read-only diagnosis retained; no progress credit'}
    definition = json.loads(store.connection.execute('SELECT definition FROM investigations WHERE problem_id=?',
                                                      (run['problem_id'],)).fetchone()[0])
    if definition['verifier'] == 'candidate-frontier' and job['spec']['inputs'][0].startswith('candidate-retest-packet:'):
        from scripts.autonomy.candidate_feedback import checked_outcome
        facts,_,_ = checked_outcome(store,repo,state,run['job_id'])
        if (facts['disposition'] == 'retained-for-integration-review' and facts['input_prefix_match'] and
                facts['raw_frontier']['classification'] == 'moved-later'):
            first = facts['raw_frontier']['candidate_first_raw_mismatch']
            if first is not None:
                if type(first) is not int or first < 1: raise ValueError('invalid frontier')
                value = first-1
            else:
                from pathlib import Path
                pins = [p for p in facts['evidence'] if Path(p['path']).name == 'candidate-comparison.json']
                if len(pins) != 1: raise ValueError('complete frontier comparison is missing')
                raw = Path(pins[0]['path']).read_bytes()
                if hashlib.sha256(raw).hexdigest() != pins[0]['sha256']: raise ValueError('frontier evidence changed')
                value = json.loads(raw)['compared_updates']
            # Outcome identity excludes fresh job IDs, commits and renamed baselines.
            metric = {'name':'selected-update-prefix','value':value}
            fingerprint = hashlib.sha256(json.dumps(metric,sort_keys=True).encode()).hexdigest()
            return {'decision':'progress','fingerprint':fingerprint,'metric':metric,
                    'reason':'independently checked candidate replay advances frontier'}
        return {**result,'reason':'independent candidate replay did not advance the frontier'}
    return {'decision':'activity','fingerprint':None,'reason':'sealed supporting work; no registered progress proof'}


def reconcile(store,repo,state):
    if not enabled(store.connection): return
    pending = store.connection.execute('SELECT * FROM problem_runs WHERE ended IS NOT NULL AND outcome IS NULL ORDER BY started').fetchall()
    for run in pending:
        try: receipt = classify(store,repo,state,run)
        except (OSError,ValueError,KeyError,TypeError):
            receipt = {'decision':'no-progress','fingerprint':None,'reason':'independent progress verification rejected evidence'}
        decide(store,run['token'],receipt)


def status(store):
    rows = store.connection.execute('SELECT * FROM investigations ORDER BY problem_id').fetchall()
    return {'schema':1,'kind':'jfg-investigation-progress','enabled':enabled(store.connection),
            'problems':[{k:row[k] for k in ('problem_id','state','reason','attempts','spent','no_progress','activity','reviews','alternatives')}
                        for row in rows],
            'denials':[dict(r) for r in store.connection.execute('SELECT * FROM guard_denials ORDER BY job_id')]}


def halted(store):
    if not enabled(store.connection): return False
    if store.connection.execute("SELECT 1 FROM jobs WHERE state IN ('leased','running','verifying')").fetchone():
        return False  # A real running dependency is a wait, not stagnation.
    return bool(store.connection.execute('''SELECT 1 FROM guard_denials d JOIN jobs j
        ON d.job_id=j.job_id WHERE j.state='queued' ''').fetchone())


def main():
    import argparse
    from pathlib import Path
    from scripts.autonomy.job_store import JobStore
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--state',type=Path,required=True)
    parser.add_argument('--register',help='trusted host problem identifier')
    parser.add_argument('--admit-continuation',metavar='PROBLEM',help='trusted same-investigation admission')
    parser.add_argument('--predecessor-job',metavar='JOB')
    parser.add_argument('--job',metavar='JOB')
    parser.add_argument('--reason',help='1..500 printable characters; no surrounding whitespace')
    parser.add_argument('--root',action='append',default=[])
    parser.add_argument('--verifier',choices=['none','candidate-frontier'],default='none')
    parser.add_argument('--enable',action='store_true')
    args = parser.parse_args()
    if args.admit_continuation:
        if args.register or args.enable or not all((args.predecessor_job,args.job,args.reason)):
            parser.error('continuation requires --predecessor-job, --job and --reason; cannot register or enable')
    elif any(v is not None for v in (args.predecessor_job,args.job,args.reason)):
        parser.error('continuation arguments require --admit-continuation')
    state = args.state.resolve(strict=True)
    repo = Path(__file__).resolve().parents[2]
    if not state.is_relative_to(repo/'tools/private'): parser.error('guard state must be private')
    with JobStore(state/'jobs.sqlite') as store:
        if args.register: register(store,args.register,roots=args.root,verifier=args.verifier)
        if args.enable: enable(store)
        if args.admit_continuation:
            try:
                receipt = admit_continuation(store,args.admit_continuation,
                    predecessor_job_id=args.predecessor_job,job_id=args.job,reason=args.reason)
            except ValueError as error: parser.error(str(error))
            print(json.dumps(receipt),flush=True)
            return
        print(json.dumps(status(store)),flush=True)


if __name__ == '__main__': main()

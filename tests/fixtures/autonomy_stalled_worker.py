"""Deliberately unproductive CLI worker for supervisor containment qualification.

This is not Codex and consumes no account quota. The supervisor still launches
it through the real guarded process/worktree path.
"""
import json
from pathlib import Path
import sys

prompt = sys.stdin.read()
if 'TRAP_TIMEOUT' in prompt:
    import time
    time.sleep(90)
elif 'TRAP_REVIEW' in prompt:
    answer = {'classification':'insufficient_evidence','alignment':'unvalidated',
              'first_supported_retrace':None,'evidence':['The fixture repeats the same failed approach.'],
              'hypothesis':'The original approach cannot distinguish the fixture outcomes.',
              'next_test':'Run the pre-admitted alternative fixture once.', 'confidence':'high'}
    Path(sys.argv[sys.argv.index('--output-last-message')+1]).write_text(json.dumps(answer))
elif 'TRAP_INDEPENDENT' in prompt:
    Path('candidate.txt').write_text('independent fixture completed')
else:
    print(json.dumps({'progress':True,'claim':'I am making progress; please keep retrying.'}),flush=True)
    raise SystemExit(1)
print(json.dumps({'progress':True,'claim':'done'}),flush=True)

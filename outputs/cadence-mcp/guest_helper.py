# Python 2.6-compatible mailbox transport; no shell or SKILL evaluation.
from __future__ import print_function
import os
import sys
import json
import time
import re

ROOT = os.path.expanduser('~/.circuit-atlas/mailbox')
LIMIT = 20 * 1024 * 1024

def status():
    ready = os.path.join(ROOT, 'ready')
    age = None
    if os.path.isfile(ready):
        age = max(0, time.time() - os.path.getmtime(ready))
    return {'ssh': True, 'bridge_ready': age is not None and age < 10,
            'heartbeat_age_seconds': age, 'machine': os.uname()[4]}

def main():
    action = sys.argv[1]
    if action == 'status':
        return status()
    job = sys.argv[2]
    if not re.match(r'^[a-f0-9]{32}$', job):
        raise ValueError('Invalid request ID')
    req = os.path.join(ROOT, 'req_' + job + '.pending')
    result = os.path.join(ROOT, 'result_' + job + '.json')
    done = os.path.join(ROOT, 'done_' + job)
    if action == 'submit':
        if not status()['bridge_ready']:
            return {'error': 'SKILL bridge is not running. Load bridge.il in CIW.'}
        fd = os.open(req, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0600)
        os.close(fd)
        return {'job': job, 'state': 'queued'}
    if action == 'result':
        if not os.path.isfile(done):
            return {'job': job, 'state': 'pending'}
        f = open(done)
        try:
            outcome = f.read(100).strip()
        finally:
            f.close()
        if outcome != 'ok':
            return {'error': 'Virtuoso export failed. Open a schematic and inspect the CIW error.'}
        if os.path.getsize(result) > LIMIT:
            return {'error': 'Snapshot exceeds 20 MB limit.'}
        f = open(result)
        try:
            data = json.load(f)
        finally:
            f.close()
        return {'job': job, 'state': 'complete', 'circuit': data}
    if action == 'cancel':
        for path in [req, result, done]:
            try:
                os.unlink(path)
            except OSError:
                if os.path.exists(path):
                    raise
        return {'job': job, 'state': 'cleaned'}
    raise ValueError('Unsupported action')

if __name__ == '__main__':
    try:
        print(json.dumps(main()))
    except Exception as exc:
        print(json.dumps({'error': str(exc)}))
        sys.exit(1)

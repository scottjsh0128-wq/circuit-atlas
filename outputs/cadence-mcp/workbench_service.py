"""Shared SQLite workspace and durable queue for local HTTP and MCP clients."""
import asyncio,json,os,sqlite3,threading,time,uuid,math
from pathlib import Path
from contextlib import contextmanager
ROOT=Path(__file__).resolve().parent
DB=ROOT.parent/'circuit-workbench/data/workbench.sqlite3'
_started=False

@contextmanager
def conn():
    DB.parent.mkdir(parents=True,exist_ok=True)
    c=sqlite3.connect(DB,timeout=15);c.row_factory=sqlite3.Row;c.execute('PRAGMA foreign_keys=ON')
    try:
        with c:yield c
    finally:c.close()

def init():
    with conn() as c:
        c.executescript('''CREATE TABLE IF NOT EXISTS projects(id TEXT PRIMARY KEY,name TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS blocks(id TEXT PRIMARY KEY,project_id TEXT NOT NULL REFERENCES projects(id),name TEXT NOT NULL,kind TEXT NOT NULL,cell TEXT NOT NULL,rails TEXT NOT NULL,roles TEXT NOT NULL DEFAULT '{}');
        CREATE TABLE IF NOT EXISTS specs(id TEXT PRIMARY KEY,block_id TEXT NOT NULL REFERENCES blocks(id),category TEXT NOT NULL,name TEXT NOT NULL,metric TEXT NOT NULL,unit TEXT NOT NULL,comparison TEXT NOT NULL,target REAL,scope TEXT NOT NULL);
        CREATE TABLE IF NOT EXISTS runs(id TEXT PRIMARY KEY,block_id TEXT NOT NULL REFERENCES blocks(id),status TEXT NOT NULL,created REAL NOT NULL,updated REAL NOT NULL,payload TEXT NOT NULL,result TEXT,error TEXT,cancel_requested INTEGER NOT NULL DEFAULT 0);
        CREATE TABLE IF NOT EXISTS inspections(block_id TEXT PRIMARY KEY REFERENCES blocks(id),payload TEXT NOT NULL,updated REAL NOT NULL);
        CREATE INDEX IF NOT EXISTS runs_block_created ON runs(block_id,created);
        CREATE INDEX IF NOT EXISTS runs_status ON runs(status);''')
        if not c.execute('SELECT 1 FROM projects').fetchone():
            c.execute('INSERT INTO projects VALUES (?,?)',('project-initial','Analog / ADC'))

def clean_string(value,name,limit=128):
    if not isinstance(value,str) or not value.strip() or len(value)>limit:raise ValueError(name+' is required')
    return value.strip()

def save_project(data):
    name=clean_string(data.get('name'),'Project name');uid=data.get('id') or uuid.uuid4().hex
    with conn() as c:
        if data.get('id'):
            if c.execute('UPDATE projects SET name=? WHERE id=?',(name,uid)).rowcount!=1:raise ValueError('Unknown project')
        else:c.execute('INSERT INTO projects VALUES (?,?)',(uid,name))
    return uid

def save_block(data):
    name=clean_string(data.get('name'),'Block name');kind=clean_string(data.get('kind'),'Block type');cell=clean_string(data.get('cell'),'Testbench cell')
    if kind not in ('ota','comparator','integrator','switch','bias','sar','sigma_delta','custom'):raise ValueError('Unknown block template')
    rails=data.get('rails',[])
    if not isinstance(rails,list) or len(rails)>20 or any(not isinstance(r,str) or len(r)>128 for r in rails):raise ValueError('Invalid supplies')
    roles=data.get('roles',{})
    if not isinstance(roles,dict) or len(roles)>2000 or any(v not in ('observe','saturation','switch','off') for v in roles.values()):raise ValueError('Invalid device roles')
    uid=data.get('id') or uuid.uuid4().hex
    with conn() as c:
        if data.get('id'):
            if c.execute('UPDATE blocks SET name=?,kind=?,cell=?,rails=?,roles=? WHERE id=?',(name,kind,cell,json.dumps(rails),json.dumps(roles),uid)).rowcount!=1:raise ValueError('Unknown block')
        else:c.execute('INSERT INTO blocks VALUES (?,?,?,?,?,?,?)',(uid,data['project_id'],name,kind,cell,json.dumps(rails),json.dumps(roles)))
    return uid

def save_spec(data):
    uid=data.get('id') or uuid.uuid4().hex
    category=clean_string(data.get('category'),'Category');name=clean_string(data.get('name'),'Metric name');metric=clean_string(data.get('metric'),'Metric key');unit=clean_string(data.get('unit'),'Unit');scope=data.get('scope',{})
    if category not in [str(i) for i in range(1,13)] or data.get('comparison') not in ('min','max'):raise ValueError('Invalid spec rule')
    target=data.get('target')
    if target is not None and (isinstance(target,bool) or not isinstance(target,(int,float)) or not math.isfinite(target)):raise ValueError('Invalid target')
    if not isinstance(scope,dict) or any(k not in ('recipe','temperature','corner') for k in scope):raise ValueError('Invalid condition scope')
    with conn() as c:
        values=(data['block_id'],category,name,metric,unit,data['comparison'],target,json.dumps(scope))
        if data.get('id'):
            if c.execute('UPDATE specs SET block_id=?,category=?,name=?,metric=?,unit=?,comparison=?,target=?,scope=? WHERE id=?',values+(uid,)).rowcount!=1:raise ValueError('Unknown spec')
        else:c.execute('INSERT INTO specs VALUES (?,?,?,?,?,?,?,?,?)',(uid,)+values)
    return uid

def get_block(uid):
    with conn() as c:r=c.execute('SELECT * FROM blocks WHERE id=?',(uid,)).fetchone()
    if not r:raise ValueError('Unknown block')
    return dict(r)

def public_state():
    with conn() as c:
        projects=[dict(r) for r in c.execute('SELECT * FROM projects')];blocks=[dict(r) for r in c.execute('SELECT * FROM blocks')];specs=[dict(r) for r in c.execute('SELECT * FROM specs')];runs=[dict(r) for r in c.execute('SELECT * FROM runs ORDER BY created DESC LIMIT 200')]
    with conn() as c: inspections={r['block_id']:json.loads(r['payload']) for r in c.execute('SELECT * FROM inspections')}
    for b in blocks:
        b['rails']=json.loads(b['rails']);b['roles']=json.loads(b['roles']);b['inspection']=inspections.get(b['id'])
        if b['inspection'] and b['inspection']['cell']!=b['cell']:b['inspection']=None
    for s in specs:s['scope']=json.loads(s['scope'])
    for r in runs:r['payload']=json.loads(r['payload']);r['result']=json.loads(r['result']) if r['result'] else None
    return {'projects':projects,'blocks':blocks,'specs':specs,'runs':runs,'schema':'circuit-workbench/1'}

def start_run(block_id,expected_sha256,overrides=None,recipe='dc'):
    b=get_block(block_id)
    if recipe not in ('dc','saved'):raise ValueError('Unsupported recipe')
    if not isinstance(expected_sha256,str) or len(expected_sha256)!=64:raise ValueError('Inspect the testbench first')
    if not isinstance(overrides or {},dict) or len(overrides or {})>100:raise ValueError('Invalid overrides')
    uid=uuid.uuid4().hex;now=time.time()
    payload={'cell':b['cell'],'expected_sha256':expected_sha256,'overrides':overrides or {},'recipe':recipe,'block_snapshot':b}
    with conn() as c:c.execute('INSERT INTO runs(id,block_id,status,created,updated,payload) VALUES (?,?,?,?,?,?)',(uid,block_id,'queued',now,now,json.dumps(payload)))
    ensure_worker();return {'id':uid,'status':'queued'}

def cancel_run(uid):
    with conn() as c:
        row=c.execute('SELECT status FROM runs WHERE id=?',(uid,)).fetchone()
        if not row:raise ValueError('Unknown run')
        if row['status']=='queued':c.execute('UPDATE runs SET status=?,updated=? WHERE id=?',('cancelled',time.time(),uid))
        elif row['status']=='running':c.execute('UPDATE runs SET cancel_requested=1 WHERE id=?',(uid,))
    return {'id':uid,'note':'Queued job cancelled; running job finishes its current bounded simulation.'}

def import_run(block_id,job):
    b=get_block(block_id)
    if not isinstance(job,str) or len(job)!=32 or any(c not in '0123456789abcdef' for c in job):raise ValueError('Invalid run ID')
    path=ROOT/'simulation-results'/job/'result.json';result=json.loads(path.read_text(encoding='utf-8'))
    if result['cell']!=b['cell']:raise ValueError('Testbench does not match this block')
    uid=uuid.uuid4().hex;payload={'cell':b['cell'],'expected_sha256':result['source_sha256'],'recipe':result.get('recipe','saved'),'overrides':{x['key']:x['after'] for x in result.get('overrides',[])},'block_snapshot':b,'imported':True}
    with conn() as c:
        # Idempotent import per block and source run.
        for row in c.execute('SELECT id,result FROM runs WHERE block_id=? AND result IS NOT NULL',(block_id,)):
            if json.loads(row['result']).get('job')==job:return {'id':row['id']}
        c.execute('INSERT INTO runs(id,block_id,status,created,updated,payload,result) VALUES (?,?,?,?,?,?,?)',(uid,block_id,'completed' if result['success'] else 'failed',path.stat().st_mtime,time.time(),json.dumps(payload),json.dumps(result)))
    return {'id':uid}

def claim():
    with conn() as c:
        c.execute('BEGIN IMMEDIATE')
        c.execute("UPDATE runs SET status='interrupted',error='Worker did not complete within lease. Review artifacts before retrying.',updated=? WHERE status='running' AND updated<?",(time.time(),time.time()-180))
        if c.execute("SELECT 1 FROM runs WHERE status='running'").fetchone():return None
        row=c.execute("SELECT * FROM runs WHERE status='queued' ORDER BY created LIMIT 1").fetchone()
        if not row:return None
        c.execute("UPDATE runs SET status='running',updated=? WHERE id=?",(time.time(),row['id']));return dict(row)

def worker():
    while True:
        row=None
        try:
            row=claim()
            if row:
                from server import cadence_run_saved_simulation
                p=json.loads(row['payload']);result=asyncio.run(cadence_run_saved_simulation(p['cell'],p['expected_sha256'],p['overrides'],p['recipe']))
                result['workbench_recipe']=p['recipe']
                with conn() as c:c.execute('UPDATE runs SET status=?,result=?,updated=? WHERE id=?',('completed' if result['success'] else 'failed',json.dumps(result),time.time(),row['id']))
            else:time.sleep(.5)
        except Exception as e:
            if 'row' in locals() and row:
                with conn() as c:c.execute('UPDATE runs SET status=?,error=?,updated=? WHERE id=?',('failed',str(e),time.time(),row['id']))
            time.sleep(.5)

def ensure_worker():
    global _started
    if not _started:_started=True;threading.Thread(target=worker,daemon=True,name='workbench-simulations').start()

def save_inspection(block_id,info):
    b=get_block(block_id)
    if info['cell']!=b['cell']:raise ValueError('Testbench changed while inspecting')
    with conn() as c:c.execute('INSERT INTO inspections VALUES (?,?,?) ON CONFLICT(block_id) DO UPDATE SET payload=excluded.payload,updated=excluded.updated',(block_id,json.dumps(info),time.time()))

# Python 2.6-compatible, fixed Spectre baseline runner. No arbitrary commands.
from __future__ import print_function
import os, sys, json, re, hashlib, shutil, subprocess, threading, signal, uuid
from netlist_parameters import public_catalog, apply_overrides
BASE='/home/buet/simulation'
RUNS='/home/buet/.circuit-atlas/runs'
SPECTRE='/home/buet/cadence/MMSIM121/tools/bin/spectre'
def inspect(cell):
    if not re.match(r'^[A-Za-z0-9_][A-Za-z0-9_-]{0,127}$',cell): raise ValueError('Invalid cell name')
    directory=os.path.realpath(os.path.join(BASE,cell,'spectre/schematic/netlist'))
    if not directory.startswith(BASE+'/'): raise ValueError('Invalid path')
    p=os.path.join(directory,'input.scs')
    with open(p,'rb') as f: text=f.read(2000001)
    if len(text)>2000000: raise ValueError('Netlist exceeds limit')
    return {'cell':cell,'netlist_directory':directory,'sha256':hashlib.sha256(text).hexdigest(),
      'model_sections':re.findall(r'\bsection=([A-Za-z0-9_]+)',text),'parameters':public_catalog(text),'netlist':text,'analyses':re.findall(r'^\s*\S+\s+(tran|ac|stb|dc|noise|pss|pnoise)\b.*',text,re.M),
      'source':'saved ADE netlist; not a fresh schematic netlist','modified_epoch':os.path.getmtime(p)}
def run(cell,expected,overrides=None,recipe='saved'):
    info=inspect(cell)
    if info['sha256']!=expected: raise ValueError('Netlist changed; inspect again before running')
    modified,changes=apply_overrides(info['netlist'],overrides or {})
    if recipe not in ('saved','dc'): raise ValueError('Unsupported recipe')
    if recipe=='dc':
        if any(a not in ('tran','ac','stb','dc','noise') for a in info['analyses']):raise ValueError('This netlist needs a dedicated DC testbench')
        modified='\n'.join(line for line in modified.splitlines() if not re.match(r'^\s*\S+\s+(tran|ac|stb|dc|noise)\b',line))+'\ncaDC dc\ncaOpInfo info what=oppoint where=rawfile\n'
    job=uuid.uuid4().hex
    target=os.path.join(RUNS,job)
    if not os.path.isdir(RUNS): os.makedirs(RUNS,0700)
    # Reject symlinks and unexpectedly large saved netlist directories.
    total=0
    for directory,dirs,files in os.walk(info['netlist_directory']):
      for name in dirs+files:
        p=os.path.join(directory,name)
        if os.path.islink(p): raise ValueError('Symlink in netlist directory')
      for name in files: total+=os.path.getsize(os.path.join(directory,name))
    if total>20*1024*1024: raise ValueError('Netlist directory exceeds limit')
    os.mkdir(target,0700)
    netlist=os.path.join(target,'netlist');shutil.copytree(info['netlist_directory'],netlist)
    with open(os.path.join(netlist,'input.scs'),'rb') as f:
      if hashlib.sha256(f.read()).hexdigest()!=expected: raise ValueError('Netlist changed during copy')
    with open(os.path.join(netlist,'input.scs'),'w') as f: f.write(modified)
    psf=os.path.join(target,'psf');os.mkdir(psf)
    log=open(os.path.join(target,'runner.log'),'w')
    process=subprocess.Popen([SPECTRE,'input.scs','+escchars','-format','psfascii','-raw',psf,'+log',os.path.join(psf,'spectre.out'),'+lqtimeout','10','-maxw','5','-maxn','5'],cwd=netlist,stdout=log,stderr=subprocess.STDOUT,preexec_fn=os.setsid)
    expired=[]
    def stop():
      expired.append(True)
      try: os.killpg(process.pid,signal.SIGKILL)
      except OSError: pass
    timer=threading.Timer(60,stop);timer.start()
    try: code=process.wait()
    finally: timer.cancel();log.close()
    with open(os.path.join(target,'runner.log')) as f: tail=f.read()[-6000:]
    result={'job':job,'cell':cell,'source_sha256':expected,'executed_sha256':hashlib.sha256(modified).hexdigest(),'overrides':changes,'parameter_mode':'raw netlist literals; no CDF or geometry recalculation','directory':target,'exit_code':code,'timed_out':bool(expired),'log_tail':tail,'source':info['source'],'analyses':['dc'] if recipe=='dc' else info['analyses'],'recipe':recipe,'model_sections':info['model_sections']}
    result['success']=code==0 and not expired and bool(re.search(r'spectre completes with 0 errors,', tail))
    with open(os.path.join(target,'result.json'),'w') as f: json.dump(result,f)
    return result
if __name__=='__main__':
 try:
  req=json.loads(sys.stdin.read(32768));action=req['action']
  if action=='inspect': result=inspect(req['cell'])
  elif action=='run': result=run(req['cell'],req['sha256'],req.get('overrides',{}),req.get('recipe','saved'))
  elif action in ('waveform','op'):
   job=req['job']
   if not re.match(r'^[a-f0-9]{32}$',job): raise ValueError('Invalid job')
   target=os.path.join(RUNS,job)
   with open(os.path.join(target,'result.json')) as f: status=json.load(f)
   if not status['success']: raise ValueError('Simulation did not complete successfully')
   p=os.path.join(target,'psf', 'caOpInfo.info' if status.get('recipe')=='dc' else 'finalTimeOP.info') if action=='op' else os.path.join(target,'psf/tran.tran')
   if os.path.getsize(p)>20*1024*1024: raise ValueError('Waveform exceeds limit')
   with open(p) as f: result={'psfascii':f.read()}
  else: raise ValueError('Unsupported action')
  print(json.dumps(result))
 except Exception as e:
  print(json.dumps({'error':str(e)}));sys.exit(1)

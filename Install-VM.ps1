$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
@'
import re,subprocess
from pathlib import Path
root=Path.cwd()
config=root/'work/cadence-mcp-ssh/ssh_config'
bridge=(root/'outputs/cadence-mcp/bridge.il').read_text(encoding='utf-8')
remote_root=re.search(r'load\("([^"\n]+)/cadence-export.il"\)',bridge).group(1)
assert re.match(r'^/[a-zA-Z0-9_/-]+$',remote_root)
def ssh(command,data=None):
    subprocess.run(['ssh','-F',str(config),'cadence-vm',command],input=data,check=True)
ssh('mkdir -p '+remote_root+'/mailbox '+remote_root+'/runs')
files={'cadence-export.il':root/'outputs/circuit-atlas/dist/cadence-export.il'}
for name in ['bridge.il','guest_helper.py','simulation_helper.py','netlist_parameters.py']:
    files[name]=root/'outputs/cadence-mcp'/name
for name,path in files.items():
    ssh('cat > '+remote_root+'/'+name,path.read_bytes())
ssh('python '+remote_root+'/guest_helper.py status')
print('VM helpers installed. In CIW run: load("'+remote_root+'/bridge.il")')
'@ | & work/cadence-mcp-venv/Scripts/python.exe -
if ($LASTEXITCODE) { throw 'VM installation failed.' }

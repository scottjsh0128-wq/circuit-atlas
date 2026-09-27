$ErrorActionPreference = 'Stop'
$outputsDir = $PSScriptRoot
$workspaceDir = Split-Path $outputsDir -Parent

function Start-CircuitServer($port, $executable, $script, $directory) {
    if (Get-NetTCPConnection -LocalPort $port -State Listen -ErrorAction SilentlyContinue) { return }
    Start-Process -FilePath $executable -ArgumentList $script -WorkingDirectory $directory -WindowStyle Hidden -RedirectStandardOutput (Join-Path $directory 'server.stdout.log') -RedirectStandardError (Join-Path $directory 'server.stderr.log') | Out-Null
}

$nodePath = (Get-Command node -ErrorAction Stop).Source
Start-CircuitServer 4173 $nodePath 'server.mjs' (Join-Path $outputsDir 'circuit-atlas')
$pythonPath = Join-Path $workspaceDir 'work/cadence-mcp-venv/Scripts/python.exe'
Start-CircuitServer 4174 $pythonPath 'server.py' (Join-Path $outputsDir 'circuit-workbench')

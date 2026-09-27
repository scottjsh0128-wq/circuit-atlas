param(
    [Parameter(Mandatory=$true)][string]$VmAddress,
    [string]$VmUser = 'buet',
    [string]$VmHome = '/home/buet',
    [string]$SpectrePath = '/home/buet/cadence/MMSIM121/tools/bin/spectre'
)
$ErrorActionPreference = 'Stop'
Set-Location $PSScriptRoot
if ($VmAddress -notmatch '^\d{1,3}(\.\d{1,3}){3}$') { throw 'Provide the VM IPv4 address.' }
if ($VmUser -notmatch '^[a-z_][a-z0-9_-]*$' -or $VmHome -notmatch '^/[a-zA-Z0-9_/-]+$' -or $SpectrePath -notmatch '^/[a-zA-Z0-9_./-]+$') { throw 'Unsupported VM user/path characters.' }
Get-Command node,ssh,ssh-keygen,py -ErrorAction Stop | Out-Null
New-Item -ItemType Directory -Force work/cadence-mcp-ssh | Out-Null
if (!(Test-Path work/cadence-mcp-venv/Scripts/python.exe)) {
    py -3.12 -m venv work/cadence-mcp-venv
    if ($LASTEXITCODE) { throw 'Python 3.12 virtual environment creation failed.' }
}
& work/cadence-mcp-venv/Scripts/python.exe -m pip install -r outputs/cadence-mcp/requirements.txt
if ($LASTEXITCODE) { throw 'Dependency installation failed.' }
$keyPath = Join-Path $PSScriptRoot 'work/cadence-mcp-ssh/id_rsa'
if (!(Test-Path $keyPath)) {
    Write-Host 'Create a dedicated RSA SSH key. For unattended use, leave its passphrase empty.'
    ssh-keygen -t rsa -b 3072 -f $keyPath
    if ($LASTEXITCODE) { throw 'SSH key generation failed.' }
}
$config = @"
Host cadence-vm
    HostName $VmAddress
    HostKeyAlias $VmAddress
    User $VmUser
    IdentityFile "$($keyPath.Replace('\','/'))"
    IdentitiesOnly yes
    HostKeyAlgorithms +ssh-rsa
    PubkeyAcceptedAlgorithms +ssh-rsa
    BatchMode yes
    ConnectTimeout 5
    StrictHostKeyChecking yes
"@
[IO.File]::WriteAllText((Join-Path $PSScriptRoot 'work/cadence-mcp-ssh/ssh_config'),$config)
# Configure fixed helper paths for this clone; no existing Cadence files are edited here.
$files = @('outputs/cadence-mcp/server.py','outputs/cadence-mcp/bridge.il','outputs/cadence-mcp/simulation_helper.py','outputs/circuit-atlas/dist/cadence-import.js','outputs/circuit-atlas/dist/app.js')
foreach ($file in $files) {
    $path = Join-Path $PSScriptRoot $file
    $text = [IO.File]::ReadAllText($path).Replace('/home/buet/cadence/MMSIM121/tools/bin/spectre',$SpectrePath).Replace('/home/buet',$VmHome).Replace('HostKeyAlias=192.168.72.128',"HostKeyAlias=$VmAddress")
    [IO.File]::WriteAllText($path,$text)
}
Write-Host 'Local setup complete. Follow README steps to trust the VM key, register your public key and install the VM helpers.'

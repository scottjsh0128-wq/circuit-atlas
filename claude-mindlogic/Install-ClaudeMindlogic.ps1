# Installs the claude-ml command for the current Windows user.
# Adds Mindlogic models to Claude Code without changing the normal `claude` command or login.
$ErrorActionPreference = 'Stop'
Get-Command py, pyw, claude -ErrorAction Stop | Out-Null
& py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE) { throw 'Python 3.10 or newer is required (py -3).' }

$claudeDir = Join-Path $env:USERPROFILE '.claude'
$installDir = Join-Path $claudeDir 'mindlogic'
New-Item -ItemType Directory -Force $installDir | Out-Null
foreach ($name in 'router.py', 'claude-ml-launcher.ps1', 'claude-ml.cmd') {
    Copy-Item -Force (Join-Path $PSScriptRoot $name) (Join-Path $installDir $name)
}
# PowerShell prefers claude-ml.ps1 over claude-ml.cmd and the default execution policy blocks it,
# so only the .cmd (which runs the launcher with -ExecutionPolicy Bypass) may carry that name.
Remove-Item -Force -ErrorAction SilentlyContinue (Join-Path $installDir 'claude-ml.ps1')

$userPath = [Environment]::GetEnvironmentVariable('Path', 'User')
if (($userPath -split ';') -notcontains $installDir) {
    [Environment]::SetEnvironmentVariable('Path', (($userPath.TrimEnd(';'), $installDir) -join ';').TrimStart(';'), 'User')
    Write-Host "Added $installDir to your user PATH. Open a new terminal to use claude-ml."
}

# Reuse an existing FACTCHAT_API_KEY; otherwise ask once. The key is never printed.
$keyFile = Join-Path $claudeDir 'mindlogic.env'
$pattern = '^\s*(?:export\s+)?FACTCHAT_API_KEY\s*=\s*(.+?)\s*$'
$key = $env:FACTCHAT_API_KEY
foreach ($file in $keyFile, (Join-Path $env:USERPROFILE '.codex\.env')) {
    if (!$key -and (Test-Path $file)) {
        $match = Get-Content $file | Where-Object { $_ -match $pattern } | Select-Object -First 1
        if ($match -match $pattern) { $key = $Matches[1].Trim('"', "'") }
    }
}
if (!$key) {
    $secure = Read-Host 'Paste your Mindlogic Gateway API key (input hidden)' -AsSecureString
    $key = [Runtime.InteropServices.Marshal]::PtrToStringAuto([Runtime.InteropServices.Marshal]::SecureStringToBSTR($secure))
    if (!$key.Trim()) { throw 'No API key entered.' }
    [IO.File]::WriteAllText($keyFile, "FACTCHAT_API_KEY=$($key.Trim())`n")
    Write-Host "Saved the key to $keyFile"
}

[Net.ServicePointManager]::SecurityProtocol = [Net.ServicePointManager]::SecurityProtocol -bor [Net.SecurityProtocolType]::Tls12
# List the models this key can use and add them to the /model picker of claude-ml sessions.
$pickerFile = Join-Path $installDir 'picker-settings.json'
try {
    $models = Invoke-RestMethod -Uri 'https://factchat-cloud.mindlogic.ai/v1/gateway/models/?type=llm' `
        -Headers @{ Authorization = "Bearer $($key.Trim())" } -TimeoutSec 20
    $data = if ($models.data) { $models.data } else { $models }
    $ids = @($data | Where-Object { $_.type -eq 'llm' } | ForEach-Object { [string]$_.id } | Sort-Object -Unique)
    if (!$ids) { throw 'no llm models returned' }
    # behavesAs lets this Claude Code version offer a model it does not know; it does not change the model sent.
    $rows = @($ids | ForEach-Object { @{ model = "mindlogic/$_"; label = "Mindlogic $([char]0x00B7) $_";
        description = 'Mindlogic Gateway (claude-ml)'; behavesAs = 'claude-sonnet-4-5' } })
    [IO.File]::WriteAllText($pickerFile, (@{ modelPicker = @{ options = $rows } } | ConvertTo-Json -Depth 6))
    Write-Host 'Added to the claude-ml /model picker:'
    $ids | ForEach-Object { Write-Host "  mindlogic/$_" }
} catch {
    Write-Warning "Could not list Mindlogic models ($($_.Exception.Message)). Check the key, network, or balance, then run this installer again."
}
Write-Host ''
Write-Host 'Done. Open a new terminal and run:  claude-ml   (plain `claude` is unchanged)'
Write-Host 'In /model, press s on a Mindlogic row to use it for this session only.'

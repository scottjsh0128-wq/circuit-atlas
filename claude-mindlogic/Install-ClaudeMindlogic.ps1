# Installs the claude-ml command for the current Windows user.
# Adds Mindlogic models to Claude Code without changing the normal `claude` command or login.
$ErrorActionPreference = 'Stop'
Get-Command py, pyw, claude -ErrorAction Stop | Out-Null
& py -3 -c "import sys; sys.exit(0 if sys.version_info >= (3, 10) else 1)"
if ($LASTEXITCODE) { throw 'Python 3.10 or newer is required (py -3).' }

$claudeDir = Join-Path $env:USERPROFILE '.claude'
$installDir = Join-Path $claudeDir 'mindlogic'
New-Item -ItemType Directory -Force $installDir | Out-Null
foreach ($name in 'router.py', 'claude-ml.ps1', 'claude-ml.cmd') {
    Copy-Item -Force (Join-Path $PSScriptRoot $name) (Join-Path $installDir $name)
}

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
# Show which models this key can use, as claude-ml model names.
try {
    $models = Invoke-RestMethod -Uri 'https://factchat-cloud.mindlogic.ai/v1/gateway/models/?type=llm' `
        -Headers @{ Authorization = "Bearer $($key.Trim())" } -TimeoutSec 20
    $data = if ($models.data) { $models.data } else { $models }
    Write-Host 'Mindlogic models available to this key:'
    $data | Where-Object { $_.type -eq 'llm' } | ForEach-Object { Write-Host "  mindlogic/$($_.id)" }
} catch {
    Write-Warning "Could not list Mindlogic models ($($_.Exception.Message)). Check the key, network, or balance."
}
Write-Host ''
Write-Host 'Done. Run:  claude-ml --model mindlogic/<model-id>   (plain `claude` is unchanged)'

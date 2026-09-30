# Installs the claude-ml command for the current Windows user.
# Adds Mindlogic models to Claude Code without changing the normal `claude` command or login.
# -Models picks which Mindlogic models appear in /model (in that order); the choice is remembered.
# -AllModels clears it so every model the key can use is listed again.
# -Global also adds the models to plain `claude` and the desktop app's Code tab, and starts the router at login.
# -RemoveGlobal undoes -Global (claude-ml keeps working).
param([string[]]$Models, [switch]$AllModels, [switch]$Global, [switch]$RemoveGlobal)
$ErrorActionPreference = 'Stop'
# Windows PowerShell 5.1 otherwise writes some arrays as {"value":[...],"Count":n}.
Remove-TypeData System.Array -ErrorAction SilentlyContinue
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

$port = 18763
$routerUrl = "http://127.0.0.1:$port"
$tokenFile = Join-Path $claudeDir 'mindlogic-router.token'
$settingsFile = Join-Path $claudeDir 'settings.json'
$startupLink = Join-Path ([Environment]::GetFolderPath('Startup')) 'Mindlogic router for Claude Code.lnk'

function Read-Settings {
    if (!(Test-Path $settingsFile) -or !([IO.File]::ReadAllText($settingsFile).Trim())) { return [pscustomobject]@{} }
    try { return [IO.File]::ReadAllText($settingsFile) | ConvertFrom-Json }
    catch { throw "Could not parse $settingsFile as JSON. Nothing was changed." }
}

function Save-Settings($settings) {
    if (Test-Path $settingsFile) { Copy-Item $settingsFile "$settingsFile.backup-$(Get-Date -Format yyyyMMdd-HHmmss)" }
    [IO.File]::WriteAllText($settingsFile, ($settings | ConvertTo-Json -Depth 32))
}

function Test-Router {
    try {
        $request = [Net.WebRequest]::Create("$routerUrl/health")
        $request.Proxy = $null
        $request.Timeout = 2000
        $response = $request.GetResponse()
        $response.Close()
        return $true
    } catch { return $false }
}

if ($RemoveGlobal) {
    $settings = Read-Settings
    if ($settings.env) {
        if ($settings.env.ANTHROPIC_BASE_URL -eq $routerUrl) { $settings.env.PSObject.Properties.Remove('ANTHROPIC_BASE_URL') }
        if ("$($settings.env.ANTHROPIC_CUSTOM_HEADERS)" -like 'X-Mindlogic-Router-Token:*') { $settings.env.PSObject.Properties.Remove('ANTHROPIC_CUSTOM_HEADERS') }
        if (!@($settings.env.PSObject.Properties).Count) { $settings.PSObject.Properties.Remove('env') }
    }
    if ($settings.modelPicker -and !@($settings.modelPicker.options | Where-Object { "$($_.model)" -notlike 'mindlogic/*' }).Count) {
        $settings.PSObject.Properties.Remove('modelPicker')
    }
    # Plain claude can no longer reach Mindlogic, so do not leave it defaulting to a Mindlogic model.
    if ("$($settings.model)" -like 'mindlogic/*') { $settings.PSObject.Properties.Remove('model') }
    Save-Settings $settings
    Remove-Item -Force -ErrorAction SilentlyContinue $startupLink
    Write-Host 'Removed Mindlogic models from plain claude and the desktop app. claude-ml still works.'
    exit 0
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
# List the models this key can use and add them to the /model picker of claude-ml sessions.
$pickerFile = Join-Path $installDir 'picker-settings.json'
try {
    $listing = Invoke-RestMethod -Uri 'https://factchat-cloud.mindlogic.ai/v1/gateway/models/?type=llm' `
        -Headers @{ Authorization = "Bearer $($key.Trim())" } -TimeoutSec 20
    $data = if ($listing.data) { $listing.data } else { $listing }
    $ids = @($data | Where-Object { $_.type -eq 'llm' } | ForEach-Object { [string]$_.id } | Sort-Object -Unique)
    if (!$ids) { throw 'no llm models returned' }
    $choiceFile = Join-Path $installDir 'models.txt'
    if ($AllModels) { Remove-Item -Force -ErrorAction SilentlyContinue $choiceFile }
    if ($Models) {
        $wanted = @($Models | ForEach-Object { $_ -split '[,\s]+' } | Where-Object { $_ } | ForEach-Object { $_ -replace '^mindlogic/', '' })
        [IO.File]::WriteAllText($choiceFile, ($wanted -join "`n") + "`n")
    }
    if (Test-Path $choiceFile) {
        $wanted = @(Get-Content $choiceFile | ForEach-Object { $_.Trim() } | Where-Object { $_ })
        $missing = @($wanted | Where-Object { $ids -notcontains $_ })
        if ($missing) { Write-Warning "Not available to this key, skipped: $($missing -join ', ')" }
        $ids = @($wanted | Where-Object { $ids -contains $_ })
        if (!$ids) { throw 'none of the chosen models are available' }
    }
    # behavesAs lets this Claude Code version offer a model it does not know; it does not change the model sent.
    $rows = @($ids | ForEach-Object { @{ model = "mindlogic/$_"; label = "Mindlogic $([char]0x00B7) $_";
        description = 'Mindlogic Gateway'; behavesAs = 'claude-sonnet-4-5' } })
    [IO.File]::WriteAllText($pickerFile, (@{ modelPicker = @{ options = $rows } } | ConvertTo-Json -Depth 6))
    Write-Host 'Added to the claude-ml /model picker:'
    $ids | ForEach-Object { Write-Host "  mindlogic/$_" }
} catch {
    Write-Warning "Could not list Mindlogic models ($($_.Exception.Message)). Check the key, network, or balance, then run this installer again."
}

if ($Global) {
    if (!$rows) { throw 'The Mindlogic model list is unavailable, so global settings were not changed.' }
    if (!(Test-Path $tokenFile) -or !([IO.File]::ReadAllText($tokenFile).Trim())) {
        $bytes = New-Object byte[] 32
        [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
        [IO.File]::WriteAllText($tokenFile, ([Convert]::ToBase64String($bytes) -replace '[+/=]', ''))
    }
    $token = [IO.File]::ReadAllText($tokenFile).Trim()

    # Start the router at every login, hidden, and right now.
    $routerArgs = "-3 `"$(Join-Path $installDir 'router.py')`" --port $port --token-file `"$tokenFile`""
    $shortcut = (New-Object -ComObject WScript.Shell).CreateShortcut($startupLink)
    $shortcut.TargetPath = (Get-Command pyw).Source
    $shortcut.Arguments = $routerArgs
    $shortcut.WindowStyle = 7
    $shortcut.Save()
    if (!(Test-Router)) {
        Start-Process -FilePath (Get-Command pyw).Source -ArgumentList $routerArgs -WindowStyle Hidden
        for ($i = 0; $i -lt 50 -and !(Test-Router); $i++) { Start-Sleep -Milliseconds 100 }
        if (!(Test-Router)) { throw 'The Mindlogic router did not start, so global settings were not changed.' }
    }

    # Claude models still go to Anthropic with your own login; only mindlogic/* models go to Mindlogic.
    $settings = Read-Settings
    if (!$settings.env) { $settings | Add-Member -Force env ([pscustomobject]@{}) }
    $settings.env | Add-Member -Force ANTHROPIC_BASE_URL $routerUrl
    $settings.env | Add-Member -Force ANTHROPIC_CUSTOM_HEADERS "X-Mindlogic-Router-Token: $token"
    $settings | Add-Member -Force modelPicker ([pscustomobject]@{ options = $rows })
    Save-Settings $settings
    Write-Host ''
    Write-Host "Added the Mindlogic models to plain claude and the desktop app's Code tab (restart the app)."
    Write-Host 'The router now starts at login. To undo:  Install-ClaudeMindlogic.ps1 -RemoveGlobal'
} else {
    Write-Host ''
    Write-Host 'Done. Open a new terminal and run:  claude-ml   (plain `claude` is unchanged)'
    Write-Host 'In /model, press s on a Mindlogic row to use it for this session only.'
}

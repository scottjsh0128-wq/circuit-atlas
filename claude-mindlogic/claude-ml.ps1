# Start Claude Code with Mindlogic models added next to the normal Claude models.
# Plain `claude` is untouched; only sessions started with claude-ml use the local router.
$ErrorActionPreference = 'Stop'
$port = if ($env:MINDLOGIC_ROUTER_PORT) { [int]$env:MINDLOGIC_ROUTER_PORT } else { 18763 }
$claudeDir = Join-Path $env:USERPROFILE '.claude'
$tokenFile = Join-Path $claudeDir 'mindlogic-router.token'
$logFile = Join-Path $claudeDir 'mindlogic-router.log'
$router = Join-Path $PSScriptRoot 'router.py'

New-Item -ItemType Directory -Force $claudeDir | Out-Null
if (!(Test-Path $tokenFile) -or !([IO.File]::ReadAllText($tokenFile).Trim())) {
    $bytes = New-Object byte[] 32
    [Security.Cryptography.RandomNumberGenerator]::Create().GetBytes($bytes)
    [IO.File]::WriteAllText($tokenFile, ([Convert]::ToBase64String($bytes) -replace '[+/=]', ''))
}
$token = [IO.File]::ReadAllText($tokenFile).Trim()

function Test-Router {
    try {
        $request = [Net.WebRequest]::Create("http://127.0.0.1:$port/health")
        $request.Proxy = $null
        $request.Timeout = 2000
        $response = $request.GetResponse()
        $ok = [int]$response.StatusCode -eq 200
        $response.Close()
        return $ok
    } catch { return $false }
}

if (!(Test-Router)) {
    # pyw has no console, so Ctrl+C in Claude Code or closing the terminal leaves the router running.
    Start-Process -FilePath 'pyw' -WindowStyle Hidden `
        -ArgumentList @('-3', "`"$router`"", '--port', $port, '--token-file', "`"$tokenFile`"") `
        -RedirectStandardOutput $logFile -RedirectStandardError "$logFile.err" | Out-Null
    for ($i = 0; $i -lt 50 -and !(Test-Router); $i++) { Start-Sleep -Milliseconds 100 }
    if (!(Test-Router)) { throw "Mindlogic router did not start. Check $logFile.err" }
}

$env:ANTHROPIC_BASE_URL = "http://127.0.0.1:$port"
$env:ANTHROPIC_CUSTOM_HEADERS = "X-Mindlogic-Router-Token: $token"
if ($env:MINDLOGIC_DEFAULT_MODEL -and !($args -contains '--model')) {
    & claude --model $env:MINDLOGIC_DEFAULT_MODEL @args
} else {
    & claude @args
}
exit $LASTEXITCODE

<#
.SYNOPSIS
ReturnOps AU demo machine: README "Deploy from zero" steps 1 to 5 in order, with checks.

.DESCRIPTION
For the Windows demo machine only (Windows PowerShell 5.1 or later). It runs
the README commands of steps 1 to 5 in order and stops at the first failure
with the reason. The manual README steps stay the fallback.

It never reads, prints or stores a model API key or a session token, and it
prints no .env value except the two port numbers. Signing in to the web
frontend stays manual (README step 4). For the model showcase, set the
RETURNOPS_MODEL_* variables in this PowerShell window first (docs/45, 2.3
step 2) and pass -ModelShowcase to start; the variables pass to the demo API
window unread.

Actions (from the package root):
  check    Report the prerequisites, ports and old data. Changes nothing.
  prepare  T-40 minutes. Step 1 (venv, locked install, .env with API_PORT=8001),
           step 2 (Compose database, migration, health checks) and npm ci.
           Safe to run again.
  start    T-5 minutes. Step 3 (provision tmp\demo-shop once, demo API window
           on port 8000) and step 4 (web window on port 5173, or on the first
           usable port up to 5399 when 5173 cannot be opened). Sessions last
           899 s from provisioning.
  fresh    T-5 minutes, all in one: opens Docker Desktop if Docker does not
           answer, then stop -RemoveData, prepare and start. The data of an
           earlier run is deleted. tools\demo\start-demo.cmd runs it on a
           double-click.
  s5       Step 5. Ctrl+C to the demo API window, provision tmp\demo-cups once,
           and a driver window that keeps its API on port 8000.
  stop     Ctrl+C to the driver and demo API windows, close all three windows,
           docker compose stop (the data is kept).
           -RemoveData also removes this folder's Compose containers and
           database volume and deletes tmp\demo-shop and tmp\demo-cups.
           tools\demo\stop-demo.cmd runs stop -RemoveData on a double-click.

Railway (docs/46 section 9, docs/15 PD-03): the Railway service runs
tools/railway/start.py. Since 31 October 2026 a deployment keeps the previous one's
data and passwords and issues new 899 s sessions; cloud-fresh starts a fresh
demonstration. Run `railway login`, then `railway link` once in this folder,
and register this machine's SSH key once (README, Railway deployment).
  cloud        Deploys this folder (railway up) and copies the new sessions to
               tmp\railway-shop through railway ssh, never showing them.
               tools\demo\cloud-demo.cmd runs it on a double-click.
  cloud-fresh  Clears the kept data (railway ssh), then redeploys: a fresh
               demonstration with new sessions, copied as for cloud.
  cloud-tokens Copies the current sessions again; warns if they have expired.
  -Url https://... is the service's public address; without it the address is read
               from railway status. The copied customer session is then tried
               there until the new deployment accepts it.
  -Service name is the app service these act on (default returnops-demo-app),
               whichever service railway link chose; never the database.

Usage:
  powershell -NoProfile -ExecutionPolicy Bypass -File tools\demo\demo.ps1 prepare

Each package folder gets its own Compose project name, so its database
volume is never shared with another checkout.

R.05.b demonstration; deployment model PD-02 (docs/15); NFR-009 (no secret
is displayed). AI-assisted implementation; author shuxiachai.
#>
param(
    [Parameter(Mandatory = $true, Position = 0)]
    [ValidateSet('check', 'prepare', 'start', 'fresh', 's5', 'stop', 'cloud', 'cloud-fresh', 'cloud-tokens')]
    [string]$Action,
    [switch]$ModelShowcase,
    [switch]$RemoveData,
    [string]$Url,
    [ValidatePattern('^[A-Za-z0-9][A-Za-z0-9_-]*$')]
    [string]$Service = 'returnops-demo-app'
)

Set-StrictMode -Version 2
$ErrorActionPreference = 'Stop'
# Railway shows domains without a scheme; HttpWebRequest needs one.
if ($Url -and $Url -notmatch '^[A-Za-z][A-Za-z0-9+.-]*://') { $Url = 'https://' + $Url }

$Root = (Resolve-Path -LiteralPath (Join-Path $PSScriptRoot '..\..')).Path
Set-Location -LiteralPath $Root
$Py = Join-Path $Root '.venv\Scripts\python.exe'
$EnvFile = Join-Path $Root '.env'
$Tmp = Join-Path $Root 'tmp'
$Shop = Join-Path $Tmp 'demo-shop'
$Cups = Join-Path $Tmp 'demo-cups'
$CloudShop = Join-Path $Tmp 'railway-shop'
$StateDir = Join-Path $Tmp 'demo-script'
$Web = Join-Path $Root 'apps\web'
$SessionSeconds = 899
$VersionCode = 'import sys;print(*sys.version_info[:3],sep=chr(46))'

$hasher = [System.Security.Cryptography.SHA256]::Create()
$digest = $hasher.ComputeHash([System.Text.Encoding]::UTF8.GetBytes($Root.ToLowerInvariant()))
$Project = 'returnops-demo-' + (-join ($digest[0..3] | ForEach-Object { $_.ToString('x2') }))
$Volume = $Project + '_postgres-data'

$script:Problems = 0

# -- output ---------------------------------------------------------------------

function Show-Step([string]$Text) { Write-Host ''; Write-Host "== $Text" -ForegroundColor Cyan }
function Show-Ok([string]$Text) { Write-Host "  OK    $Text" -ForegroundColor Green }
function Show-Info([string]$Text) { Write-Host "        $Text" }
function Show-Warn([string]$Text) { Write-Host "  WARN  $Text" -ForegroundColor Yellow }
function Show-Problem([string]$Text) { Write-Host "  STOP  $Text" -ForegroundColor Red; $script:Problems++ }
function Stop-Script([string]$Text) { Write-Host "  STOP  $Text" -ForegroundColor Red; exit 1 }

# -- helpers --------------------------------------------------------------------

function Invoke-Checked([string]$What, [scriptblock]$Command) {
    & $Command
    if ($LASTEXITCODE -ne 0) { Stop-Script "$What failed (exit code $LASTEXITCODE). See the output above." }
}

# Runs a native command whose failure is an answer, not an error; stderr is dropped.
# A command that does not exist leaves LASTEXITCODE unchanged, so it starts at -1.
function Invoke-Quiet([scriptblock]$Command) {
    $ErrorActionPreference = 'Continue'
    $global:LASTEXITCODE = -1
    $output = & $Command 2>$null
    return [pscustomobject]@{ Code = $LASTEXITCODE; Output = (@($output) -join "`n").Trim() }
}

function Read-DotEnv {
    $values = @{}
    if (Test-Path -LiteralPath $EnvFile) {
        foreach ($line in [System.IO.File]::ReadAllLines($EnvFile)) {
            if ($line -match '^\s*([A-Za-z_][A-Za-z0-9_]*)\s*=(.*)$') { $values[$Matches[1]] = $Matches[2].Trim() }
        }
    }
    return $values
}

function Get-FileDigest([string[]]$Paths) {
    $text = ($Paths | ForEach-Object { (Get-FileHash -Algorithm SHA256 -LiteralPath $_).Hash }) -join ' '
    return $text
}

function Test-Listening([int]$Port) {
    try { return [bool](Get-NetTCPConnection -LocalPort $Port -State Listen -ErrorAction Stop) } catch { return $false }
}

# Windows can reserve whole port ranges after Docker or WSL starts (netsh
# interface ipv4 show excludedportrange protocol=tcp); nothing listens there,
# but opening such a port fails. So a free port is checked by opening it on the
# loopback addresses.
function Test-PortOpenable([int]$Port) {
    $addresses = @([System.Net.IPAddress]::Loopback)
    if ([System.Net.Sockets.Socket]::OSSupportsIPv6) { $addresses += [System.Net.IPAddress]::IPv6Loopback }
    foreach ($address in $addresses) {
        $listener = New-Object System.Net.Sockets.TcpListener($address, $Port)
        try { $listener.Start() } catch { return $false } finally { $listener.Stop() }
    }
    return $true
}

$ReservedHint = 'Windows has reserved it (netsh interface ipv4 show excludedportrange protocol=tcp); the ranges change when Windows restarts.'

# The web frontend's port: 5173 (apps/web/vite.config.ts), or the first usable
# port up to 5399; 0 when there is none. The proxy target stays 8000.
function Select-WebPort {
    $listening = @()
    try { $listening = @(Get-NetTCPConnection -State Listen -ErrorAction Stop | ForEach-Object { [int]$_.LocalPort }) } catch { }
    foreach ($port in 5173..5399) {
        if ($listening -notcontains $port -and (Test-PortOpenable $port)) { return $port }
    }
    return 0
}

function Get-WebPort {
    $path = Join-Path $StateDir 'web.port'
    if (Test-Path -LiteralPath $path) { return [int][System.IO.File]::ReadAllText($path) }
    return 5173
}

# The engine version, or $null. While Docker Desktop is starting, or after it
# has failed to start, docker version can wait without end, so it gets 15 s.
function Test-DockerEngine {
    $info = New-Object System.Diagnostics.ProcessStartInfo('docker.exe', 'version --format "{{.Server.Version}}"')
    $info.UseShellExecute = $false
    $info.CreateNoWindow = $true
    $info.RedirectStandardOutput = $true
    $info.RedirectStandardError = $true
    try { $process = [System.Diagnostics.Process]::Start($info) } catch { return $null }
    $output = $process.StandardOutput.ReadToEndAsync()
    $null = $process.StandardError.ReadToEndAsync()
    if (-not $process.WaitForExit(15000)) { try { $process.Kill() } catch { }; return $null }
    $version = $output.Result.Trim()
    if ($process.ExitCode -eq 0 -and $version) { return $version }
    return $null
}

function Wait-PortFree([int]$Port, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        if (-not (Test-Listening $Port)) { return $true }
        Start-Sleep -Milliseconds 500
    }
    return (-not (Test-Listening $Port))
}

# Direct HTTP without the system proxy; returns $null when nothing answers. A bearer
# token goes only into the request header and is never shown.
function Get-Http([string]$Url, [string]$Bearer = '') {
    try {
        $request = [System.Net.HttpWebRequest]::Create($Url)
        $request.Proxy = $null
        $request.Timeout = 5000
        if ($Bearer) { $request.Headers.Add('Authorization', 'Bearer ' + $Bearer) }
        $response = $request.GetResponse()
        try {
            $reader = New-Object System.IO.StreamReader($response.GetResponseStream())
            return [pscustomobject]@{ Status = [int]$response.StatusCode; Body = $reader.ReadToEnd() }
        } finally { $response.Close() }
    } catch [System.Net.WebException] {
        $failed = $_.Exception.Response
        if ($failed) { $code = [int]$failed.StatusCode; $failed.Close(); return [pscustomobject]@{ Status = $code; Body = '' } }
        return $null
    } catch {
        return $null
    }
}

function Wait-Http([string]$Url, [string]$Expect, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $answer = Get-Http $Url
        if ($answer -and $answer.Status -eq 200 -and $answer.Body.Contains($Expect)) { return $true }
        Start-Sleep -Seconds 1
    }
    return $false
}

function Get-ComposeContainers([switch]$Running) {
    $arguments = @('ps', '-aq', '--filter', "label=com.docker.compose.project=$Project")
    if ($Running) { $arguments += @('--filter', 'status=running') }
    $answer = Invoke-Quiet { docker @arguments }
    if ($answer.Code -ne 0 -or -not $answer.Output) { return @() }
    return @($answer.Output -split "`n" | Where-Object { $_ })
}

function Test-VolumeExists {
    $answer = Invoke-Quiet { docker volume inspect --format '{{.Name}}' $Volume }
    return ($answer.Code -eq 0 -and $answer.Output -eq $Volume)
}

function Format-Time([datetime]$Value) { return $Value.ToString('HH:mm:ss') }

function Save-Time([string]$Name) {
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $StateDir "$Name.time"), (Get-Date).ToString('o'))
}

function Get-SavedTime([string]$Name) {
    $path = Join-Path $StateDir "$Name.time"
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    return [datetime]::Parse([System.IO.File]::ReadAllText($path), $null, [System.Globalization.DateTimeStyles]::RoundtripKind)
}

# demo.py writes auth.json before it registers the identities, so only the time this
# script saves after a successful provision, no older than auth.json, shows they work.
function Test-Provisioned([string]$Name, [string]$Folder) {
    $saved = Get-SavedTime $Name
    if (-not $saved) { return $false }
    return ($saved -ge (Get-Item -LiteralPath (Join-Path $Folder 'auth.json')).LastWriteTime)
}

# -- the three windows ----------------------------------------------------------
# Each window is a PowerShell console started by this script. Its record holds
# the process ID and start time, so a reused process ID is never acted on.

function Format-Literal([string]$Text) { return "'" + $Text.Replace("'", "''") + "'" }

function Start-Window([string]$Name, [string]$Title, [string]$Body) {
    # Parenthesised: the comma binds tighter than +.
    $lines = @(
        ('$Host.UI.RawUI.WindowTitle = ' + (Format-Literal $Title)),
        ('Set-Location -LiteralPath ' + (Format-Literal $Root)),
        $Body
    )
    $encoded = [Convert]::ToBase64String([System.Text.Encoding]::Unicode.GetBytes(($lines -join "`n")))
    $process = Start-Process -FilePath 'powershell.exe' -PassThru -ArgumentList @(
        '-NoProfile', '-NoExit', '-ExecutionPolicy', 'Bypass', '-EncodedCommand', $encoded)
    New-Item -ItemType Directory -Force -Path $StateDir | Out-Null
    $record = "$($process.Id) $($process.StartTime.ToFileTimeUtc())"
    [System.IO.File]::WriteAllText((Join-Path $StateDir "$Name.window"), $record)
    return $process
}

function Get-Window([string]$Name) {
    $path = Join-Path $StateDir "$Name.window"
    if (-not (Test-Path -LiteralPath $path)) { return $null }
    $id, $started = [System.IO.File]::ReadAllText($path).Split(' ')
    $process = Get-Process -Id ([int]$id) -ErrorAction SilentlyContinue
    # After a restart the ID may belong to a process whose start time cannot be read
    # (Access denied): that record is stale, not a reason to stop the script.
    $same = $false
    if ($process) { try { $same = $process.StartTime.ToFileTimeUtc() -eq [long]$started } catch { $same = $false } }
    if ($same) { return $process }
    Remove-Item -LiteralPath $path -Force
    return $null
}

function Get-WindowCommands([System.Diagnostics.Process]$Window) {
    return @(Get-CimInstance Win32_Process -Filter "ParentProcessId=$($Window.Id)" |
        Where-Object { $_.Name -ne 'conhost.exe' })
}

# Ctrl+C reaches every process of the window's console, as if typed there. The
# helper is a separate process, because attaching to a console detaches it from
# this one.
function Send-CtrlC([System.Diagnostics.Process]$Window) {
    $code = 'import ctypes,sys,time;k=ctypes.windll.kernel32;k.FreeConsole();' +
        'ok=k.AttachConsole(int(sys.argv[1])) and k.SetConsoleCtrlHandler(None,1) and k.GenerateConsoleCtrlEvent(0,0);' +
        'time.sleep(1);sys.exit(0 if ok else 1)'
    $answer = Invoke-Quiet { & $Py -I -c $code $Window.Id }
    return ($answer.Code -eq 0)
}

# The window and every process started under it, each with its start time, so
# a reused process ID is never taken for one of them.
function Get-WindowTree([System.Diagnostics.Process]$Window) {
    $all = @(Get-CimInstance Win32_Process)
    $root = [pscustomobject]@{ Id = $Window.Id; Started = $Window.StartTime.ToFileTimeUtc() }
    $tree = @($root)
    $seen = @{ $Window.Id = $true }
    $queue = New-Object System.Collections.Queue
    $queue.Enqueue($root)
    while ($queue.Count -gt 0) {
        $parent = $queue.Dequeue()
        foreach ($child in @($all | Where-Object { $_.ParentProcessId -eq $parent.Id -and -not $seen.ContainsKey([int]$_.ProcessId) })) {
            try { $started = (Get-Process -Id $child.ProcessId -ErrorAction Stop).StartTime.ToFileTimeUtc() } catch { continue }
            if ($started -lt $parent.Started) { continue }
            $entry = [pscustomobject]@{ Id = [int]$child.ProcessId; Started = $started }
            $seen[$entry.Id] = $true
            $tree += $entry
            $queue.Enqueue($entry)
        }
    }
    return $tree
}

function Test-TreeEnded([object[]]$Tree, [int]$Seconds) {
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ($true) {
        $alive = @($Tree | Where-Object {
            try { (Get-Process -Id $_.Id -ErrorAction Stop).StartTime.ToFileTimeUtc() -eq $_.Started } catch { $false }
        })
        if ($alive.Count -eq 0) { return $true }
        if ((Get-Date) -ge $deadline) { return $false }
        Start-Sleep -Milliseconds 500
    }
}

function Close-Window([string]$Name, [string]$Label, [switch]$CtrlC, [int]$Seconds = 60) {
    $hadRecord = Test-Path -LiteralPath (Join-Path $StateDir "$Name.window")
    $window = Get-Window $Name
    if (-not $window) {
        if ($hadRecord) { Show-Info "The $Label window had already ended." }
        return
    }
    if ($CtrlC -and @(Get-WindowCommands $window).Count -gt 0) {
        if (Send-CtrlC $window) {
            Show-Info "Ctrl+C sent to the $Label window; waiting up to $Seconds s for it to finish."
            $deadline = (Get-Date).AddSeconds($Seconds)
            while ((Get-Date) -lt $deadline -and @(Get-WindowCommands $window).Count -gt 0) { Start-Sleep -Milliseconds 500 }
            if (@(Get-WindowCommands $window).Count -gt 0) { Show-Warn "The $Label did not finish after Ctrl+C; it is ended now." }
        } else {
            Show-Warn "Ctrl+C could not be sent to the $Label window; it is ended now."
        }
    }
    # taskkill's answer is not trusted: the record goes only once the window and
    # every process under it have ended. Otherwise the script stops here, before
    # any Compose or folder cleanup, and keeps the record for a later stop.
    $tree = Get-WindowTree $window
    Invoke-Quiet { taskkill.exe /PID $window.Id /T /F } | Out-Null
    if (-not (Test-TreeEnded $tree 15)) {
        Stop-Script "The $Label window (process $($window.Id)) or a process under it is still running, so nothing was deleted. Close that window, then run stop again."
    }
    Remove-Item -LiteralPath (Join-Path $StateDir "$Name.window") -Force -ErrorAction SilentlyContinue
    Show-Ok "$Label window closed."
}

# Waits for a window's service to answer; 'ended' when its command has already exited.
function Wait-WindowReady([System.Diagnostics.Process]$Window, [string]$Url, [string]$Expect, [int]$Seconds) {
    $begun = Get-Date
    $seen = $false
    while (((Get-Date) - $begun).TotalSeconds -lt $Seconds) {
        $answer = Get-Http $Url
        if ($answer -and $answer.Status -eq 200 -and $answer.Body.Contains($Expect)) { return 'ready' }
        if (@(Get-WindowCommands $Window).Count -gt 0) { $seen = $true }
        elseif ($seen -or ((Get-Date) - $begun).TotalSeconds -gt 15) { return 'ended' }
        Start-Sleep -Seconds 1
    }
    return 'timeout'
}

# -- checks ---------------------------------------------------------------------

function Test-PythonVersion([string]$Version) {
    if ($Version -notmatch '^3\.12\.(\d+)$') { return $false }
    return ([int]$Matches[1] -ge 4)
}

function Find-BasePython {
    $launcher = Get-Command py.exe -ErrorAction SilentlyContinue
    if ($launcher) {
        $answer = Invoke-Quiet { & $launcher.Source -3.12 -c $VersionCode }
        if ($answer.Code -eq 0) { return [pscustomobject]@{ Exe = $launcher.Source; Prefix = @('-3.12'); Version = $answer.Output } }
    }
    $python = Get-Command python.exe -ErrorAction SilentlyContinue
    if ($python) {
        $answer = Invoke-Quiet { & $python.Source -c $VersionCode }
        if ($answer.Code -eq 0) { return [pscustomobject]@{ Exe = $python.Source; Prefix = @(); Version = $answer.Output } }
    }
    return $null
}

function Test-NodeVersion([string]$Version) {
    if ($Version -notmatch '^v(\d+)\.(\d+)\.(\d+)$') { return $false }
    $major, $minor, $patch = [int]$Matches[1], [int]$Matches[2], [int]$Matches[3]
    if ($major -ge 26) { return $true }
    if ($major -eq 24) { return ($minor -ge 15) }
    if ($major -eq 22) { return ($minor -gt 22 -or ($minor -eq 22 -and $patch -ge 2)) }
    return $false
}

function Test-Prerequisites {
    Show-Step "Prerequisites (README step 0); package root $Root"
    foreach ($file in @('compose.yaml', 'requirements-dev.lock', 'tools\environment\local.py', 'apps\web\package-lock.json')) {
        if (-not (Test-Path -LiteralPath (Join-Path $Root $file))) { Show-Problem "$file is missing; run this script from an unpacked ReturnOps package." }
    }

    if (Test-Path -LiteralPath $Py) {
        $answer = Invoke-Quiet { & $Py -c $VersionCode }
        if (Test-PythonVersion $answer.Output) { Show-Ok "Python $($answer.Output) in .venv" }
        else { Show-Problem "The .venv Python is '$($answer.Output)'; CPython 3.12.4 or a later 3.12 is required. Delete .venv and run prepare with a suitable Python." }
    } else {
        $base = Find-BasePython
        if ($base -and (Test-PythonVersion $base.Version)) { Show-Ok "Python $($base.Version) ($($base.Exe)) will create .venv" }
        elseif ($base) { Show-Problem "Python $($base.Version) found; CPython 3.12.4 or a later 3.12 is required (py -3.12 or python)." }
        else { Show-Problem 'No Python found; install CPython 3.12.4 or a later 3.12.' }
    }

    $engine = Test-DockerEngine
    if ($engine) { Show-Ok "Docker engine $engine" }
    else { Show-Problem 'Docker does not answer; start Docker Desktop and wait until it reports running.' }
    $compose = Invoke-Quiet { docker compose version --short }
    if ($compose.Code -eq 0 -and $compose.Output -match '^v?(\d+)\.' -and [int]$Matches[1] -ge 2) { Show-Ok "Docker Compose $($compose.Output)" }
    else { Show-Problem 'Docker Compose v2 or later (docker compose) is not available.' }

    $node = Invoke-Quiet { node --version }
    if ($node.Code -ne 0) { Show-Problem 'Node.js is not installed (needs ^22.22.2, ^24.15.0 or >=26.0.0).' }
    elseif (Test-NodeVersion $node.Output) { Show-Ok "Node.js $($node.Output)" }
    else { Show-Warn "Node.js $($node.Output) is outside ^22.22.2 || ^24.15.0 || >=26.0.0 (apps/web/package.json); npm warns. Upgrade before the demonstration." }
    $npm = Invoke-Quiet { npm.cmd --version }
    if ($npm.Code -ne 0) { Show-Problem 'npm is not available.' }
    elseif ($npm.Output -match '^(\d+)\.' -and [int]$Matches[1] -ge 10) { Show-Ok "npm $($npm.Output)" }
    else { Show-Warn "npm $($npm.Output); npm 10 or later is expected." }

    $values = Read-DotEnv
    $dbPort = 5433; $apiPort = 8001
    if ($values.ContainsKey('DB_PORT')) { $dbPort = [int]$values['DB_PORT'] }
    if ($values.ContainsKey('API_PORT')) { $apiPort = [int]$values['API_PORT'] }
    if (Test-Path -LiteralPath $EnvFile) {
        Show-Ok ".env exists (DB_PORT $dbPort, API_PORT $apiPort)"
        if ($apiPort -eq 8000) { Show-Warn 'API_PORT is 8000 in .env; prepare changes it to 8001 (README step 1).'; $apiPort = 8001 }
    } else {
        Show-Info '.env does not exist yet; prepare creates it (DB_PORT 5433, API_PORT 8001).'
    }

    Show-Info "Compose project for this folder: $Project"
    if (@(Get-ComposeContainers -Running).Count -gt 0) {
        Show-Ok "This folder's Compose services are running (ports $dbPort and $apiPort are theirs)."
    } else {
        foreach ($port in @($dbPort, $apiPort)) {
            if (Test-Listening $port) { Show-Problem "Port $port is in use by another program. Stop it, or change DB_PORT / API_PORT in .env (README troubleshooting)." }
            elseif (-not (Test-PortOpenable $port)) { Show-Problem "Port $port cannot be opened. $ReservedHint Or change DB_PORT / API_PORT in .env." }
            else { Show-Ok "Port $port is free" }
        }
    }
    if (@(@('serve', 'driver') | Where-Object { Get-Window $_ }).Count -gt 0) { Show-Ok "Port 8000 is used by this script's demo API window" }
    elseif (Test-Listening 8000) { Show-Problem 'Port 8000 (demo API) is in use by another program; the frontend proxy needs it. Stop that program first.' }
    elseif (-not (Test-PortOpenable 8000)) { Show-Problem "Port 8000 (demo API, needed by the frontend proxy) cannot be opened. $ReservedHint" }
    else { Show-Ok 'Port 8000 is free' }
    if (Get-Window 'web') {
        Show-Ok "Port $(Get-WebPort) is used by this script's web window"
    } else {
        $webPort = Select-WebPort
        if ($webPort -eq 5173) { Show-Ok 'Port 5173 is free' }
        elseif ($webPort -gt 0) { Show-Warn "Port 5173 cannot be opened (in use, or reserved by Windows); start will open the web frontend on port $webPort." }
        else { Show-Problem 'No port from 5173 to 5399 can be opened for the web frontend.' }
    }

    if (Test-VolumeExists) {
        if (Test-Path -LiteralPath $EnvFile) { Show-Ok "Database volume $Volume exists (this folder's data)" }
        else { Show-Problem "Volume $Volume exists but .env does not, so its password is unknown. Run: tools\demo\demo.ps1 stop -RemoveData" }
    }
}

function Assert-Prerequisites {
    Test-Prerequisites
    if ($script:Problems -gt 0) { Write-Host ''; Stop-Script "$($script:Problems) prerequisite problem(s) above; nothing was changed." }
}

function Assert-Prepared {
    if (-not (Test-Path -LiteralPath $Py) -or -not (Test-Path -LiteralPath $EnvFile) -or
        -not (Test-Path -LiteralPath (Join-Path $Web 'node_modules'))) {
        Stop-Script 'Not prepared yet. Run: tools\demo\demo.ps1 prepare'
    }
    $values = Read-DotEnv
    $apiPort = [int]$values['API_PORT']
    if (-not (Wait-Http "http://127.0.0.1:$apiPort/health/ready" '"ready"' 5)) {
        Stop-Script "The Compose database or API on port $apiPort is not ready. Run: tools\demo\demo.ps1 prepare"
    }
}

# -- actions --------------------------------------------------------------------

function Invoke-Prepare {
    Assert-Prerequisites

    Show-Step 'Step 1: Python environment and .env'
    if (-not (Test-Path -LiteralPath $Py)) {
        $base = Find-BasePython
        $prefix = $base.Prefix
        Invoke-Checked 'Creating .venv' { & $base.Exe @prefix -m venv (Join-Path $Root '.venv') }
        Show-Ok '.venv created'
    }
    $marker = Join-Path $Root '.venv\returnops-demo-install.txt'
    $wanted = Get-FileDigest @((Join-Path $Root 'requirements-dev.lock'), (Join-Path $Root 'pyproject.toml'))
    if ((Test-Path -LiteralPath $marker) -and ([System.IO.File]::ReadAllText($marker) -eq $wanted)) {
        Show-Ok 'Locked dependencies already installed'
    } else {
        Invoke-Checked 'pip install --require-hashes' { & $Py -m pip install --require-hashes -r requirements-dev.lock }
        Invoke-Checked 'pip install -e .' { & $Py -m pip install --no-deps --no-build-isolation -e . }
        [System.IO.File]::WriteAllText($marker, $wanted)
        Show-Ok 'Locked dependencies installed'
    }
    Invoke-Checked 'pip check' { & $Py -m pip check }
    if (-not (Test-Path -LiteralPath $EnvFile)) {
        Invoke-Checked 'local.py init' { & $Py -B tools/environment/local.py init }
    }
    $text = [System.IO.File]::ReadAllText($EnvFile)
    if ($text -match '(?m)^API_PORT=8000\r?$') {
        [System.IO.File]::WriteAllText($EnvFile, ($text -replace '(?m)^API_PORT=8000(\r?)$', 'API_PORT=8001$1'))
        Show-Ok 'API_PORT changed from 8000 to 8001 in .env (README step 1)'
    }
    $values = Read-DotEnv
    Show-Ok ".env ready (DB_PORT $($values['DB_PORT']), API_PORT $($values['API_PORT'])); no secret displayed"

    Show-Step "Step 2: database, migration and health-only API (Compose project $Project)"
    Invoke-Checked 'docker compose config' { docker compose -p $Project config --quiet }
    Invoke-Checked 'docker compose up' { docker compose -p $Project up --build -d --wait --wait-timeout 180 }
    Invoke-Checked 'docker compose ps' { docker compose -p $Project ps -a --format 'table {{.Service}}\t{{.State}}\t{{.Status}}' }
    $apiPort = $values['API_PORT']
    foreach ($check in @(@('live', '"alive"'), @('ready', '"ready"'))) {
        $name, $expect = $check
        if (Wait-Http "http://127.0.0.1:$apiPort/health/$name" $expect 30) { Show-Ok "/health/$name on port $apiPort answers $expect" }
        else { Stop-Script "/health/$name on port $apiPort did not answer $expect; see docker compose -p $Project logs" }
    }

    Show-Step 'Step 4 (install only): web frontend dependencies'
    $webMarker = Join-Path $Web 'node_modules\.returnops-demo-install.txt'
    $webWanted = Get-FileDigest @((Join-Path $Web 'package-lock.json'))
    if ((Test-Path -LiteralPath $webMarker) -and ([System.IO.File]::ReadAllText($webMarker) -eq $webWanted)) {
        Show-Ok 'npm ci already done for this package-lock.json'
    } else {
        Push-Location -LiteralPath $Web
        try { Invoke-Checked 'npm ci' { npm.cmd ci --no-audit --no-fund } } finally { Pop-Location }
        [System.IO.File]::WriteAllText($webMarker, $webWanted)
        Show-Ok 'npm ci done'
    }

    Show-Step 'Prepared'
    if ($Action -ne 'fresh') {
        Show-Info 'About five minutes before the demonstration (sessions last 899 s), run:'
        Show-Info '  powershell -NoProfile -ExecutionPolicy Bypass -File tools\demo\demo.ps1 start'
    }
}

function Invoke-Start {
    Assert-Prepared
    if (Get-Window 'driver') { Stop-Script 'The S5 driver window holds port 8000. Run stop first, then start.' }

    Show-Step 'Step 3: demo identities and demo API (port 8000)'
    if (Get-Window 'serve') {
        Show-Ok 'The demo API window is already running'
    } else {
        if (Test-Listening 8000) { Stop-Script 'Port 8000 is in use by a program this script did not start; stop it first.' }
        if (Test-Path -LiteralPath (Join-Path $Shop 'auth.json')) {
            if (-not (Test-Provisioned 'demo-shop' $Shop)) {
                Stop-Script 'tmp\demo-shop holds identities whose provision did not finish, so the server would refuse their tokens. Run stop -RemoveData, then prepare and start.'
            }
            Show-Warn 'tmp\demo-shop exists, so its identities are reused (the database refuses to register them twice).'
        } elseif (Test-Path -LiteralPath $Shop) {
            Stop-Script 'tmp\demo-shop exists without auth.json (an interrupted provision). Run stop -RemoveData, then prepare and start.'
        } else {
            New-Item -ItemType Directory -Force -Path $Tmp | Out-Null
            Invoke-Checked 'demo.py provision (demo-shop)' {
                & $Py -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir $Shop `
                    --store synthetic_au_store --customer-one synthetic_customer_a --customer-two synthetic_customer_b `
                    --founder founder --order-investigation --fixed-proposal --founder-manual
            }
            Save-Time 'demo-shop'
        }
        $serve = '& ' + (Format-Literal $Py) + ' -B tools/environment/local.py run python -m returnops_api.demo serve --auth-file ' +
            (Format-Literal (Join-Path $Shop 'auth.json')) + ' --port 8000 --fixed-proposal --founder-decisions --accounts'
        if ($ModelShowcase) { $serve += ' --model-showcase'; Show-Info 'With --model-showcase; the RETURNOPS_MODEL_* variables pass on unread.' }
        $window = Start-Window 'serve' 'ReturnOps demo API (port 8000) - Ctrl+C stops it' $serve
        $state = Wait-WindowReady $window 'http://127.0.0.1:8000/health/ready' '"ready"' 60
        if ($state -eq 'ended') {
            $hint = ''
            if ($ModelShowcase) { $hint = ' With -ModelShowcase, check that the RETURNOPS_MODEL_* variables are set in this window.' }
            Stop-Script "The demo API stopped right after starting; its window shows the reason.$hint"
        }
        if ($state -ne 'ready') { Stop-Script 'The demo API did not become ready within 60 s; read its window.' }
        Show-Ok 'Demo API ready on http://127.0.0.1:8000 (its window shows warnings and errors)'
    }

    Show-Step 'Step 4: web frontend'
    if (Get-Window 'web') {
        $webPort = Get-WebPort
        Show-Ok "The web window is already running (port $webPort)"
    } else {
        $webPort = Select-WebPort
        if ($webPort -eq 0) { Stop-Script 'No port from 5173 to 5399 can be opened for the web frontend.' }
        if ($webPort -ne 5173) { Show-Warn "Port 5173 cannot be opened (in use, or reserved by Windows); the web frontend uses port $webPort instead." }
        $webBody = 'Set-Location -LiteralPath ' + (Format-Literal $Web) + "`n& npm.cmd run dev -- --port $webPort --strictPort"
        $window = Start-Window 'web' "ReturnOps web (port $webPort)" $webBody
        [System.IO.File]::WriteAllText((Join-Path $StateDir 'web.port'), "$webPort")
        if ((Wait-WindowReady $window "http://localhost:$webPort/" '<' 60) -ne 'ready') { Stop-Script 'The web frontend did not start; read its window.' }
    }
    $webUrl = "http://localhost:$webPort"
    if (Wait-Http "$webUrl/health/ready" '"ready"' 15) { Show-Ok "$webUrl answers, and its proxy reaches the demo API" }
    else { Stop-Script "$webUrl does not reach the demo API through its proxy." }

    $since = Get-SavedTime 'demo-shop'
    Show-Step 'Sign in (manual, README step 4)'
    Show-Info "Open $webUrl in two browser profiles: sign in with the username and its password (the account decides the page); a new customer can use Create account."
    Show-Info 'Copy a password to the clipboard without showing it (customer synthetic_customer_a, then Founder founder):'
    Show-Info '  (Get-Content -Raw tmp\demo-shop\passwords.json | ConvertFrom-Json).synthetic_customer_a | Set-Clipboard'
    Show-Info '  (Get-Content -Raw tmp\demo-shop\passwords.json | ConvertFrom-Json).founder | Set-Clipboard'
    Show-Info 'Each sign-in starts a new 15-minute session, so signing in again renews it.'
    if ($since) {
        $until = $since.AddSeconds($SessionSeconds)
        if ($until -gt (Get-Date)) { Show-Info "The access keys in sessions.json (the fallback) were provisioned at $(Format-Time $since) and expire at $(Format-Time $until)." }
        else { Show-Info "The access keys in sessions.json (the fallback) expired at $(Format-Time $until); passwords still work." }
    }
    Show-Info 'S5 later: tools\demo\demo.ps1 s5    After the demonstration: tools\demo\demo.ps1 stop -RemoveData (or tools\demo\stop-demo.cmd)'
}

# Docker Desktop's two default install folders: for all users and for one user.
function Start-DockerDesktop {
    Show-Step 'Docker Desktop'
    $engine = Test-DockerEngine
    if ($engine) { Show-Ok "Docker engine $engine answers"; return }
    $exe = @(
        (Join-Path $env:ProgramFiles 'Docker\Docker\Docker Desktop.exe'),
        (Join-Path $env:LOCALAPPDATA 'Programs\DockerDesktop\Docker Desktop.exe')
    ) | Where-Object { Test-Path -LiteralPath $_ } | Select-Object -First 1
    if (-not $exe) { Stop-Script 'Docker does not answer and Docker Desktop was not found in its default folders; start it, wait until it reports running, then run this again.' }
    Start-Process -FilePath $exe
    Show-Info 'Docker Desktop opened; waiting up to 3 minutes for its engine.'
    $deadline = (Get-Date).AddMinutes(3)
    while ((Get-Date) -lt $deadline) {
        Start-Sleep -Seconds 3
        $engine = Test-DockerEngine
        if ($engine) { Show-Ok "Docker engine $engine answers"; return }
    }
    Stop-Script 'Docker Desktop did not report running within 3 minutes; look at its window (if it reports an unexpected error, choose Quit, never Reset to factory defaults), then run this again.'
}

# stop -RemoveData, prepare and start in one go; Stop-Script ends it at the first failure.
function Invoke-Fresh {
    Start-DockerDesktop
    $script:RemoveData = $true
    Invoke-Stop
    Invoke-Prepare
    Invoke-Start
}

function Invoke-S5 {
    Assert-Prepared
    if (Get-Window 'driver') { Stop-Script 'The S5 driver window is already running. Run stop first for another run.' }

    Show-Step 'Step 5: stop the step 3 demo API'
    if (Get-Window 'serve') { Close-Window 'serve' 'demo API' -CtrlC -Seconds 30 }
    if (-not (Wait-PortFree 8000 15)) { Stop-Script 'Port 8000 is still in use by a program this script did not start; stop it first.' }
    Show-Ok 'Port 8000 is free'

    Show-Step 'Step 5: S5 identities and the R.02 driver (demo mode)'
    if (Test-Path -LiteralPath (Join-Path $Cups 'auth.json')) {
        if (-not (Test-Provisioned 'demo-cups' $Cups)) {
            Stop-Script 'tmp\demo-cups holds identities whose provision did not finish, so the server would refuse their tokens. Run stop -RemoveData, then prepare and start.'
        }
        Show-Warn 'tmp\demo-cups exists, so its identities are reused; the driver refuses if the cups store already has a case.'
    } elseif (Test-Path -LiteralPath $Cups) {
        Stop-Script 'tmp\demo-cups exists without auth.json (an interrupted provision). Run stop -RemoveData, then prepare and start.'
    } else {
        Invoke-Checked 'demo.py provision (demo-cups)' {
            & $Py -B tools/environment/local.py run python -m returnops_api.demo provision --private-dir $Cups `
                --store demo_cups_store --customer-one demo_cups_customer_one --customer-two demo_cups_customer_two `
                --founder demo_cups_founder
        }
        Save-Time 'demo-cups'
    }
    $output = Join-Path $Tmp ('r02-demo-run-' + (Get-Date).ToString('yyyyMMdd-HHmmss'))
    $driver = '& ' + (Format-Literal $Py) + ' -B tools/r02/driver.py --output ' + (Format-Literal $output) +
        ' --identities ' + (Format-Literal $Cups) + ' --api-port 8000 --keep-api --allow-existing-data'
    # README step 5: DATABASE_URL is set directly for the driver, never through local.py run.
    # It exists only in this process and the driver window, and is not printed.
    $values = Read-DotEnv
    $env:DATABASE_URL = 'postgresql+psycopg://' + $values['POSTGRES_USER'] + ':' + $values['POSTGRES_PASSWORD'] +
        '@127.0.0.1:' + $values['DB_PORT'] + '/' + $values['POSTGRES_DB']
    try { $window = Start-Window 'driver' 'ReturnOps S5 driver (keeps the API on port 8000) - Ctrl+C stops it' $driver }
    finally { Remove-Item Env:DATABASE_URL -ErrorAction SilentlyContinue }

    Show-Info "Driver started; waiting up to 10 minutes for its receipt in tmp\$(Split-Path -Leaf $output)."
    $receipt = Join-Path $output 'run-receipt.json'
    $begun = Get-Date
    $deadline = $begun.AddMinutes(10)
    $data = $null
    $seen = $false
    while ((Get-Date) -lt $deadline -and -not $data) {
        if (Test-Path -LiteralPath $receipt) {
            try { $data = [System.IO.File]::ReadAllText($receipt) | ConvertFrom-Json } catch { $data = $null }
        }
        if (-not $data) {
            # The window needs a moment before its driver process appears.
            if (@(Get-WindowCommands $window).Count -gt 0) { $seen = $true }
            elseif ($seen -or ((Get-Date) - $begun).TotalSeconds -gt 30) { break }
            Start-Sleep -Seconds 2
        }
    }
    if (-not $data) { Stop-Script 'The driver stopped or wrote no receipt; read the driver window.' }
    if ($data.result -ne 'PASSED') {
        $stop = ''
        if ($data.PSObject.Properties['stop'] -and $data.stop) { $stop = " ($($data.stop.code))" }
        Stop-Script "Driver result $($data.result)$stop; read the driver window and tools/r02/README.md."
    }
    Show-Ok "Driver result PASSED; case $($data.case_id)"
    if (Wait-Http 'http://127.0.0.1:8000/health/ready' '"ready"' 30) { Show-Ok 'The driver keeps its API on port 8000' }
    else { Show-Warn 'Port 8000 does not answer ready; read the driver window.' }

    Show-Step 'Show the case (manual, README step 5)'
    Show-Info 'The driver API has no password sign-in: Sign out, Use an access key instead, the demo_cups_founder key, then Case Queue & Review -> Inspect.'
    Show-Info '  (Get-Content -Raw tmp\demo-cups\sessions.json | ConvertFrom-Json).tokens.demo_cups_founder | Set-Clipboard'
}

# -- Railway --------------------------------------------------------------------
# The sessions file of the running Railway deployment is read through `railway ssh`
# into a variable and written to tmp\railway-shop; it is never shown. cmd passes the
# `--` to the Railway CLI unchanged, which Windows PowerShell 5.1 may not.
# Every Railway command names -Service: a folder can be linked to the database service
# (`railway add` links the service it adds), and `railway up` there would replace it.

function Assert-Railway {
    Show-Step 'Railway CLI'
    if (-not (Get-Command railway -ErrorAction SilentlyContinue)) { Stop-Script 'The Railway CLI is not installed: npm install -g @railway/cli, then railway login and railway link.' }
    if ((Invoke-Quiet { railway whoami }).Code -ne 0) { Stop-Script 'The Railway CLI is not signed in: run railway login.' }
    Show-Ok 'Railway CLI signed in'
}

# The sessions of the running deployment as text and data, or $null.
function Get-CloudSessions {
    $answer = Invoke-Quiet { cmd.exe /d /c "railway ssh --service $Service -- cat /app/private/demo-shop/sessions.json" }
    if ($answer.Code -ne 0 -or -not $answer.Output) { return $null }
    try { $data = $answer.Output | ConvertFrom-Json } catch { return $null }
    if (-not ($data.PSObject.Properties['tokens'] -and $data.PSObject.Properties['sessions'])) { return $null }
    return [pscustomobject]@{ Text = $answer.Output; Data = $data; Issued = [long]$data.sessions[0].issued_at }
}

# Waits for sessions issued after $Before (the issue time seen before the deploy, or 0),
# so the server's clock is compared only with itself.
function Wait-CloudSessions([long]$Before, [int]$Minutes) {
    Show-Info "Waiting up to $Minutes minutes for the new deployment's sessions (railway ssh)."
    $deadline = (Get-Date).AddMinutes($Minutes)
    while ((Get-Date) -lt $deadline) {
        $found = Get-CloudSessions
        if ($found -and $found.Issued -gt $Before) { return $found }
        Start-Sleep -Seconds 10
    }
    Stop-Script "No new sessions within $Minutes minutes. Look at the deployment logs on railway.com, and check that this machine's SSH key is registered (railway ssh keys list; README, Railway deployment)."
}

# The public address of the app service from `railway status --json`, or $null when
# there is none or more than one.
function Get-CloudAddress {
    $answer = Invoke-Quiet { railway status --json }
    if ($answer.Code -ne 0 -or -not $answer.Output) { return $null }
    try { $status = $answer.Output | ConvertFrom-Json } catch { return $null }
    $found = @()
    try {
        foreach ($environment in @($status.environments.edges)) {
            foreach ($instance in @($environment.node.serviceInstances.edges)) {
                if ($instance.node.serviceName -ne $Service) { continue }
                foreach ($domain in @($instance.node.domains.customDomains) + @($instance.node.domains.serviceDomains)) {
                    if ($domain -and $domain.domain) { $found += [string]$domain.domain }
                }
            }
        }
    } catch { return $null }
    $found = @($found | Select-Object -Unique)
    if ($found.Count -ne 1) { return $null }
    return 'https://' + $found[0]
}

# The copied sessions are new only once the public address serves the deployment that
# issued them: until Railway switches traffic, the old deployment answers 401.
function Wait-CloudSignIn([string]$Address, $Found, [int]$Seconds) {
    $token = [string]$Found.Data.tokens.synthetic_customer_a
    $deadline = (Get-Date).AddSeconds($Seconds)
    while ((Get-Date) -lt $deadline) {
        $answer = Get-Http "$Address/v1/session" $token
        if ($answer -and $answer.Status -eq 200) { return $true }
        Start-Sleep -Seconds 5
    }
    return $false
}

function Save-CloudSessions($Found) {
    if (Test-Path -LiteralPath $CloudShop) { Remove-Item -LiteralPath $CloudShop -Recurse -Force }
    New-Item -ItemType Directory -Path $CloudShop | Out-Null
    [System.IO.File]::WriteAllText((Join-Path $CloudShop 'sessions.json'), $Found.Text + "`n")
    # The passwords of the same deployment (31 October 2026), read the same way and never shown.
    $passwords = Invoke-Quiet { cmd.exe /d /c "railway ssh --service $Service -- cat /app/private/demo-shop/passwords.json" }
    $passwordsValid = $false
    if ($passwords.Code -eq 0 -and $passwords.Output) { try { $null = $passwords.Output | ConvertFrom-Json; $passwordsValid = $true } catch { } }
    if ($passwordsValid) { [System.IO.File]::WriteAllText((Join-Path $CloudShop 'passwords.json'), $passwords.Output + "`n") }
    else { Show-Warn 'The passwords could not be copied; sign in with the access keys instead (Use an access key instead).' }
    $until = [DateTimeOffset]::FromUnixTimeSeconds([long]$Found.Data.sessions[0].expires_at).LocalDateTime
    if ($until -le (Get-Date)) { Show-Warn "Sessions copied to tmp\railway-shop (not shown), but they expired at $(Format-Time $until); run cloud-fresh for new ones." }
    else { Show-Ok "Sessions copied to tmp\railway-shop (not shown); they expire at $(Format-Time $until)." }
    $address = $Url
    if (-not $address) { $address = Get-CloudAddress }
    if ($address) {
        $address = $address.TrimEnd('/')
        if (-not (Wait-Http "$address/health/ready" '"ready"' 30)) { Show-Warn "$address does not answer ready; check the address and the deployment on railway.com." }
        elseif ($until -le (Get-Date)) { Show-Ok "$address answers ready" }
        elseif (Wait-CloudSignIn $address $Found 180) { Show-Ok "$address answers ready and accepts the copied sessions" }
        else { Show-Warn "$address does not accept the copied sessions yet (the previous deployment may still be serving); wait a minute and run cloud-tokens." }
    } else {
        Show-Warn 'The public address is unknown (pass -Url), so it was not checked that the deployment answers and accepts these sessions.'
        $address = 'the Railway address of the service (railway.com, service, Settings, Networking)'
    }
    Show-Step 'Sign in (manual, README step 4)'
    Show-Info "Open $address in two browser profiles: sign in with the username and its password (the account decides the page); a new customer can use Create account."
    Show-Info 'Copy a password to the clipboard without showing it (customer synthetic_customer_a, then Founder founder):'
    Show-Info '  (Get-Content -Raw tmp\railway-shop\passwords.json | ConvertFrom-Json).synthetic_customer_a | Set-Clipboard'
    Show-Info '  (Get-Content -Raw tmp\railway-shop\passwords.json | ConvertFrom-Json).founder | Set-Clipboard'
    Show-Info 'Each sign-in starts a new 15-minute session. Fallback: the access keys in tmp\railway-shop\sessions.json.'
    Show-Info 'New sessions: tools\demo\demo.ps1 cloud-fresh. After the demonstration: stop the Railway service and run stop -RemoveData here.'
}

function Invoke-Cloud {
    Assert-Railway
    $before = Get-CloudSessions
    # Without an answer from the running deployment, sessions issued more than a minute
    # before this deploy are old ones, not the new deployment's (local and server clocks).
    $since = [DateTimeOffset]::UtcNow.ToUnixTimeSeconds() - 60; if ($before) { $since = $before.Issued }
    Show-Step "Deploying this folder to the Railway service $Service (railway up; $Root)"
    Invoke-Checked 'railway up' { railway up --ci --service $Service }
    Save-CloudSessions (Wait-CloudSessions $since 10)
}

function Invoke-CloudFresh {
    Assert-Railway
    $before = Get-CloudSessions
    if (-not $before) { Stop-Script 'railway ssh returned no sessions from the running service; run cloud first, or cloud-tokens to see the reason.' }
    # A redeploy keeps the data since 31 October 2026, so a fresh demonstration is asked for first.
    Show-Step "Clearing the kept data of the Railway service $Service (railway ssh), so the redeploy starts fresh"
    $cleared = Invoke-Quiet { cmd.exe /d /c "railway ssh --service $Service -- python /app/start.py forget-data" }
    if ($cleared.Code -ne 0) { Stop-Script 'The kept data could not be cleared (railway ssh); nothing was redeployed. Check that the service is running, then run cloud-fresh again.' }
    Show-Ok 'Kept data cleared; the next start resets the demonstration'
    Show-Step "Redeploying the Railway service $Service for a fresh demonstration (railway redeploy)"
    Invoke-Checked 'railway redeploy' { railway redeploy --yes --service $Service }
    Save-CloudSessions (Wait-CloudSessions $before.Issued 5)
}

function Invoke-CloudTokens {
    Assert-Railway
    $found = Get-CloudSessions
    if (-not $found) { Stop-Script "railway ssh returned no sessions from the service $Service. Check that this machine's SSH key is registered (railway ssh keys list; README, Railway deployment), that -Service names the app service, and that it is running." }
    Save-CloudSessions $found
}

function Invoke-Stop {
    Show-Step 'Stopping the windows this script started'
    $webPort = Get-WebPort
    Close-Window 'driver' 'S5 driver' -CtrlC -Seconds 60
    Close-Window 'serve' 'demo API' -CtrlC -Seconds 30
    Close-Window 'web' 'web frontend'
    foreach ($port in @(8000, $webPort)) {
        if (Test-Listening $port) { Show-Warn "Port $port is still in use (a program this script did not start)." }
    }

    Show-Step "Compose project $Project"
    $containers = @(Get-ComposeContainers)
    if ($RemoveData) {
        # Without Docker the lookups below come back empty, and the volume would be reported removed.
        if (-not (Test-DockerEngine)) { Stop-Script 'Docker is not answering, so the containers and the database volume could not be removed. Start Docker Desktop and run stop -RemoveData again.' }
        if (Test-Path -LiteralPath $EnvFile) {
            Invoke-Checked 'docker compose down -v' { docker compose -p $Project down -v --remove-orphans }
        } else {
            if ($containers.Count -gt 0) { Invoke-Checked 'docker rm' { docker rm -f @containers } }
            if (Test-VolumeExists) { Invoke-Checked 'docker volume rm' { docker volume rm $Volume } }
        }
        Show-Ok 'Containers and the database volume removed'
        foreach ($dir in @($Shop, $Cups, $CloudShop, $StateDir)) {
            if (Test-Path -LiteralPath $dir) { Remove-Item -LiteralPath $dir -Recurse -Force; Show-Ok "Deleted tmp\$(Split-Path -Leaf $dir)" }
        }
        Show-Info 'Kept: .env, .venv, apps\web\node_modules and the driver receipts in tmp\r02-demo-run-*.'
        Show-Info 'In both browser profiles, use Sign out.'
    } elseif ($containers.Count -gt 0) {
        Invoke-Checked 'docker compose stop' { docker compose -p $Project stop }
        Show-Ok 'Compose services stopped; the database is kept (prepare starts them again).'
        Show-Info 'After the demonstration: tools\demo\demo.ps1 stop -RemoveData'
    } else {
        Show-Ok 'No Compose containers for this folder'
    }
}

switch ($Action) {
    'check' {
        Test-Prerequisites
        Write-Host ''
        if ($script:Problems -gt 0) { Write-Host "$($script:Problems) problem(s) found." -ForegroundColor Red; exit 1 }
        Write-Host 'No problem found.' -ForegroundColor Green
    }
    'prepare' { Invoke-Prepare }
    'start' { Invoke-Start }
    'fresh' { Invoke-Fresh }
    's5' { Invoke-S5 }
    'stop' { Invoke-Stop }
    'cloud' { Invoke-Cloud }
    'cloud-fresh' { Invoke-CloudFresh }
    'cloud-tokens' { Invoke-CloudTokens }
}
exit 0

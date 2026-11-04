<#
.SYNOPSIS
    Launch all Amidst demo processes on Windows PowerShell.
    Segment A (rec), Segment B (live), Segment C (events), prints workbench URL.
.DESCRIPTION
    Native Windows PowerShell implementation corresponding to start_all_demo.command.
    Pre-flight checks:
    - Python (>=3.12) and Node.js (>=20)
    - Disk space (>= 1 GiB free to start UI)
    - Port availability (8766, 8765, 8780)
    - Asset directories and tracking scope verification
#>
[CmdletBinding()]
param(
    [string]$P1Bundle = "",
    [string]$CX7Root = "",
    [string]$StateParent = "",
    [string]$Python = "python",
    [string]$ManifestSha = "",
    [int]$PortRec = 8766,
    [int]$PortLive = 8765,
    [int]$PortCx = 8780,
    [switch]$NoOpen,
    [switch]$CheckOnly
)

$ErrorActionPreference = "Stop"
$ROOT = $PSScriptRoot
if (-not $ROOT) { $ROOT = (Get-Location).Path }

# Default folder name contains Chinese characters: "Amidst P1 最終測試"
$p1DefaultFolder = "Amidst P1 " + [char]0x6700 + [char]0x7d42 + [char]0x6e2c + [char]0x8a66

# Resolve default values and environment variables
if ([string]::IsNullOrWhiteSpace($P1Bundle)) {
    if ($env:P1_BUNDLE -and (Test-Path -LiteralPath $env:P1_BUNDLE)) {
        $P1Bundle = $env:P1_BUNDLE
    } elseif ($env:AMIDST_SAFE_PACKS -and (Test-Path -LiteralPath (Join-Path $env:AMIDST_SAFE_PACKS "p1-v4-stripped"))) {
        $P1Bundle = Join-Path $env:AMIDST_SAFE_PACKS "p1-v4-stripped"
    } elseif (Test-Path -LiteralPath (Join-Path $ROOT "p1-v4-stripped")) {
        $P1Bundle = Join-Path $ROOT "p1-v4-stripped"
    } elseif ($env:P1_BUNDLE) {
        $P1Bundle = $env:P1_BUNDLE
    } else {
        $P1Bundle = Join-Path (Join-Path $HOME "amidst-p1-clean-room-20261026") $p1DefaultFolder
    }
}
if ([string]::IsNullOrWhiteSpace($CX7Root)) {
    if ($env:CX7_ROOT -and (Test-Path -LiteralPath $env:CX7_ROOT)) {
        $CX7Root = $env:CX7_ROOT
    } elseif ($env:AMIDST_SAFE_PACKS -and (Test-Path -LiteralPath (Join-Path $env:AMIDST_SAFE_PACKS "cx7-d119"))) {
        $CX7Root = Join-Path $env:AMIDST_SAFE_PACKS "cx7-d119"
    } elseif (Test-Path -LiteralPath (Join-Path $ROOT "cx7-d119")) {
        $CX7Root = Join-Path $ROOT "cx7-d119"
    } elseif ($env:CX7_ROOT) {
        $CX7Root = $env:CX7_ROOT
    } else {
        $CX7Root = Join-Path $HOME "amidst-artifacts\r004-cx7-d115-20261102-01a199f8"
    }
}
if ([string]::IsNullOrWhiteSpace($StateParent)) {
    if ($env:STATE_PARENT) {
        $StateParent = $env:STATE_PARENT
    } else {
        $StateParent = Join-Path $HOME "amidst-demo-state"
    }
}
if ($env:PYTHON -and $Python -eq "python") {
    $Python = $env:PYTHON
}
if ($env:PORT_REC -and $PortRec -eq 8766) {
    $PortRec = [int]$env:PORT_REC
}
if ($env:PORT_LIVE -and $PortLive -eq 8765) {
    $PortLive = [int]$env:PORT_LIVE
}
if ($env:PORT_CX -and $PortCx -eq 8780) {
    $PortCx = [int]$env:PORT_CX
}
if ($env:NO_OPEN -eq "1") {
    $NoOpen = $true
}

$MANIFEST_SHA_V4 = "6e9a0a4c5494b0bffad24dea0315b903216fcf8108a0c675d749466f4cb1f1d7"
$MANIFEST_SHA_STRIPPED = "13ab3c559fd63dd6f5d44ac7f6dabe1192274b368bfd1307f3a3bbd6682e5805"
$VALID_MANIFEST_SHAS = @($MANIFEST_SHA_V4, $MANIFEST_SHA_STRIPPED)

if ([string]::IsNullOrWhiteSpace($ManifestSha) -and $env:MANIFEST_SHA) {
    $ManifestSha = $env:MANIFEST_SHA
}

$SCOPE_SHA = "e2ca308b13181346707660a1ae4edcd7b8cc594709a3e009c2db0a9fea3374b8"
$STAMP = Get-Date -Format "HHmmss"

function Write-Fatal([string]$message) {
    Write-Error "Error: $message"
    exit 1
}

function Test-PortInUse([int]$port) {
    try {
        $listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, $port)
        $listener.Start()
        $listener.Stop()
        return $false
    } catch {
        return $true
    }
}

function Get-FreeDiskGiB([string]$targetPath) {
    $probe = $targetPath
    while (-not (Test-Path $probe) -and (Split-Path $probe -Parent) -ne $probe) {
        $probe = Split-Path $probe -Parent
        if ([string]::IsNullOrWhiteSpace($probe)) { break }
    }
    if (-not $probe -or -not (Test-Path $probe)) {
        $probe = (Get-Location).Path
    }
    $rootPath = [System.IO.Path]::GetPathRoot((Resolve-Path $probe).Path)
    $drive = [System.IO.DriveInfo]::new($rootPath)
    return [Math]::Round($drive.AvailableFreeSpace / 1GB, 2)
}

# --- 1. Pre-flight checks ---
Write-Host "Running demo pre-flight checks..." -ForegroundColor Cyan

# Check Python
$pyCmd = Get-Command $Python -ErrorAction SilentlyContinue
if (-not $pyCmd) {
    Write-Fatal "Python executable not found: $Python (specify via -Python or env PYTHON)"
}
$pythonVersion = & $Python -c "import sys; print('.'.join(map(str, sys.version_info[:3]))); sys.exit(0 if sys.version_info >= (3,12) else 1)"
if ($LASTEXITCODE -ne 0) { Write-Fatal "Python 3.12 or newer is required (found: $pythonVersion)" }

# Check Node.js
$nodeCmd = Get-Command "node" -ErrorAction SilentlyContinue
if (-not $nodeCmd) {
    Write-Fatal "Node.js executable not found in PATH"
}
$nodeVersion = & node --version
if ($LASTEXITCODE -ne 0 -or $nodeVersion -notmatch '^v(\d+)\.' -or [int]$Matches[1] -lt 20) {
    Write-Fatal "Node.js 20 or newer is required"
}

# Check disk space (>= 1 GiB free to start UI)
$freeGiB = Get-FreeDiskGiB $StateParent
Write-Host "  Free disk space: $freeGiB GiB" -ForegroundColor DarkGray
if ($freeGiB -lt 1.0) {
    Write-Fatal "Available disk space is ${freeGiB} GiB, below 1 GiB threshold; will not start UI."
}

# Check port numbers and availability
$ports = @(
    @{ Name = "Segment A (Rec)"; Port = $PortRec },
    @{ Name = "Segment B (Live)"; Port = $PortLive },
    @{ Name = "Segment C (Events)"; Port = $PortCx }
)

if ($PortRec -eq $PortLive -or $PortRec -eq $PortCx -or $PortLive -eq $PortCx) {
    Write-Fatal "Service ports must be unique (REC: $PortRec, LIVE: $PortLive, CX: $PortCx)"
}

foreach ($item in $ports) {
    $p = $item.Port
    $n = $item.Name
    if ($p -lt 1024 -or $p -gt 65535) {
        Write-Fatal "Port for $n must be between 1024 and 65535: $p"
    }
    if (Test-PortInUse $p) {
        Write-Fatal "Port $p is already in use ($n). Terminate existing process or choose another port."
    }
}

$trackingScopePath = Join-Path $ROOT "configs\q1q5\p1_live_tracking_scope.json"
if (-not (Test-Path $trackingScopePath)) {
    Write-Fatal "Tracking scope file missing: $trackingScopePath"
}

# Check P1 and CX-7 assets
if (-not (Test-Path $P1Bundle)) {
    Write-Fatal "P1 bundle directory not found: $P1Bundle"
}
$manifestFile = Join-Path $P1Bundle "MANIFEST.json"
if (-not (Test-Path $manifestFile)) {
    Write-Fatal "P1 bundle missing MANIFEST.json: $manifestFile"
}
if (-not (Test-Path $CX7Root)) {
    Write-Fatal "CX-7 root directory not found: $CX7Root"
}
# Read only the declared safe directory paths. Full PNG validation remains in the
# event server; CheckOnly does not claim that validation or launch any service.
foreach ($rootDir in @($P1Bundle, $CX7Root)) {
    if (-not (Test-Path -LiteralPath $rootDir -PathType Container) -or
        ((Get-Item -LiteralPath $rootDir).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Write-Fatal "Asset root must be a regular directory without a reparse point"
    }
}
foreach ($pinnedFile in @($manifestFile, $trackingScopePath)) {
    if (-not (Test-Path -LiteralPath $pinnedFile -PathType Leaf) -or
        ((Get-Item -LiteralPath $pinnedFile).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
        Write-Fatal "Pinned manifest/scope must be a regular file without a reparse point"
    }
}
$actualManifestSha = (Get-FileHash -LiteralPath $manifestFile -Algorithm SHA256).Hash.ToLowerInvariant()
if (-not [string]::IsNullOrWhiteSpace($ManifestSha)) {
    if ($actualManifestSha -ne $ManifestSha.ToLowerInvariant()) {
        Write-Fatal "P1 manifest SHA-256 mismatch: $actualManifestSha (expected: $ManifestSha)"
    }
} else {
    if ($actualManifestSha -notin $VALID_MANIFEST_SHAS) {
        Write-Fatal "P1 manifest SHA-256 mismatch: $actualManifestSha (expected one of $($VALID_MANIFEST_SHAS -join ', '))"
    }
    $ManifestSha = $actualManifestSha
}
if ((Get-FileHash -LiteralPath $trackingScopePath -Algorithm SHA256).Hash.ToLowerInvariant() -ne $SCOPE_SHA) {
    Write-Fatal "Tracking scope SHA-256 mismatch"
}
Push-Location $ROOT
try {
    $runsJson = & node --input-type=module -e "import {RUNS} from './frontend/event-viewer/runs.mjs'; console.log(JSON.stringify(RUNS.map(r=>({key:r.key,cameras:r.cameras}))));"
    if ($LASTEXITCODE -ne 0) { Write-Fatal "Cannot load declared CX7 safe directory catalog" }
    foreach ($run in ($runsJson | ConvertFrom-Json)) {
        $safeDir = $CX7Root
        foreach ($part in @($run.key, "safe", "media")) {
            $safeDir = Join-Path $safeDir $part
            if (-not (Test-Path -LiteralPath $safeDir -PathType Container) -or
                ((Get-Item -LiteralPath $safeDir).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                Write-Fatal "Declared CX7 safe directory is missing or is a reparse point"
            }
        }
        foreach ($camera in $run.cameras) {
            $cameraDir = Join-Path $safeDir $camera
            if (-not (Test-Path -LiteralPath $cameraDir -PathType Container) -or
                ((Get-Item -LiteralPath $cameraDir).Attributes -band [IO.FileAttributes]::ReparsePoint)) {
                Write-Fatal "Declared CX7 safe camera directory is missing or is a reparse point"
            }
        }
    }
} finally { Pop-Location }

if ($CheckOnly) {
    Write-Host "Pre-flight checks passed successfully (directory and pin checks only; PNG validation and service launch not run)." -ForegroundColor Green
    exit 0
}

# --- 2. Setup state directories ---
New-Item -ItemType Directory -Path $StateParent -Force | Out-Null
$REC_STATE = Join-Path $StateParent "rec-$STAMP"
$LIVE_STATE = Join-Path $StateParent "live-$STAMP"
$LOG_DIR = Join-Path $StateParent "logs-$STAMP"
New-Item -ItemType Directory -Path $LOG_DIR -Force | Out-Null

$env:PYTHONDONTWRITEBYTECODE = "1"
$env:P1_BUNDLE = $P1Bundle

$procA = $null
$procB = $null
$procC = $null

try {
    Write-Host "Starting Segment A (rec) on port $PortRec, Segment B (live) on port $PortLive, Segment C (events) on port $PortCx..." -ForegroundColor Cyan

    $procA = Start-Process -FilePath $Python -ArgumentList @(
        "-S", "scripts/start_q1q5_p1.py",
        "--bundle", "`"$P1Bundle`"",
        "--manifest-sha256", $ManifestSha,
        "--state-root", "`"$REC_STATE`"",
        "--current-ui", "--no-open",
        "--port", $PortRec
    ) -WorkingDirectory $ROOT -RedirectStandardOutput (Join-Path $LOG_DIR "a-rec.log") -RedirectStandardError (Join-Path $LOG_DIR "a-rec-err.log") -PassThru

    $procB = Start-Process -FilePath $Python -ArgumentList @(
        "-S", "scripts/start_q1q5_p1.py",
        "--bundle", "`"$P1Bundle`"",
        "--manifest-sha256", $ManifestSha,
        "--state-root", "`"$LIVE_STATE`"",
        "--tracking-scope", "`"$trackingScopePath`"",
        "--tracking-scope-sha256", $SCOPE_SHA,
        "--current-ui", "--no-open",
        "--port", $PortLive
    ) -WorkingDirectory $ROOT -RedirectStandardOutput (Join-Path $LOG_DIR "b-live.log") -RedirectStandardError (Join-Path $LOG_DIR "b-live-err.log") -PassThru

    $procC = Start-Process -FilePath "node" -ArgumentList @(
        "frontend/event-viewer/server.mjs",
        "--root", "`"$CX7Root`"",
        "--port", $PortCx
    ) -WorkingDirectory $ROOT -RedirectStandardOutput (Join-Path $LOG_DIR "c-events.log") -RedirectStandardError (Join-Path $LOG_DIR "c-events-err.log") -PassThru

    # Wait for services to be ready
    Write-Host "Waiting for services to become ready (max 180s)..." -ForegroundColor DarkGray
    $deadline = (Get-Date).AddSeconds(180)
    $doneA = $false; $doneB = $false; $doneC = $false

    while (-not ($doneA -and $doneB -and $doneC)) {
        if ((Get-Date) -gt $deadline) {
            Write-Fatal "Service startup timed out (180s). Logs located at: $LOG_DIR"
        }
        if (-not $doneA) {
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$PortRec/workbench-v2/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($resp.StatusCode -eq 200) { $doneA = $true; Write-Host "  ✔ Segment A ready (port $PortRec)" -ForegroundColor Green }
            } catch {}
        }
        if (-not $doneB) {
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$PortLive/workbench-v2/" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($resp.StatusCode -eq 200) { $doneB = $true; Write-Host "  ✔ Segment B ready (port $PortLive)" -ForegroundColor Green }
            } catch {}
        }
        if (-not $doneC) {
            try {
                $resp = Invoke-WebRequest -Uri "http://127.0.0.1:$PortCx/api/runs" -UseBasicParsing -TimeoutSec 2 -ErrorAction SilentlyContinue
                if ($resp.StatusCode -eq 200) { $doneC = $true; Write-Host "  ✔ Segment C ready (port $PortCx)" -ForegroundColor Green }
            } catch {}
        }
        Start-Sleep -Seconds 1
    }

    $URL = ('http://127.0.0.1:{0}/workbench-v2/?ev=wall' + '&' + 'ev_live={1}' + '&' + 'ev_cx={2}') -f $PortRec, $PortLive, $PortCx
    Write-Host ""
    Write-Host "All services ready. Workbench URL: $URL" -ForegroundColor Cyan
    Write-Host "Log directory: $LOG_DIR" -ForegroundColor DarkGray
    Write-Host "Press Ctrl-C to terminate all services." -ForegroundColor Yellow

    if (-not $NoOpen) {
        Start-Process $URL
    }

    while ($true) {
        if ($procA.HasExited -or $procB.HasExited -or $procC.HasExited) {
            Write-Warning "A child process terminated unexpectedly. Check logs at: $LOG_DIR"
            break
        }
        Start-Sleep -Seconds 2
    }
} finally {
    Write-Host "Shutting down all service processes..." -ForegroundColor Yellow
    foreach ($p in @($procA, $procB, $procC)) {
        if ($p -and -not $p.HasExited) {
            try { Stop-Process -Id $p.Id -Force -ErrorAction SilentlyContinue } catch {}
        }
    }
    Write-Host "Cleanup completed." -ForegroundColor Green
}

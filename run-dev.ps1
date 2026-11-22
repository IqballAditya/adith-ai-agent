<#
.SYNOPSIS
    Adith AI Studio - Unified Local Development Bootstrapper.

.DESCRIPTION
    Bootstraps the complete 4-layer AI development environment on Windows:
      1. Verifies Python 3.10+, Go 1.22+, and Node.js environments.
      2. Validates and compiles React Monaco Web frontend if needed.
      3. Launches the Python Agent service (FastAPI reasoning loop on :5050).
      4. Health-checks the Python Agent until ready.
      5. Launches the Go Gateway (reverse proxy, SSE bridge, ConPTY terminal on :8090).
      6. Health-checks the Go Gateway until ready.
      7. Launches the default web browser to http://127.0.0.1:8090.
      8. Monitors both processes and performs graceful tree cleanup on exit/Ctrl+C.

.PARAMETER AgentPort
    Port for the Python Agent service (default: 5050).

.PARAMETER GatewayPort
    Port for the Go Gateway service (default: 8090).

.PARAMETER WorkspaceRoot
    Root directory for workspace files and indexing (default: repository root).

.PARAMETER NoBrowser
    Do not launch the web browser automatically.

.PARAMETER SkipBuild
    Skip checking/building frontend web assets (web/dist).

.EXAMPLE
    .\run-dev.ps1
    .\run-dev.ps1 -NoBrowser
    .\run-dev.ps1 -AgentPort 5051 -GatewayPort 8091
#>

[CmdletBinding()]
param(
    [string]$AgentPort = "5050",
    [string]$GatewayPort = "8090",
    [string]$WorkspaceRoot = "",
    [switch]$NoBrowser,
    [switch]$SkipBuild
)

$ErrorActionPreference = "Stop"

# Determine repository root
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) {
    $ScriptDir = (Get-Location).Path
}
if (-not $WorkspaceRoot) {
    $WorkspaceRoot = $ScriptDir
}
$WorkspaceRoot = (Resolve-Path $WorkspaceRoot).Path

Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "         Adith AI Studio - Development Bootstrapper       " -ForegroundColor Cyan
Write-Host "==========================================================" -ForegroundColor Cyan
Write-Host "[dev] Workspace root: $WorkspaceRoot" -ForegroundColor Gray
Write-Host "[dev] Python Agent port: $AgentPort" -ForegroundColor Gray
Write-Host "[dev] Go Gateway port:   $GatewayPort" -ForegroundColor Gray

# -------------------------------------------------------------
# 1. Environment & Dependency Checks
# -------------------------------------------------------------
Write-Host "`n[1/5] Checking development prerequisites..." -ForegroundColor Yellow

# Check Python
$pythonCmd = Get-Command "python" -ErrorAction SilentlyContinue
if (-not $pythonCmd) {
    $pythonCmd = Get-Command "python3" -ErrorAction SilentlyContinue
}
if (-not $pythonCmd) {
    Write-Host "[ERROR] Python 3 was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Python 3.10+ from https://www.python.org/ or Microsoft Store." -ForegroundColor Red
    exit 1
}
$pyVersion = & $pythonCmd.Source --version 2>&1
Write-Host "  -> Python: $pyVersion ($($pythonCmd.Source))" -ForegroundColor Green

# Check Go
$goCmd = Get-Command "go" -ErrorAction SilentlyContinue
if (-not $goCmd) {
    Write-Host "[ERROR] Go compiler was not found in PATH." -ForegroundColor Red
    Write-Host "Please install Go 1.22+ from https://go.dev/dl/." -ForegroundColor Red
    exit 1
}
$goVersion = & $goCmd.Source version 2>&1
Write-Host "  -> Go:     $goVersion ($($goCmd.Source))" -ForegroundColor Green

# Check Node / npm (optional warning if missing)
$npmCmd = Get-Command "npm" -ErrorAction SilentlyContinue
if ($npmCmd) {
    $npmVersion = & $npmCmd.Source --version 2>&1
    Write-Host "  -> npm:    v$npmVersion ($($npmCmd.Source))" -ForegroundColor Green
} else {
    Write-Host "  -> npm:    Not found (Frontend building may be skipped if web/dist exists)" -ForegroundColor DarkYellow
}

# -------------------------------------------------------------
# 2. Build Web Frontend Assets if needed
# -------------------------------------------------------------
$distDir = Join-Path $WorkspaceRoot "web\dist"
$distIndex = Join-Path $distDir "index.html"

if (-not $SkipBuild) {
    if (-not (Test-Path $distIndex)) {
        Write-Host "`n[2/5] Frontend build assets not found in web/dist. Building..." -ForegroundColor Yellow
        if (-not $npmCmd) {
            Write-Host "[ERROR] web/dist is missing and npm is not installed. Cannot build frontend." -ForegroundColor Red
            exit 1
        }
        $webDir = Join-Path $WorkspaceRoot "web"
        Push-Location $webDir
        try {
            Write-Host "  -> Running 'npm run build'..." -ForegroundColor Gray
            & npm.cmd run build
            if ($LASTEXITCODE -ne 0) {
                Write-Host "[ERROR] Frontend build failed." -ForegroundColor Red
                exit 1
            }
            Write-Host "  -> Frontend build successful." -ForegroundColor Green
        } finally {
            Pop-Location
        }
    } else {
        Write-Host "`n[2/5] Frontend build assets found in web/dist (skipping build)." -ForegroundColor Green
    }
} else {
    Write-Host "`n[2/5] Skipping frontend build check (-SkipBuild specified)." -ForegroundColor Gray
}

# -------------------------------------------------------------
# Process Management & Cleanup Handlers
# -------------------------------------------------------------
$agentProc = $null
$gatewayProc = $null

function Stop-ProcessTree {
    param([int]$ProcessId)
    if ($ProcessId -le 0) { return }
    try {
        & taskkill.exe /PID $ProcessId /T /F 2>$null | Out-Null
    } catch {
        try {
            Stop-Process -Id $ProcessId -Force -ErrorAction SilentlyContinue
        } catch {}
    }
}

function Cleanup {
    Write-Host "`n`n[dev] Shutting down Adith AI Studio services..." -ForegroundColor Yellow
    if ($agentProc -and -not $agentProc.HasExited) {
        Write-Host "  -> Stopping Python Agent (PID $($agentProc.Id))..." -ForegroundColor DarkGray
        Stop-ProcessTree -ProcessId $agentProc.Id
    }
    if ($gatewayProc -and -not $gatewayProc.HasExited) {
        Write-Host "  -> Stopping Go Gateway (PID $($gatewayProc.Id))..." -ForegroundColor DarkGray
        Stop-ProcessTree -ProcessId $gatewayProc.Id
    }
    Write-Host "[dev] Cleanup complete. Goodbye!" -ForegroundColor Green
}

trap {
    Cleanup
    break
}

# -------------------------------------------------------------
# 3. Start Python Agent Service (:5050)
# -------------------------------------------------------------
try {
    Write-Host "`n[3/5] Starting Python Agent engine on port $AgentPort..." -ForegroundColor Yellow
    $agentArgs = "-m", "uvicorn", "agent.server:app", "--host", "127.0.0.1", "--port", "$AgentPort", "--reload"

    $agentStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $agentStartInfo.FileName = $pythonCmd.Source
    $agentStartInfo.Arguments = "$agentArgs"
    $agentStartInfo.WorkingDirectory = $WorkspaceRoot
    $agentStartInfo.UseShellExecute = $false
    $agentStartInfo.CreateNoWindow = $false

    $agentProc = [System.Diagnostics.Process]::Start($agentStartInfo)
    Write-Host "  -> Python Agent process spawned (PID $($agentProc.Id))." -ForegroundColor Gray

    # Poll Agent Health
    $agentUrl = "http://127.0.0.1:$AgentPort"
    $agentHealthy = $false
    Write-Host "  -> Waiting for Python Agent health check" -NoNewline -ForegroundColor Gray

    for ($i = 0; $i -lt 35; $i++) {
        Start-Sleep -Milliseconds 1000
        if ($agentProc.HasExited) {
            Write-Host "`n[ERROR] Python Agent process terminated unexpectedly (ExitCode: $($agentProc.ExitCode))." -ForegroundColor Red
            exit 1
        }
        try {
            $resp = Invoke-RestMethod -Uri "$agentUrl/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "ok") {
                $agentHealthy = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline -ForegroundColor DarkGray
        }
    }
    Write-Host ""

    if (-not $agentHealthy) {
        Write-Host "[ERROR] Python Agent failed to become healthy on $agentUrl within 35 seconds." -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> Python Agent is healthy and operational! ($agentUrl/health)" -ForegroundColor Green

    # -------------------------------------------------------------
    # 4. Start Go Gateway Service (:8090)
    # -------------------------------------------------------------
    Write-Host "`n[4/5] Starting Go Gateway on port $GatewayPort..." -ForegroundColor Yellow

    $gwArgs = "run cmd/gateway/main.go -port $GatewayPort -agent $agentUrl -workspace `"$WorkspaceRoot`""
    $gwStartInfo = New-Object System.Diagnostics.ProcessStartInfo
    $gwStartInfo.FileName = $goCmd.Source
    $gwStartInfo.Arguments = $gwArgs
    $gwStartInfo.WorkingDirectory = $WorkspaceRoot
    $gwStartInfo.UseShellExecute = $false
    $gwStartInfo.CreateNoWindow = $false

    $gatewayProc = [System.Diagnostics.Process]::Start($gwStartInfo)
    Write-Host "  -> Go Gateway process spawned (PID $($gatewayProc.Id))." -ForegroundColor Gray

    # Poll Gateway Health
    $gatewayUrl = "http://127.0.0.1:$GatewayPort"
    $gatewayHealthy = $false
    Write-Host "  -> Waiting for Go Gateway health check" -NoNewline -ForegroundColor Gray

    for ($i = 0; $i -lt 25; $i++) {
        Start-Sleep -Milliseconds 1000
        if ($gatewayProc.HasExited) {
            Write-Host "`n[ERROR] Go Gateway process terminated unexpectedly (ExitCode: $($gatewayProc.ExitCode))." -ForegroundColor Red
            exit 1
        }
        try {
            $resp = Invoke-RestMethod -Uri "$gatewayUrl/health" -Method Get -TimeoutSec 2 -ErrorAction Stop
            if ($resp.status -eq "ok") {
                $gatewayHealthy = $true
                break
            }
        } catch {
            Write-Host "." -NoNewline -ForegroundColor DarkGray
        }
    }
    Write-Host ""

    if (-not $gatewayHealthy) {
        Write-Host "[ERROR] Go Gateway failed to become healthy on $gatewayUrl within 25 seconds." -ForegroundColor Red
        exit 1
    }
    Write-Host "  -> Go Gateway is healthy and operational! ($gatewayUrl/health)" -ForegroundColor Green

    # -------------------------------------------------------------
    # 5. Launch Browser & Keep Alive
    # -------------------------------------------------------------
    Write-Host "`n[5/5] Launching user interface..." -ForegroundColor Yellow
    if (-not $NoBrowser) {
        Write-Host "  -> Opening web browser to $gatewayUrl" -ForegroundColor Cyan
        Start-Process $gatewayUrl
    } else {
        Write-Host "  -> Headless mode (-NoBrowser). Open $gatewayUrl manually." -ForegroundColor Gray
    }

    Write-Host "`n==========================================================" -ForegroundColor Green
    Write-Host "       Adith AI Studio is active and ready for work!      " -ForegroundColor Green
    Write-Host "==========================================================" -ForegroundColor Green
    Write-Host "  Web IDE & Gateway:  $gatewayUrl" -ForegroundColor White
    Write-Host "  Python Agent:       $agentUrl" -ForegroundColor White
    Write-Host "  Workspace Root:     $WorkspaceRoot" -ForegroundColor White
    Write-Host "`nPress Ctrl+C to terminate all services gracefully.`n" -ForegroundColor Yellow

    # Monitor child processes until user cancels or a process exits
    while (-not $agentProc.HasExited -and -not $gatewayProc.HasExited) {
        Start-Sleep -Milliseconds 500
    }

    if ($agentProc.HasExited) {
        Write-Host "`n[dev] Python Agent exited with code $($agentProc.ExitCode)." -ForegroundColor DarkYellow
    }
    if ($gatewayProc.HasExited) {
        Write-Host "`n[dev] Go Gateway exited with code $($gatewayProc.ExitCode)." -ForegroundColor DarkYellow
    }

} finally {
    Cleanup
}

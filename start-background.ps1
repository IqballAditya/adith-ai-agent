# start-background.ps1 - Menjalankan Adith AI Studio di background dan membuka browser
param([switch]$NoBrowser)

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

# 1. Jalankan Python Agent (:5050) jika belum aktif
$agentPort = 5050
$conn = Get-NetTCPConnection -LocalPort $agentPort -ErrorAction SilentlyContinue
if (-not $conn) {
    Start-Process -FilePath "python" -ArgumentList "-m uvicorn agent.server:app --host 127.0.0.1 --port $agentPort" -WorkingDirectory $ScriptDir -WindowStyle Hidden
}

# 2. Jalankan Go Gateway (:8090) jika belum aktif
$gatewayPort = 8090
$connGw = Get-NetTCPConnection -LocalPort $gatewayPort -ErrorAction SilentlyContinue
if (-not $connGw) {
    $gwExe = Join-Path $ScriptDir "bin\adith-gateway.exe"
    if (Test-Path $gwExe) {
        Start-Process -FilePath $gwExe -ArgumentList "-port $gatewayPort -agent http://127.0.0.1:$agentPort -workspace `"$ScriptDir`" -db `"$ScriptDir\adith.db`"" -WorkingDirectory $ScriptDir -WindowStyle Hidden
    } else {
        Start-Process -FilePath "go" -ArgumentList "run cmd/gateway/main.go -port $gatewayPort -agent http://127.0.0.1:$agentPort -workspace `"$ScriptDir`" -db `"$ScriptDir\adith.db`"" -WorkingDirectory $ScriptDir -WindowStyle Hidden
    }
}

# 3. Tunggu hingga gateway siap lalu buka browser otomatis jika tidak dinonaktifkan
$gwUrl = "http://127.0.0.1:$gatewayPort"
if (-not $NoBrowser) {
    for ($i = 0; $i -lt 15; $i++) {
        Start-Sleep -Milliseconds 500
        try {
            $resp = Invoke-RestMethod -Uri "$gwUrl/health" -Method Get -TimeoutSec 1 -ErrorAction Stop
            if ($resp.status -eq "ok") { break }
        } catch {}
    }
    Start-Process $gwUrl
}

Write-Host "ADITH AI STUDIO aktif di background: $gwUrl" -ForegroundColor Green

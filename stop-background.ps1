# stop-background.ps1 - Menghentikan layanan Adith AI Studio yang berjalan di background
Get-Process adith-gateway -ErrorAction SilentlyContinue | Stop-Process -Force -ErrorAction SilentlyContinue

$ports = 5050, 8090
foreach ($p in $ports) {
    $conns = Get-NetTCPConnection -LocalPort $p -ErrorAction SilentlyContinue
    foreach ($c in $conns) {
        if ($c.OwningProcess -gt 0) {
            Stop-Process -Id $c.OwningProcess -Force -ErrorAction SilentlyContinue
        }
    }
}

Write-Host "Layanan background ADITH AI STUDIO telah dihentikan." -ForegroundColor Yellow

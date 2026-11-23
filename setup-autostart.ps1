# setup-autostart.ps1 - Mengatur agar Adith AI Studio otomatis aktif setiap kali Windows menyala
param([switch]$Uninstall)

$startupFolder = [System.Environment]::GetFolderPath([System.Environment+SpecialFolder]::Startup)
if (-not $startupFolder -or -not (Test-Path $startupFolder)) {
    $startupFolder = Join-Path $env:APPDATA "Microsoft\Windows\Start Menu\Programs\Startup"
}
$shortcutPath = Join-Path $startupFolder "AdithAIStudioAutoStart.lnk"
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
if (-not $ScriptDir) { $ScriptDir = (Get-Location).Path }

if ($Uninstall) {
    if (Test-Path $shortcutPath) {
        Remove-Item -Path $shortcutPath -Force
        Write-Host "Auto-start berhasil dinonaktifkan. Shortcut dihapus dari Windows Startup." -ForegroundColor Yellow
    } else {
        Write-Host "Auto-start saat ini belum terpasang." -ForegroundColor Gray
    }
    exit 0
}

# Buat shortcut di folder Startup Windows yang menjalankan start-background.ps1 tanpa jendela terminal
$wscript = New-Object -ComObject WScript.Shell
$shortcut = $wscript.CreateShortcut($shortcutPath)
$shortcut.TargetPath = "powershell.exe"
$shortcut.Arguments = "-WindowStyle Hidden -ExecutionPolicy Bypass -File `"$ScriptDir\start-background.ps1`""
$shortcut.WorkingDirectory = $ScriptDir
$shortcut.Description = "Auto-start Adith AI Studio in the background"
$shortcut.Save()

Write-Host "==========================================================" -ForegroundColor Green
Write-Host "  ADITH AI STUDIO Auto-Start Berhasil Diaktifkan!         " -ForegroundColor Green
Write-Host "==========================================================" -ForegroundColor Green
Write-Host "Mulai sekarang, setiap kali laptop menyala atau kamu login," -ForegroundColor White
Write-Host "Adith AI Studio akan otomatis aktif di background tanpa jendela." -ForegroundColor White
Write-Host "Kamu bisa langsung membuka http://127.0.0.1:8090 di browser kapan pun!" -ForegroundColor Cyan

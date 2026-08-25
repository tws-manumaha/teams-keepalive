# ============================================================
#  Teams Keep-Alive — Create Desktop Shortcut
#  Right-click this file → "Run with PowerShell"
#  Creates a desktop shortcut with the app icon.
# ============================================================

$ErrorActionPreference = "Stop"

# Resolve the script's own directory (where teams_keepalive.py lives)
$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$TargetScript = Join-Path $ScriptDir "teams_keepalive.py"
$IconFile     = Join-Path $ScriptDir "teams_keepalive.ico"

if (-not (Test-Path $TargetScript)) {
    Write-Host "Error: teams_keepalive.py not found in $ScriptDir" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Find Python
$Python = $null
$Candidates = @(
    (Get-Command pythonw -ErrorAction SilentlyContinue),
    (Get-Command python -ErrorAction SilentlyContinue),
    (Get-Command pyw -ErrorAction SilentlyContinue),
    (Get-Command py -ErrorAction SilentlyContinue)
) | Where-Object { $_ -ne $null } | Select-Object -First 1

if ($Candidates) {
    $Python = $Candidates.Source
} else {
    Write-Host "Python not found! Please install Python from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Desktop path
$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Teams Keep-Alive.lnk"

# Create the shortcut
$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $Python
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ScriptDir
$Shortcut.IconLocation = $IconFile
$Shortcut.Description = "Keep your Microsoft Teams status Available"
$Shortcut.WindowStyle = 7  # Minimised — no console window
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "  Location: $ShortcutPath" -ForegroundColor Cyan
Write-Host ""
Read-Host "Press Enter to close"

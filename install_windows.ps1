# ============================================================
#  Teams Keep-Alive — Windows Installer
#  Right-click → "Run with PowerShell"
#  or:  powershell -ExecutionPolicy Bypass -File install_windows.ps1
# ============================================================

$ErrorActionPreference = "Stop"

$ScriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
Set-Location $ScriptDir

function Write-Step($msg) { Write-Host "`n▶ $msg" -ForegroundColor Cyan }
function Write-Ok($msg)   { Write-Host "  ✅ $msg" -ForegroundColor Green }
function Write-Warn($msg)  { Write-Host "  ⚠ $msg" -ForegroundColor Yellow }
function Write-Err($msg)   { Write-Host "  ❌ $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "========================================" -ForegroundColor Cyan
Write-Host "  Teams Keep-Alive — Windows Installer"    -ForegroundColor Cyan
Write-Host "========================================" -ForegroundColor Cyan

# --- 1. Check Python -------------------------------------------------------

Write-Step "Checking for Python..."

$Python = $null
$Pythonw = $null
foreach ($Exe in @("pythonw", "python", "pyw", "py")) {
    $Cmd = Get-Command $Exe -ErrorAction SilentlyContinue
    if ($Cmd) {
        if ($Exe -match "w$") { if (-not $Pythonw) { $Pythonw = $Cmd.Source } }
        else                  { if (-not $Python)  { $Python  = $Cmd.Source } }
    }
}
$RunExe = $null
if ($Pythonw) { $RunExe = $Pythonw } elseif ($Python) { $RunExe = $Python }
$PyForGen = $Python; if (-not $PyForGen) { $PyForGen = $RunExe }

if (-not $RunExe) {
    Write-Err "Python not found!"
    Write-Host "  Please install Python 3.8+ from https://www.python.org/downloads/" -ForegroundColor Yellow
    Read-Host "`nPress Enter to exit"
    exit 1
}
$Version = & $PyForGen --version 2>&1
Write-Ok "Found $Version at $RunExe"

# --- 2. Install dependencies ------------------------------------------------

Write-Step "Installing Python dependencies..."

$ReqFile = Join-Path $ScriptDir "requirements.txt"
if (Test-Path $ReqFile) {
    & $PyForGen -m pip install -r $ReqFile --quiet 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    Write-Ok "Dependencies installed"
} else {
    Write-Warn "requirements.txt not found, installing individually"
    & $PyForGen -m pip install pystray Pillow --quiet 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    Write-Ok "Core dependencies installed"
}

# --- 3. Generate icon -------------------------------------------------------

Write-Step "Generating desktop icon..."

$IconFile = Join-Path $ScriptDir "teams_keepalive.ico"
$GenScript = Join-Path $ScriptDir "generate_icon.py"
if (Test-Path $GenScript) {
    & $PyForGen $GenScript 2>&1 | ForEach-Object { Write-Host "  $_" -ForegroundColor DarkGray }
    if (Test-Path $IconFile) {
        $IconSize = (Get-Item $IconFile).Length
        Write-Ok "Icon created ($IconSize bytes)"
    } else {
        Write-Warn "Icon generation failed — shortcut will use default icon"
    }
} else {
    Write-Warn "generate_icon.py not found — skipping icon"
}

# --- 4. Create desktop shortcut ---------------------------------------------

Write-Step "Creating desktop shortcut..."

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Teams Keep-Alive.lnk"
$TargetScript = Join-Path $ScriptDir "teams_keepalive.py"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $RunExe
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ScriptDir
if (Test-Path $IconFile) { $Shortcut.IconLocation = $IconFile }
$Shortcut.Description = "Keep your Microsoft Teams status Available"
$Shortcut.WindowStyle = 7  # Minimised — no console window
$Shortcut.Save()

Write-Ok "Shortcut created: $ShortcutPath"

# --- 5. Optional: Add to startup --------------------------------------------

Write-Step "Add to Windows Startup?"
$StartupDir = [Environment]::GetFolderPath("Startup")
$StartupShortcut = Join-Path $StartupDir "Teams Keep-Alive.lnk"

if (Test-Path $StartupShortcut) {
    Write-Host "  Startup shortcut already exists." -ForegroundColor DarkGray
} else {
    $Response = Read-Host "  Launch Teams Keep-Alive on Windows startup? (y/N)"
    if ($Response -match "^[yY]") {
        $WshShell = New-Object -ComObject WScript.Shell
        $StartupLnk = $WshShell.CreateShortcut($StartupShortcut)
        $StartupLnk.TargetPath = $RunExe
        $StartupLnk.Arguments = "`"$TargetScript`""
        $StartupLnk.WorkingDirectory = $ScriptDir
        if (Test-Path $IconFile) { $StartupLnk.IconLocation = $IconFile }
        $StartupLnk.WindowStyle = 7
        $StartupLnk.Description = "Keep your Microsoft Teams status Available"
        $StartupLnk.Save()
        Write-Ok "Startup shortcut created"
    } else {
        Write-Host "  Skipped." -ForegroundColor DarkGray
    }
}

# --- Done -------------------------------------------------------------------

Write-Host ""
Write-Host "========================================" -ForegroundColor Green
Write-Host "  Installation complete!" -ForegroundColor Green
Write-Host "========================================" -ForegroundColor Green
Write-Host ""
Write-Host "  Desktop shortcut: $ShortcutPath" -ForegroundColor Cyan
Write-Host "  App location:     $ScriptDir" -ForegroundColor Cyan
Write-Host "  Log file:         $env:USERPROFILE\.teams_keepalive\keepalive.log" -ForegroundColor Cyan
Write-Host ""
Write-Host "  Double-click the desktop shortcut to start." -ForegroundColor White
Write-Host ""
Read-Host "Press Enter to close"

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

# --- Find Python -----------------------------------------------------------

$Python = $null
$Pythonw = $null
$Candidates = @(
    @{ Exe = "pythonw"; Name = "pythonw" },
    @{ Exe = "python";  Name = "python" },
    @{ Exe = "pyw";     Name = "pyw" },
    @{ Exe = "py";      Name = "py" }
)

foreach ($Cand in $Candidates) {
    $Cmd = Get-Command $Cand.Exe -ErrorAction SilentlyContinue
    if ($Cmd) {
        if (-not $Pythonw -and $Cand.Exe -match "w$") {
            $Pythonw = $Cmd.Source
        }
        if (-not $Python -and $Cand.Exe -notmatch "w$") {
            $Python = $Cmd.Source
        }
    }
}

$RunExe = $Pythonw
if (-not $RunExe) { $RunExe = $Python }
if (-not $RunExe) {
    Write-Host "Python not found! Please install Python from https://www.python.org/downloads/" -ForegroundColor Red
    Read-Host "Press Enter to exit"
    exit 1
}

# Use python (not pythonw) for icon generation so we can see output
$PythonForGen = $Python
if (-not $PythonForGen) { $PythonForGen = $RunExe }

# --- Generate icon if missing ----------------------------------------------

if (-not (Test-Path $IconFile)) {
    Write-Host "Generating icon file..." -ForegroundColor Yellow
    $GenScript = Join-Path $ScriptDir "generate_icon.py"
    if (Test-Path $GenScript) {
        & $PythonForGen $GenScript
        if (Test-Path $IconFile) {
            Write-Host "Icon generated successfully." -ForegroundColor Green
        } else {
            Write-Host "Warning: Icon generation failed. Shortcut will use default icon." -ForegroundColor Yellow
        }
    } else {
        Write-Host "Warning: generate_icon.py not found. Shortcut will use default icon." -ForegroundColor Yellow
    }
}

# --- Create the shortcut ---------------------------------------------------

$Desktop = [Environment]::GetFolderPath("Desktop")
$ShortcutPath = Join-Path $Desktop "Teams Keep-Alive.lnk"

$WshShell = New-Object -ComObject WScript.Shell
$Shortcut = $WshShell.CreateShortcut($ShortcutPath)
$Shortcut.TargetPath = $RunExe
$Shortcut.Arguments = "`"$TargetScript`""
$Shortcut.WorkingDirectory = $ScriptDir
if (Test-Path $IconFile) {
    $Shortcut.IconLocation = $IconFile
}
$Shortcut.Description = "Keep your Microsoft Teams status Available"
$Shortcut.WindowStyle = 7  # Minimised — no console window
$Shortcut.Save()

Write-Host ""
Write-Host "Desktop shortcut created successfully!" -ForegroundColor Green
Write-Host "  Location: $ShortcutPath" -ForegroundColor Cyan
if (Test-Path $IconFile) {
    Write-Host "  Icon: $IconFile" -ForegroundColor Cyan
}
Write-Host ""
Read-Host "Press Enter to close"

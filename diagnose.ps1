# Teams Keep-Alive - Diagnostic Script
# Run this to check if your system can run the app

Write-Host "=== Teams Keep-Alive Diagnostic ===" -ForegroundColor Cyan
Write-Host ""

# Check Python
Write-Host "1. Checking Python..." -ForegroundColor Yellow
$python = Get-Command python -ErrorAction SilentlyContinue
$pythonw = Get-Command pythonw -ErrorAction SilentlyContinue
if ($python) {
    $version = & python --version 2>&1
    Write-Host "   python found: $version" -ForegroundColor Green
    Write-Host "   path: $($python.Source)" -ForegroundColor Gray
} else {
    Write-Host "   python NOT found!" -ForegroundColor Red
}
if ($pythonw) {
    Write-Host "   pythonw found: $($pythonw.Source)" -ForegroundColor Green
} else {
    Write-Host "   pythonw NOT found (console window will appear)" -ForegroundColor Yellow
}
Write-Host ""

# Check dependencies
Write-Host "2. Checking Python dependencies..." -ForegroundColor Yellow
$deps = @("pystray", "PIL", "pynput")
foreach ($dep in $deps) {
    $result = & python -c "import $dep; print('OK')" 2>&1
    if ($result -eq "OK") {
        Write-Host "   $dep: OK" -ForegroundColor Green
    } else {
        Write-Host "   $dep: MISSING - run: pip install $dep" -ForegroundColor Red
    }
}
Write-Host ""

# Check script exists
Write-Host "3. Checking app files..." -ForegroundColor Yellow
$scriptDir = Split-Path -Parent $MyInvocation.MyCommand.Path
$mainScript = Join-Path $scriptDir "teams_keepalive.py"
$iconScript = Join-Path $scriptDir "generate_icon.py"
if (Test-Path $mainScript) {
    Write-Host "   teams_keepalive.py: Found" -ForegroundColor Green
} else {
    Write-Host "   teams_keepalive.py: NOT FOUND" -ForegroundColor Red
}
if (Test-Path $iconScript) {
    Write-Host "   generate_icon.py: Found" -ForegroundColor Green
} else {
    Write-Host "   generate_icon.py: NOT FOUND" -ForegroundColor Red
}
Write-Host ""

# Check icon
Write-Host "4. Checking icon..." -ForegroundColor Yellow
$iconPath = Join-Path $scriptDir "teams_keepalive.ico"
if (Test-Path $iconPath) {
    $iconSize = (Get-Item $iconPath).Length
    Write-Host "   teams_keepalive.ico: Found ($iconSize bytes)" -ForegroundColor Green
} else {
    Write-Host "   teams_keepalive.ico: Not found. Run: python generate_icon.py" -ForegroundColor Yellow
}
Write-Host ""

# Check config dir
Write-Host "5. Checking config directory..." -ForegroundColor Yellow
$configDir = Join-Path $HOME ".teams_keepalive"
if (Test-Path $configDir) {
    Write-Host "   $configDir: Exists" -ForegroundColor Green
    $logFile = Join-Path $configDir "keepalive.log"
    if (Test-Path $logFile) {
        Write-Host "   keepalive.log: Found" -ForegroundColor Green
        Write-Host "   Last 10 log lines:" -ForegroundColor Gray
        Get-Content $logFile -Tail 10 | ForEach-Object { Write-Host "     $_" -ForegroundColor DarkGray }
    } else {
        Write-Host "   keepalive.log: Not found (app may not have started)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   $configDir: Does not exist (app never started)" -ForegroundColor Yellow
}
Write-Host ""

# Try syntax check
Write-Host "6. Syntax check..." -ForegroundColor Yellow
$result = & python -m py_compile $mainScript 2>&1
if ($LASTEXITCODE -eq 0) {
    Write-Host "   teams_keepalive.py: Syntax OK" -ForegroundColor Green
} else {
    Write-Host "   teams_keepalive.py: SYNTAX ERROR" -ForegroundColor Red
    Write-Host "   $result" -ForegroundColor Red
}
Write-Host ""

Write-Host "=== Diagnostic Complete ===" -ForegroundColor Cyan
Write-Host ""
Write-Host "If all checks are green, try running:"
Write-Host "  python teams_keepalive.py" -ForegroundColor White
Write-Host ""
Write-Host "Press any key to exit..."
$null = $Host.UI.RawUI.ReadKey("NoEcho,IncludeKeyDown")

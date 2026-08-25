#!/usr/bin/env bash
# ============================================================
#  Teams Keep-Alive — Installer for macOS and Linux
#  Usage:
#    chmod +x install.sh
#    ./install.sh
# ============================================================

set -e

SCRIPT_DIR="$( cd "$( dirname "${BASH_SOURCE[0]}" )" && pwd )"
cd "$SCRIPT_DIR"

# --- Helpers ---------------------------------------------------------------

step() { echo ""; echo "▶ $1"; }
ok()   { echo "  ✅ $1"; }
warn() { echo "  ⚠ $1"; }
err()  { echo "  ❌ $1"; }

OS_TYPE="$(uname -s)"
case "$OS_TYPE" in
    Darwin) OS_NAME="macOS" ;;
    Linux)  OS_NAME="Linux" ;;
    *)      OS_NAME="$OS_TYPE" ;;
esac

echo ""
echo "========================================"
echo "  Teams Keep-Alive — Installer ($OS_NAME)"
echo "========================================"

# --- 1. Check Python -------------------------------------------------------

step "Checking for Python 3..."

if command -v python3 &>/dev/null; then
    PYTHON="python3"
elif command -v python &>/dev/null; then
    PYTHON="python"
else
    err "Python 3 not found!"
    echo "  Please install Python 3.8+ from https://www.python.org/downloads/"
    echo "  Or use your package manager:"
    echo "    macOS:  brew install python3"
    echo "    Ubuntu: sudo apt install python3 python3-pip"
    exit 1
fi

PY_VERSION="$($PYTHON --version 2>&1)"
ok "Found $PY_VERSION"

# --- 2. Check pip ----------------------------------------------------------

step "Checking for pip..."

if $PYTHON -m pip --version &>/dev/null; then
    ok "pip is available"
else
    warn "pip not found, attempting to install..."
    if [ "$OS_NAME" = "macOS" ]; then
        $PYTHON -m ensurepip --upgrade 2>/dev/null || warn "Please install pip manually"
    else
        echo "  Try: sudo apt install python3-pip"
        exit 1
    fi
fi

# --- 3. Install dependencies ------------------------------------------------

step "Installing Python dependencies..."

PIP_ARGS="--quiet --user"
if [ "$OS_NAME" = "macOS" ]; then
    # On macOS, --user can conflict with framework Python; skip it
    PIP_ARGS="--quiet"
fi

$PYTHON -m pip install -r requirements.txt $PIP_ARGS 2>&1 | sed 's/^/  /'
ok "Dependencies installed"

# --- 4. Generate icon -------------------------------------------------------

step "Generating desktop icon..."

ICON_FILE="$SCRIPT_DIR/teams_keepalive.ico"
GEN_SCRIPT="$SCRIPT_DIR/generate_icon.py"

if [ -f "$GEN_SCRIPT" ]; then
    $PYTHON "$GEN_SCRIPT" 2>&1 | sed 's/^/  /'
    if [ -f "$ICON_FILE" ]; then
        ICON_SIZE=$(wc -c < "$ICON_FILE" | tr -d ' ')
        ok "Icon created ($ICON_SIZE bytes)"
    else
        warn "Icon generation failed"
    fi
else
    warn "generate_icon.py not found — skipping icon"
fi

# --- 5. Platform-specific desktop integration -------------------------------

step "Creating desktop integration..."

APP_PY="$SCRIPT_DIR/teams_keepalive.py"

if [ "$OS_NAME" = "macOS" ]; then
    # --- macOS: create .app bundle ---
    APP_DIR="$HOME/Applications/Teams Keep-Alive.app"
    MACOS_DIR="$APP_DIR/Contents/MacOS"
    RESOURCES_DIR="$APP_DIR/Contents/Resources"

    mkdir -p "$MACOS_DIR" "$RESOURCES_DIR"

    # Launcher script inside the .app
    cat > "$MACOS_DIR/Teams Keep-Alive" << LAUNCHER
#!/usr/bin/env bash
cd "$SCRIPT_DIR"
exec $PYTHON "$APP_PY"
LAUNCHER
    chmod +x "$MACOS_DIR/Teams Keep-Alive"

    # Info.plist
    cat > "$APP_DIR/Contents/Info.plist" << PLIST
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>CFBundleName</key>
    <string>Teams Keep-Alive</string>
    <key>CFBundleDisplayName</key>
    <string>Teams Keep-Alive</string>
    <key>CFBundleIdentifier</key>
    <string>com.teams-keepalive.app</string>
    <key>CFBundleVersion</key>
    <string>1.0</string>
    <key>CFBundleExecutable</key>
    <string>Teams Keep-Alive</string>
    <key>CFBundlePackageType</key>
    <string>APPL</string>
</dict>
</plist>
PLIST

    # Copy icon if it exists
    if [ -f "$ICON_FILE" ]; then
        cp "$ICON_FILE" "$RESOURCES_DIR/app.icns"
    fi

    ok "App bundle created: $APP_DIR"
    echo "  You can also drag it to /Applications if you prefer."

    # Also create a symlink on Desktop
    DESKTOP_LNK="$HOME/Desktop/Teams Keep-Alive"
    rm -f "$DESKTOP_LNK"
    ln -s "$APP_DIR" "$DESKTOP_LNK"
    ok "Desktop alias created"

    warn "macOS: Grant Accessibility permission!"
    echo "  System Settings → Privacy & Security → Accessibility"
    echo "  Enable Terminal (or the Python app you run this from)."

elif [ "$OS_NAME" = "Linux" ]; then
    # --- Linux: create .desktop file ---
    DESKTOP_FILE="$HOME/.local/share/applications/teams-keepalive.desktop"
    mkdir -p "$(dirname "$DESKTOP_FILE")"

    cat > "$DESKTOP_FILE" << DESKTOP
[Desktop Entry]
Type=Application
Name=Teams Keep-Alive
Comment=Keep your Microsoft Teams status Available
Exec=$PYTHON "$APP_PY"
Path=$SCRIPT_DIR
Icon=$ICON_FILE
Terminal=false
Categories=Utility;Office;
DESKTOP

    chmod +x "$DESKTOP_FILE"
    ok "App menu entry created: $DESKTOP_FILE"

    # Also create a desktop shortcut
    DESKTOP_LNK="$HOME/Desktop/teams-keepalive.desktop"
    cp "$DESKTOP_FILE" "$DESKTOP_LNK"
    chmod +x "$DESKTOP_LNK"
    ok "Desktop shortcut created: $DESKTOP_LNK"

    # Check for tray support
    if ! command -v gnome-shell &>/dev/null && ! command -v plasmashell &>/dev/null; then
        warn "No GNOME/KDE detected. You may need a tray/appindicator extension."
    fi
fi

# --- 6. Optional: Add to autostart ------------------------------------------

step "Add to autostart?"

if [ "$OS_NAME" = "macOS" ]; then
    echo "  To auto-launch on login, add Teams Keep-Alive to:"
    echo "  System Settings → General → Login Items"
    ok "See macOS Login Items settings (manual step)"
else
    AUTOSTART_FILE="$HOME/.config/autostart/teams-keepalive.desktop"
    if [ -f "$AUTOSTART_FILE" ]; then
        ok "Autostart entry already exists"
    else
        read -p "  Launch Teams Keep-Alive on login? (y/N) " -r
        if [[ $REPLY =~ ^[Yy]$ ]]; then
            mkdir -p "$(dirname "$AUTOSTART_FILE")"
            cp "$HOME/.local/share/applications/teams-keepalive.desktop" "$AUTOSTART_FILE"
            ok "Autostart entry created: $AUTOSTART_FILE"
        else
            echo "  Skipped."
        fi
    fi
fi

# --- Done -------------------------------------------------------------------

echo ""
echo "========================================"
echo "  Installation complete!"
echo "========================================"
echo ""
echo "  App location:  $SCRIPT_DIR"
echo "  Log file:      $HOME/.teams_keepalive/keepalive.log"
echo ""
if [ "$OS_NAME" = "macOS" ]; then
    echo "  Launch: Double-click 'Teams Keep-Alive' on your Desktop"
    echo "  Or:     open \"$APP_DIR\""
else
    echo "  Launch: Find 'Teams Keep-Alive' in your application menu"
    echo "  Or:     $PYTHON \"$APP_PY\""
fi
echo ""

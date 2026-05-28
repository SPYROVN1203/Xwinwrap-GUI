#!/bin/bash
set -e

APP="xwinwrap-gui"
VER="1.0.0"
ARCH="amd64"
PKG_DIR="/tmp/${APP}_${VER}_${ARCH}"

echo "=== Building $APP v$VER ==="

# ── Install system dependencies ─────────────────────────
echo ""
echo ">>> Installing system dependencies..."
sudo apt update 2>/dev/null || true
sudo apt install -y \
    mpv \
    xdotool \
    x11-utils \
    socat \
    ffmpeg \
    python3-gi \
    python3-pil \
    python3-gi-cairo \
    build-essential \
    dh-make \
    devscripts \
    pkg-config \
    libx11-dev \
    libxcomposite-dev \
    libxdamage-dev \
    libxrender-dev \
    libxrandr-dev \
    libxfixes-dev \
    libxext-dev

# Build xwinwrap from source if not installed
if ! command -v xwinwrap &>/dev/null; then
    echo ">>> xwinwrap not found — building from source..."
    XW_DIR=$(mktemp -d)
    git clone --depth=1 https://github.com/ujjwal96/xwinwrap.git "$XW_DIR"
    cd "$XW_DIR"
    make
    sudo cp xwinwrap /usr/local/bin/
    cd /tmp
    rm -rf "$XW_DIR"
    echo "    xwinwrap installed to /usr/local/bin/"
fi

# ── Clean previous build ───────────────────────────────
rm -rf "$PKG_DIR"

# ── Create package structure ───────────────────────────
mkdir -p "$PKG_DIR/DEBIAN"
mkdir -p "$PKG_DIR/usr/bin"
mkdir -p "$PKG_DIR/usr/share/$APP"
mkdir -p "$PKG_DIR/usr/share/applications"
mkdir -p "$PKG_DIR/usr/share/icons/hicolor/128x128/apps"
mkdir -p "$PKG_DIR/usr/share/doc/$APP"

# ── DEBIAN/control ─────────────────────────────────────
cat > "$PKG_DIR/DEBIAN/control" <<EOF
Package: $APP
Version: $VER
Section: utils
Priority: optional
Architecture: $ARCH
Depends: python3, python3-gi, python3-pil, mpv, xdotool, x11-utils, socat, ffmpeg
Recommends: xwinwrap
Maintainer: $(whoami) <$(whoami)@$(hostname)>
Description: GTK3 GUI for managing xwinwrap + mpv video wallpapers
 Inspired by Lively Wallpaper / Wallpaper Engine.
 Provides a library browser, playback controls, thumbnail generation,
 dark/light theme, and full configuration of xwinwrap + mpv options.
EOF

# ── DEBIAN/postinst ────────────────────────────────────
cat > "$PKG_DIR/DEBIAN/postinst" <<'POSTINST'
#!/bin/bash
set -e

APP="xwinwrap-gui"

echo ">>> Configuring $APP..."

# Create config directory
CONFIG_DIR="$HOME/.config/xwinwrap-gui"
mkdir -p "$CONFIG_DIR/thumbnails"

# Check dependencies
MISSING=""
for cmd in mpv xdotool xprop socat ffmpeg xwinwrap; do
    if ! command -v "$cmd" &>/dev/null; then
        MISSING="$MISSING $cmd"
    fi
done

if [ -n "$MISSING" ]; then
    echo "WARNING: Missing optional dependencies:$MISSING"
    echo "  Install with: sudo apt install$MISSING"
fi

echo ">>> $APP installed successfully!"
echo "  Run: $APP"
POSTINST
chmod +x "$PKG_DIR/DEBIAN/postinst"

# ── Application files ──────────────────────────────────
cp gui.py "$PKG_DIR/usr/share/$APP/"
cp tools.py "$PKG_DIR/usr/share/$APP/"
cp lang.py "$PKG_DIR/usr/share/$APP/"

# ── Executable wrapper ─────────────────────────────────
cat > "$PKG_DIR/usr/bin/$APP" <<'WRAPPER'
#!/bin/bash
cd /usr/share/xwinwrap-gui
exec python3 gui.py "$@"
WRAPPER
chmod +x "$PKG_DIR/usr/bin/$APP"

# ── .desktop file ─────────────────────────────────────
cat > "$PKG_DIR/usr/share/applications/${APP}.desktop" <<DESKTOP
[Desktop Entry]
Type=Application
Name=Xwinwrap Manager
GenericName=Xwinwrap Manager
Comment=Manage xwinwrap + mpv video wallpapers
Exec=$APP
Icon=$APP
Terminal=false
Categories=Utility;Graphics;Video;
Keywords=wallpaper;video;live;mpv;xwinwrap;
DESKTOP

# ── Icon ────────────────────────────────────────────────
if [ -f "icon.ico" ]; then
    echo ">>> Converting icon.ico to PNG..."
    python3 -c "
from PIL import Image
img = Image.open('icon.ico')
if getattr(img, 'n_frames', 1) > 1:
    frames = [img.copy()]
    for i in range(1, img.n_frames):
        img.seek(i)
        frames.append(img.copy())
    img = max(frames, key=lambda f: f.size[0] * f.size[1])
if img.size != (128, 128):
    img = img.resize((128, 128), Image.LANCZOS)
img.save('$PKG_DIR/usr/share/icons/hicolor/128x128/apps/${APP}.png', 'PNG')
"
    echo ">>> icon.ico converted and installed"
elif [ -f "icon.png" ]; then
    cp icon.png "$PKG_DIR/usr/share/icons/hicolor/128x128/apps/${APP}.png"
    echo ">>> Using icon.png from project directory"
else
    echo "WARNING: icon.png / icon.ico not found — generating placeholder..."
    python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (128, 128), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([(8, 8), (120, 120)], radius=20,
    fill=(78, 205, 196), outline=(60, 180, 170), width=2)
draw.polygon([(50, 35), (50, 93), (95, 64)], fill=(13, 13, 26))
img.save('$PKG_DIR/usr/share/icons/hicolor/128x128/apps/${APP}.png', 'PNG')
"
fi

# ── Changelog ──────────────────────────────────────────
cat > "$PKG_DIR/usr/share/doc/$APP/changelog" <<EOF
$APP ($VER) unstable; urgency=medium

  * Initial release.

 -- $(whoami) <$(whoami)@$(hostname)>  $(date -R)
EOF

gzip -9 "$PKG_DIR/usr/share/doc/$APP/changelog"

# ── Build .deb ─────────────────────────────────────────
echo ""
echo ">>> Building .deb package..."
DEB_FILE="${APP}_${VER}_${ARCH}.deb"
fakeroot dpkg-deb --build "$PKG_DIR" "$DEB_FILE" >/dev/null

echo ""
echo "=== Package built successfully ==="
echo "  File: $DEB_FILE"
echo "  Size: $(du -h "$DEB_FILE" | cut -f1)"
echo ""
echo "  Install with: sudo dpkg -i $DEB_FILE"
echo "  Remove with:  sudo dpkg -r $APP"

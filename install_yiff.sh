#!/bin/bash
# ============================================================
# 🐾 Yiff Downloader - Automatic Installer
# ============================================================

set -e

# Colors for output
R='\033[0;31m'
G='\033[0;32m'
Y='\033[1;33m'
B='\033[0;34m'
P='\033[0;35m'
NC='\033[0m'

echo -e "${P}"
echo "=============================================="
echo "  🐾 Yiff Downloader - Installer"
echo "=============================================="
echo -e "${NC}"

# ---------- Paths ----------
APP_DIR="$HOME/YiffDownloader"
DESKTOP_DIR="$HOME/.local/share/applications"
DESKTOP_FILE="$DESKTOP_DIR/yiff-downloader.desktop"
ICON_FILE="$APP_DIR/icon.png"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# ---------- Step 1: System packages ----------
echo -e "${B}[1/7]${NC} Installing system packages (needs sudo)..."
sudo apt update -qq
sudo apt install -y python3 python3-venv python3-tk ffmpeg wmctrl xdotool > /dev/null 2>&1
echo -e "${G}   ✓ Done${NC}"

# ---------- Step 2: Create app dir ----------
echo -e "${B}[2/7]${NC} Creating app directory..."
mkdir -p "$APP_DIR"
cd "$APP_DIR"
echo -e "${G}   ✓ $APP_DIR${NC}"

# ---------- Step 3: Copy app file ----------
echo -e "${B}[3/7]${NC} Copying application..."
if [ -f "$SCRIPT_DIR/yiff_downloader.py" ]; then
    cp "$SCRIPT_DIR/yiff_downloader.py" "$APP_DIR/yiff_downloader.py"
    echo -e "${G}   ✓ Copied from $SCRIPT_DIR${NC}"
else
    echo -e "${Y}   ⚠ yiff_downloader.py not found in $SCRIPT_DIR${NC}"
    echo -e "${Y}   Please place yiff_downloader.py next to this installer.${NC}"
    exit 1
fi

# ---------- Step 4: Virtual env ----------
echo -e "${B}[4/7]${NC} Setting up virtual environment..."
if [ ! -d "$APP_DIR/.venv" ]; then
    python3 -m venv "$APP_DIR/.venv"
fi
source "$APP_DIR/.venv/bin/activate"
pip install --upgrade pip -q
pip install customtkinter pillow requests -q
deactivate
echo -e "${G}   ✓ Virtual environment ready${NC}"

# ---------- Step 5: Install icon and GIF ----------
echo -e "${B}[5/7]${NC} Installing icon and header GIF..."

if [ -f "$SCRIPT_DIR/assets/icon.png" ]; then
    cp "$SCRIPT_DIR/assets/icon.png" "$APP_DIR/icon.png"
    echo -e "${G}   ✓ Icon installed from assets${NC}"
else
    echo -e "${Y}   ⚠ assets/icon.png not found, generating default${NC}"
    python3 -c "
from PIL import Image, ImageDraw
img = Image.new('RGBA', (512, 512), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)
draw.rounded_rectangle([40, 40, 472, 472], radius=100, fill=(255, 140, 66, 255))
draw.ellipse([190, 280, 320, 400], fill=(26, 22, 37, 255))
draw.ellipse([140, 180, 210, 250], fill=(26, 22, 37, 255))
draw.ellipse([230, 150, 300, 220], fill=(26, 22, 37, 255))
draw.ellipse([310, 180, 380, 250], fill=(26, 22, 37, 255))
img.save('$APP_DIR/icon.png', 'PNG')
"
    echo -e "${G}   ✓ Default icon created${NC}"
fi

if [ -f "$SCRIPT_DIR/assets/header.gif" ]; then
    cp "$SCRIPT_DIR/assets/header.gif" "$APP_DIR/header.gif"
    echo -e "${G}   ✓ Header GIF installed${NC}"
fi

# Generate system icons for taskbar
python3 -c "
from PIL import Image
from pathlib import Path
src = Path('$APP_DIR/icon.png')
if src.exists():
    img = Image.open(src).convert('RGBA')
    icons_dir = Path.home() / '.local' / 'share' / 'icons' / 'hicolor'
    for s in [16, 32, 48, 64, 128, 256, 512]:
        d = icons_dir / f'{s}x{s}' / 'apps'
        d.mkdir(parents=True, exist_ok=True)
        img.resize((s, s), Image.LANCZOS).save(d / 'yiff-downloader.png', 'PNG')
"
echo -e "${G}   ✓ System icons generated${NC}"

# ---------- Step 6: Create smart launcher ----------
echo -e "${B}[6/7]${NC} Creating smart launcher..."

cat > "$APP_DIR/launch.sh" << 'LAUNCHER_EOF'
#!/bin/bash
# Yiff Downloader - Smart Launcher
APP_DIR="__APP_DIR__"
PYTHON_SCRIPT="$APP_DIR/yiff_downloader.py"
VENV="$APP_DIR/.venv"

if pgrep -f "python3.*yiff_downloader.py" > /dev/null 2>&1; then
    if command -v wmctrl > /dev/null 2>&1; then
        wmctrl -a "Yiff Downloader" 2>/dev/null && exit 0
    fi
    if command -v xdotool > /dev/null 2>&1; then
        WID=$(xdotool search --name "Yiff Downloader" 2>/dev/null | head -1)
        if [ -n "$WID" ]; then
            xdotool windowactivate "$WID" 2>/dev/null && exit 0
        fi
    fi
    exit 0
fi

cd "$APP_DIR"
source "$VENV/bin/activate"
exec python3 "$PYTHON_SCRIPT"
LAUNCHER_EOF

sed -i "s|__APP_DIR__|$APP_DIR|g" "$APP_DIR/launch.sh"
chmod +x "$APP_DIR/launch.sh"
echo -e "${G}   ✓ Smart launcher created${NC}"

# ---------- Step 7: Create desktop entry ----------
echo -e "${B}[7/7]${NC} Creating desktop entry..."
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Yiff Downloader
Comment=Furry-themed media downloader
Exec=$APP_DIR/launch.sh
Icon=$ICON_FILE
Terminal=false
Categories=Network;FileTransfer;Utility;
StartupNotify=true
StartupWMClass=Yiff Downloader
EOF

chmod +x "$DESKTOP_FILE"

if command -v update-desktop-database > /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
echo -e "${G}   ✓ Desktop entry created${NC}"

# ---------- Copy to Desktop ----------
DESK="$HOME/Desktop"
[ -d "$HOME/Desktop" ] || DESK="$HOME/سطح المكتب"
[ -d "$DESK" ] || DESK="$HOME/Desktop"
mkdir -p "$DESK"
cp "$DESKTOP_FILE" "$DESK/Yiff Downloader.desktop"
chmod +x "$DESK/Yiff Downloader.desktop"

if command -v gio > /dev/null; then
    gio set "$DESK/Yiff Downloader.desktop" metadata::trusted true 2>/dev/null || true
fi
echo -e "${G}   ✓ Desktop shortcut: $DESK/Yiff Downloader.desktop${NC}"

# ---------- Done ----------
echo ""
echo -e "${G}=============================================="
echo "  ✅ Installation Complete!"
echo -e "=============================================="
echo -e "${NC}"
echo -e "🐾 App location:    ${B}$APP_DIR${NC}"
echo -e "🐾 Icon:            ${B}$ICON_FILE${NC}"
echo -e "🐾 Desktop file:    ${B}$DESKTOP_FILE${NC}"
echo -e "🐾 Desktop shortcut: ${B}$DESK/Yiff Downloader.desktop${NC}"
echo ""
echo -e "${Y}⚠ Note: On first launch, go to Settings and add your e621 API key${NC}"
echo -e "${Y}   without it, downloads are limited to 320 posts.${NC}"
echo ""
echo -e "${B}Launching app now...${NC}"
sleep 2

# ---------- Launch ----------
cd "$APP_DIR"
source "$APP_DIR/.venv/bin/activate"
python3 yiff_downloader.py &

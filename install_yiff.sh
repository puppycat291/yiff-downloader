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
sudo apt install -y python3 python3-venv python3-tk ffmpeg > /dev/null 2>&1
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

# ---------- Step 5: Create icon ----------
echo -e "${B}[5/7]${NC} Creating icon..."
python3 << 'PYEOF'
from PIL import Image, ImageDraw, ImageFont
import os

icon_path = os.path.expanduser("~/YiffDownloader/icon.png")
size = 256

# Create orange gradient background
img = Image.new("RGBA", (size, size), (0, 0, 0, 0))
draw = ImageDraw.Draw(img)

# Rounded rect background
margin = 20
draw.rounded_rectangle(
    [margin, margin, size - margin, size - margin],
    radius=50,
    fill=(255, 140, 66, 255)  # Furry orange
)

# Try to draw paw emoji
try:
    # Try common emoji fonts
    font_paths = [
        "/usr/share/fonts/truetype/noto/NotoColorEmoji.ttf",
        "/usr/share/fonts/truetype/noto/NotoEmoji-Regular.ttf",
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
    ]
    font = None
    for fp in font_paths:
        if os.path.exists(fp):
            try:
                font = ImageFont.truetype(fp, 140)
                break
            except Exception:
                continue

    if font:
        # Try paw emoji
        text = "🐾"
        try:
            bbox = draw.textbbox((0, 0), text, font=font)
            w = bbox[2] - bbox[0]
            h = bbox[3] - bbox[1]
            draw.text(
                ((size - w) / 2 - bbox[0], (size - h) / 2 - bbox[1]),
                text, font=font, fill=(26, 22, 37, 255)
            )
        except Exception:
            # Fallback: draw simple paw shape
            raise Exception("emoji failed")
    else:
        raise Exception("no font")
except Exception:
    # Draw a simple paw shape
    draw.ellipse([95, 140, 160, 200], fill=(26, 22, 37, 255))  # main pad
    # toes
    draw.ellipse([70, 90, 105, 125], fill=(26, 22, 37, 255))
    draw.ellipse([115, 75, 150, 110], fill=(26, 22, 37, 255))
    draw.ellipse([155, 90, 190, 125], fill=(26, 22, 37, 255))

img.save(icon_path, "PNG")
print(f"   Icon saved: {icon_path}")
PYEOF
echo -e "${G}   ✓ Icon created${NC}"

# ---------- Step 6: Create desktop entry ----------
echo -e "${B}[6/7]${NC} Creating desktop entry..."
mkdir -p "$DESKTOP_DIR"

cat > "$DESKTOP_FILE" << EOF
[Desktop Entry]
Version=1.0
Type=Application
Name=Yiff Downloader
Comment=Furry-themed e621 downloader
Exec=bash -c 'cd $APP_DIR && source .venv/bin/activate && python3 yiff_downloader.py'
Icon=$ICON_FILE
Terminal=false
Categories=Network;FileTransfer;Utility;
StartupNotify=true
EOF

chmod +x "$DESKTOP_FILE"

# Update desktop database
if command -v update-desktop-database > /dev/null; then
    update-desktop-database "$DESKTOP_DIR" 2>/dev/null || true
fi
echo -e "${G}   ✓ Desktop entry created${NC}"

# ---------- Step 7: Copy to Desktop ----------
echo -e "${B}[7/7]${NC} Creating desktop shortcut..."
# Try to detect desktop folder
if [ -d "$HOME/Desktop" ]; then
    DESK="$HOME/Desktop"
elif [ -d "$HOME/سطح المكتب" ]; then
    DESK="$HOME/سطح المكتب"
else
    DESK="$HOME/Desktop"
    mkdir -p "$DESK"
fi

cp "$DESKTOP_FILE" "$DESK/Yiff Downloader.desktop"
chmod +x "$DESK/Yiff Downloader.desktop"

# Mark as trusted (GNOME)
if command -v gio > /dev/null; then
    gio set "$DESK/Yiff Downloader.desktop" metadata::trusted true 2>/dev/null || true
fi
echo -e "${G}   ✓ Shortcut: $DESK/Yiff Downloader.desktop${NC}"

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

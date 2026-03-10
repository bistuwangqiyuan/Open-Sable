#!/bin/bash
# ============================================================
#  Open-Sable,  1-Click Setup (Linux / macOS)
#  This script ensures Python 3.11+ exists, then delegates
#  everything to install.py which handles the full setup.
# ============================================================
set -e

BOLD="\033[1m"
GREEN="\033[32m"
YELLOW="\033[33m"
RED="\033[31m"
CYAN="\033[36m"
RESET="\033[0m"

header() { echo -e "\n${BOLD}${CYAN}$1${RESET}"; }
ok()     { echo -e "  ${GREEN}✓${RESET} $1"; }
warn()   { echo -e "  ${YELLOW}!${RESET} $1"; }
fail()   { echo -e "  ${RED}✗${RESET} $1"; }

echo -e "${BOLD}${CYAN}"
echo "╔═══════════════════════════════════════════╗"
echo "║     Open-Sable ,   1-Click Setup          ║"
echo "╚═══════════════════════════════════════════╝"
echo -e "${RESET}"

# ------------------------------------------------------------------
#  1. Ensure Python 3.11+ is available
# ------------------------------------------------------------------
header "Checking Python..."

need_python=false

if command -v python3 &>/dev/null; then
    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 11 ]; then
        ok "Python $PY_VER found"
    else
        warn "Python $PY_VER found but 3.11+ is required"
        need_python=true
    fi
else
    warn "Python 3 not found"
    need_python=true
fi

if [ "$need_python" = true ]; then
    header "Installing Python 3..."

    if [[ "$OSTYPE" == "darwin"* ]]; then
        # macOS,  try Homebrew first, then Xcode Command Line Tools
        if command -v brew &>/dev/null; then
            echo "  Installing via Homebrew..."
            brew install python@3.12
            ok "Python installed via Homebrew"
        else
            echo "  Installing Homebrew first..."
            /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
            # Add brew to path for current session
            if [ -f /opt/homebrew/bin/brew ]; then
                eval "$(/opt/homebrew/bin/brew shellenv)"
            elif [ -f /usr/local/bin/brew ]; then
                eval "$(/usr/local/bin/brew shellenv)"
            fi
            brew install python@3.12
            ok "Homebrew + Python installed"
        fi
    else
        # Linux,  try package manager
        if command -v apt-get &>/dev/null; then
            echo "  Installing via apt (may ask for sudo password)..."
            sudo apt-get update -qq
            sudo apt-get install -y python3.12 python3.12-venv python3.12-dev python3-pip 2>/dev/null \
                || sudo apt-get install -y python3.11 python3.11-venv python3.11-dev python3-pip 2>/dev/null \
                || sudo apt-get install -y python3 python3-venv python3-dev python3-pip
            ok "Python installed via apt"
        elif command -v dnf &>/dev/null; then
            echo "  Installing via dnf (may ask for sudo password)..."
            sudo dnf install -y python3.12 python3.12-devel 2>/dev/null \
                || sudo dnf install -y python3.11 python3.11-devel 2>/dev/null \
                || sudo dnf install -y python3 python3-devel python3-pip
            ok "Python installed via dnf"
        elif command -v pacman &>/dev/null; then
            echo "  Installing via pacman (may ask for sudo password)..."
            sudo pacman -Sy --noconfirm python python-pip
            ok "Python installed via pacman"
        elif command -v zypper &>/dev/null; then
            echo "  Installing via zypper (may ask for sudo password)..."
            sudo zypper install -y python312 python312-pip 2>/dev/null \
                || sudo zypper install -y python311 python311-pip 2>/dev/null \
                || sudo zypper install -y python3 python3-pip
            ok "Python installed via zypper"
        else
            fail "No supported package manager found (apt, dnf, pacman, zypper)"
            echo ""
            echo "  Please install Python 3.11+ manually:"
            echo "    https://www.python.org/downloads/"
            echo ""
            echo "  Then re-run:  ./quickstart.sh"
            exit 1
        fi
    fi

    # Verify installation worked
    if ! command -v python3 &>/dev/null; then
        fail "Python installation failed. Please install Python 3.11+ manually."
        exit 1
    fi

    PY_VER=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    ok "Python $PY_VER ready"
fi

# ------------------------------------------------------------------
#  2. Delegate to install.py (it handles everything else)
# ------------------------------------------------------------------
header "Launching installer..."
echo ""

# Pass through any arguments, default to --full
if [ $# -eq 0 ]; then
    python3 install.py --full
else
    python3 install.py "$@"
fi

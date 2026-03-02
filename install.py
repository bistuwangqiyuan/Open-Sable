#!/usr/bin/env python3
"""
Open-Sable Installation Script
Automated one-click installer for all platforms
"""

import sys
import subprocess
import platform
from pathlib import Path


def print_banner():
    """Print installation banner"""
    print("""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   🚀 Open-Sable Automated Installer                       ║
║   Your personal AI that actually does things              ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝
""")


def check_python_version():
    """Ensure Python 3.11+"""
    version = sys.version_info
    if version.major < 3 or (version.major == 3 and version.minor < 11):
        print("❌ Python 3.11 or higher is required")
        print(f"   Current version: {version.major}.{version.minor}")
        sys.exit(1)
    print(f"✅ Python {version.major}.{version.minor} detected")


def install_ollama():
    """Install Ollama automatically if not present"""
    try:
        result = subprocess.run(["ollama", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            print("✅ Ollama is already installed")
            return True
    except FileNotFoundError:
        pass

    print("📥 Ollama not found - installing automatically...")
    os_type = platform.system()

    try:
        if os_type == "Darwin":
            print("   Installing via Homebrew...")
            subprocess.run(["brew", "install", "ollama"], check=True)
        elif os_type == "Linux":
            print("   Installing via official script...")
            subprocess.run(
                ["bash", "-c", "curl -fsSL https://ollama.com/install.sh | sh"],
                check=True,
            )
        elif os_type == "Windows":
            print("❌ Cannot auto-install on Windows")
            print("   Please download from: https://ollama.com/download")
            return False

        print("✅ Ollama installed successfully")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        print("❌ Failed to install Ollama automatically")
        print("   Please install manually from: https://ollama.com")
        return False


def create_venv():
    """Create virtual environment if not exists"""
    venv_path = Path("venv")

    if venv_path.exists():
        print("✅ Virtual environment already exists")
        return True

    print("\n🔨 Creating virtual environment...")
    try:
        subprocess.run([sys.executable, "-m", "venv", "venv"], check=True)
        print("✅ Virtual environment created")
        return True
    except subprocess.CalledProcessError:
        print("❌ Failed to create virtual environment")
        return False


def get_venv_python():
    """Get path to venv Python executable"""
    if platform.system() == "Windows":
        return Path("venv") / "Scripts" / "python.exe"
    else:
        return Path("venv") / "bin" / "python"


def install_dependencies():
    """Install Python dependencies in venv"""
    print("\n📦 Installing dependencies...")

    venv_python = get_venv_python()

    try:
        # Upgrade pip first
        print("   Upgrading pip...")
        subprocess.run(
            [str(venv_python), "-m", "pip", "install", "--upgrade", "pip", "setuptools", "wheel"],
            check=True,
            capture_output=True,
        )

        # Install package with core dependencies
        print("   Installing opensable[core]...")
        subprocess.run([str(venv_python), "-m", "pip", "install", "-e", ".[core]"], check=True)
        print("✅ Dependencies installed successfully")
        return True
    except subprocess.CalledProcessError as e:
        print(f"❌ Failed to install dependencies: {e}")
        return False


def install_playwright():
    """Install Playwright browsers"""
    print("\n🌐 Installing Playwright browsers...")

    venv_python = get_venv_python()
    try:
        subprocess.run([str(venv_python), "-m", "playwright", "install", "chromium"], check=True)
        print("✅ Playwright browsers installed")
        return True
    except subprocess.CalledProcessError:
        print("⚠️  Playwright browser installation failed (optional)")
        return False


def patch_aggr_tracking(aggr_dir: Path):
    """Remove all tracking/analytics from aggr (GTM, etc)."""
    import re

    targets = [
        aggr_dir / "index.html",
        aggr_dir / "dist" / "index.html",
    ]

    patterns = [
        # Google Tag Manager <script> block
        (r'\s*<!-- Google Tag Manager -->.*?<!-- End Google Tag Manager -->\s*', '\n'),
        # Google Tag Manager (noscript) block
        (r'\s*<!-- Google Tag Manager \(noscript\) -->.*?<!-- End Google Tag Manager \(noscript\) -->\s*', '\n'),
        # Standalone GTM/gtag script tags (fallback)
        (r'<script[^>]*>[^<]*googletagmanager[^<]*</script>', ''),
        (r'<noscript[^>]*>[^<]*googletagmanager[^<]*</noscript>', ''),
        # Any remaining GTM iframe
        (r'<iframe[^>]*googletagmanager[^>]*>[^<]*</iframe[^>]*>', ''),
        # Google Analytics
        (r'<script[^>]*>[^<]*google-analytics[^<]*</script>', ''),
        (r'<script[^>]*>[^<]*\.google\.com/analytics[^<]*</script>', ''),
        # Generic tracking pixels / beacons
        (r'<script[^>]*>[^<]*(?:hotjar|fbq|mixpanel|amplitude|segment\.io|fullstory|clarity\.ms)[^<]*</script>', ''),
        # Fix base href for /aggr/ subpath
        (r'<base\s+href="/"\s*/>', '<base href="/aggr/" />'),
    ]

    patched_count = 0
    for fp in targets:
        if not fp.exists():
            continue
        content = fp.read_text(encoding="utf-8")
        original = content
        for pat, repl in patterns:
            content = re.sub(pat, repl, content, flags=re.DOTALL | re.IGNORECASE)
        if content != original:
            fp.write_text(content, encoding="utf-8")
            patched_count += 1

    if patched_count:
        print(f"   \U0001f6e1\ufe0f  Stripped tracking from {patched_count} file(s)")
    return patched_count


def install_aggr():
    """Install Aggr.trade charts (crypto market visualization)"""
    print("\n📈 Setting up Aggr.trade charts...")

    aggr_dir = Path("aggr")
    aggr_dist = aggr_dir / "dist"
    templates_dir = aggr_dir / "templates"

    # Check if already built
    if aggr_dist.exists() and (aggr_dist / "index.html").exists():
        print("✅ Aggr.trade already installed and built")
        return True

    # Check Node.js
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("⚠️  Node.js required for Aggr.trade - skipping")
            return False
        print(f"   Node.js {result.stdout.strip()} detected")
    except FileNotFoundError:
        print("⚠️  Node.js not found - skipping Aggr.trade installation")
        return False

    try:
        # Clone main aggr app
        if not aggr_dir.exists():
            print("   📥 Cloning Aggr.trade...")
            subprocess.run(
                ["git", "clone", "--depth=1", "https://github.com/Tucsky/aggr.git", str(aggr_dir)],
                check=True,
            )

        # Clone templates
        if not templates_dir.exists():
            print("   📥 Cloning Aggr templates...")
            subprocess.run(
                ["git", "clone", "--depth=1", "https://github.com/0xd3lbow/aggr.template.git", str(templates_dir)],
                check=True,
            )

        # npm install
        print("   📦 Installing Aggr dependencies (this may take a minute)...")
        subprocess.run(["npm", "install"], cwd=str(aggr_dir), check=True)
        # Create .env.local with production settings (CORS proxy + base path)
        env_local = aggr_dir / ".env.local"
        if not env_local.exists():
            env_local.write_text(
                "VITE_APP_PROXY_URL=https://cors.aggr.trade/\n"
                "VITE_APP_API_URL=https://api.aggr.trade/\n"
                "VITE_APP_LIB_URL=https://lib.aggr.trade/\n"
                "VITE_APP_LIB_REPO_URL=https://github.com/Tucsky/aggr-lib\n"
                "VITE_APP_BASE_PATH=/aggr/\n"
                "VITE_APP_API_SUPPORTED_TIMEFRAMES=5,10,15,30,60,180,300,900,1260,1800,3600,7200,14400,21600,28800,43200,86400\n"
            )
        # Build static dist with correct base path for /aggr/ route
        print("   🔨 Building Aggr.trade...")
        subprocess.run(["npx", "vite", "build", "--base", "/aggr/"], cwd=str(aggr_dir), check=True)

        if aggr_dist.exists() and (aggr_dist / "index.html").exists():
            patch_aggr_tracking(aggr_dir)
            print("✅ Aggr.trade installed and built successfully")
            return True
        else:
            print("⚠️  Build completed but dist not found")
            return False

    except subprocess.CalledProcessError as e:
        print(f"⚠️  Aggr.trade installation failed: {e}")
        print("   You can install manually later: cd aggr && npm install && npm run build")
        return False
    except FileNotFoundError:
        print("⚠️  git or npm not found - skipping Aggr.trade")
        return False


def ensure_nodejs():
    """Check Node.js is available, return version string or None"""
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return result.stdout.strip()
    except FileNotFoundError:
        pass
    return None


def install_nodejs_if_missing():
    """Install Node.js via nvm if not present"""
    if ensure_nodejs():
        return True

    print("   📥 Node.js not found — installing via nvm...")
    os_type = platform.system()
    try:
        if os_type == "Linux" or os_type == "Darwin":
            subprocess.run(
                ["bash", "-c",
                 'curl -o- https://raw.githubusercontent.com/nvm-sh/nvm/v0.40.1/install.sh | bash '
                 '&& export NVM_DIR="$HOME/.nvm" '
                 '&& [ -s "$NVM_DIR/nvm.sh" ] && . "$NVM_DIR/nvm.sh" '
                 '&& nvm install --lts'],
                check=True,
            )
            print("✅ Node.js installed via nvm")
            return True
        else:
            print("⚠️  Please install Node.js manually: https://nodejs.org")
            return False
    except subprocess.CalledProcessError:
        print("⚠️  Failed to install Node.js automatically")
        print("   Install manually: https://nodejs.org")
        return False


def install_pnpm_if_missing():
    """Install pnpm if not present"""
    try:
        result = subprocess.run(["pnpm", "--version"], capture_output=True, text=True)
        if result.returncode == 0:
            return True
    except FileNotFoundError:
        pass

    print("   📥 pnpm not found — installing...")
    try:
        subprocess.run(["npm", "install", "-g", "pnpm"], check=True)
        print("✅ pnpm installed")
        return True
    except (subprocess.CalledProcessError, FileNotFoundError):
        try:
            subprocess.run(
                ["bash", "-c", "curl -fsSL https://get.pnpm.io/install.sh | sh -"],
                check=True,
            )
            print("✅ pnpm installed via standalone script")
            return True
        except subprocess.CalledProcessError:
            print("⚠️  Failed to install pnpm")
            return False


def install_dashboard():
    """Build the React dashboard (Vite + React SPA served by the gateway)"""
    print("\n📊 Setting up React Dashboard...")

    dashboard_dir = Path("dashboard")
    dist_dir = dashboard_dir / "dist"

    if dist_dir.exists() and (dist_dir / "index.html").exists():
        print("✅ Dashboard already built")
        return True

    if not dashboard_dir.exists() or not (dashboard_dir / "package.json").exists():
        print("⚠️  dashboard/ folder not found — skipping")
        return False

    node_ver = ensure_nodejs()
    if not node_ver:
        if not install_nodejs_if_missing():
            print("⚠️  Node.js required for dashboard — skipping")
            return False
        node_ver = ensure_nodejs()

    print(f"   Node.js {node_ver} detected")

    try:
        print("   📦 Installing dashboard dependencies...")
        subprocess.run(["npm", "install"], cwd=str(dashboard_dir), check=True)
        print("   🔨 Building dashboard...")
        subprocess.run(["npm", "run", "build"], cwd=str(dashboard_dir), check=True)

        if dist_dir.exists() and (dist_dir / "index.html").exists():
            print("✅ Dashboard built successfully")
            return True
        else:
            print("⚠️  Dashboard build completed but dist not found")
            return False
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Dashboard build failed: {e}")
        print("   You can build manually: cd dashboard && npm install && npm run build")
        return False


def install_marketplace():
    """Build the Skills Marketplace (Express server + React client)"""
    print("\n🏪 Setting up Skills Marketplace...")

    server_dir = Path("marketplace/server")
    client_dir = Path("marketplace/client")

    if not server_dir.exists() or not client_dir.exists():
        print("⚠️  marketplace/ folder not found — skipping")
        return False

    node_ver = ensure_nodejs()
    if not node_ver:
        if not install_nodejs_if_missing():
            print("⚠️  Node.js required for marketplace — skipping")
            return False

    # Build server
    if (server_dir / "package.json").exists():
        try:
            print("   📦 Installing marketplace server dependencies...")
            subprocess.run(["npm", "install"], cwd=str(server_dir), check=True)
            print("✅ Marketplace server ready")
        except subprocess.CalledProcessError as e:
            print(f"⚠️  Marketplace server setup failed: {e}")

    # Build client
    if (client_dir / "package.json").exists():
        client_built = (client_dir / "build" / "index.html").exists()
        if client_built:
            print("✅ Marketplace client already built")
        else:
            try:
                print("   📦 Installing marketplace client dependencies...")
                subprocess.run(["npm", "install"], cwd=str(client_dir), check=True)
                print("   🔨 Building marketplace client...")
                subprocess.run(["npm", "run", "build"], cwd=str(client_dir), check=True)
                print("✅ Marketplace client built")
            except subprocess.CalledProcessError as e:
                print(f"⚠️  Marketplace client build failed: {e}")
                print("   Build manually: cd marketplace/client && npm install && npm run build")

    return True


def install_desktop():
    """Set up the OpenSable Desktop Agent (Electron app)"""
    print("\n🖥️  Setting up Desktop Agent...")

    desktop_dir = Path("desktop")

    if not desktop_dir.exists() or not (desktop_dir / "package.json").exists():
        print("⚠️  desktop/ folder not found — skipping")
        return False

    # Check if already built
    dist_dir = desktop_dir / "dist"
    if dist_dir.exists() and (dist_dir / "index.html").exists():
        print("✅ Desktop agent already built")
        return True

    node_ver = ensure_nodejs()
    if not node_ver:
        if not install_nodejs_if_missing():
            print("⚠️  Node.js required for desktop agent — skipping")
            return False

    try:
        print("   📦 Installing desktop dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(desktop_dir),
            check=True,
        )

        # Build web renderer (Vite)
        print("   🔨 Building desktop agent...")
        subprocess.run(
            ["npm", "run", "build"],
            cwd=str(desktop_dir),
            check=True,
        )

        if dist_dir.exists():
            print("✅ Desktop agent built successfully")
            print("   Launch with: cd desktop && npm run dev")
            return True
        else:
            print("⚠️  Desktop build completed but dist/ not found")
            return False
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Desktop agent build failed: {e}")
        print("   Build manually: cd desktop && npm install && npm run build")
        return False


def install_dev_studio():
    """Set up Sable Dev Studio — AI-powered app builder (like Lovable)"""
    print("\n🛠️  Setting up Dev Studio...")

    dev_dir = Path("sable_dev")

    if not dev_dir.exists() or not (dev_dir / "package.json").exists():
        print("⚠️  sable_dev/ folder not found — skipping")
        return False

    node_ver = ensure_nodejs()
    if not node_ver:
        if not install_nodejs_if_missing():
            print("⚠️  Node.js required for Dev Studio — skipping")
            return False

    # Check if deps already installed
    if (dev_dir / "node_modules" / ".bin" / "next").exists():
        print("✅ Dev Studio already installed")
        return True

    try:
        print("   📦 Installing Dev Studio dependencies...")
        subprocess.run(
            ["npm", "install"],
            cwd=str(dev_dir),
            check=True,
        )

        if (dev_dir / "node_modules" / ".bin" / "next").exists():
            print("✅ Dev Studio installed successfully")
            print("   Uses local sandbox (no API keys needed for sandboxes)")
            print("   Configure AI providers in sable_dev/.env.local")
            print("   Start with: cd sable_dev && npm run dev")

            # Enable in .env if not already set
            env_path = Path(".env")
            if env_path.exists():
                env_content = env_path.read_text()
                if "DEV_STUDIO_ENABLED" not in env_content:
                    with open(env_path, "a") as f:
                        f.write("\n# Dev Studio (AI app builder)\nDEV_STUDIO_ENABLED=true\n")
                    print("   Added DEV_STUDIO_ENABLED=true to .env")
            return True
        else:
            print("⚠️  Dev Studio install completed but next binary not found")
            return False
    except subprocess.CalledProcessError as e:
        print(f"⚠️  Dev Studio install failed: {e}")
        print("   Install manually: cd sable_dev && npm install")
        return False


def install_whatsapp_bridge():
    """Install WhatsApp bridge (whatsapp-web.js) for WhatsApp integration"""
    print("\n💬 Install WhatsApp bridge? (y/n): ", end="")
    choice = input().strip().lower()
    if choice != "y":
        print("⏭️  Skipping WhatsApp bridge installation")
        return

    # Check if Node.js is installed
    try:
        result = subprocess.run(["node", "--version"], capture_output=True, text=True)
        if result.returncode != 0:
            print("❌ Node.js is required for WhatsApp integration")
            print("   Install Node.js 16+ and run installer again")
            return
        print(f"✅ Node.js {result.stdout.strip()} detected")
    except FileNotFoundError:
        print("❌ Node.js not found - install it first")
        return

    bridge_dir = Path("whatsapp-bridge")

    # Check if already exists
    if bridge_dir.exists() and (bridge_dir / "package.json").exists():
        print("✅ WhatsApp bridge already installed")
        return

    print("📥 Installing WhatsApp bridge dependencies...")

    try:
        # Install npm dependencies
        subprocess.run(
            ["npm", "install", "whatsapp-web.js", "qrcode-terminal", "express", "dotenv"],
            cwd=str(bridge_dir),
            check=True,
        )
        print("✅ WhatsApp bridge installed successfully")
        print("\n📱 To connect WhatsApp:")
        print("   1. Run: cd whatsapp-bridge && node bridge.js")
        print("   2. Scan QR code with WhatsApp")
        print("   3. Start OpenSable with WHATSAPP_ENABLED=true")
    except subprocess.CalledProcessError:
        print("⚠️  WhatsApp bridge installation failed - install manually")
    except FileNotFoundError:
        print("❌ npm not found - install Node.js and npm first")


def setup_directories():
    """Create necessary directories"""
    print("\n📁 Setting up directories...")

    dirs = ["data", "logs", "config"]
    for dir_name in dirs:
        Path(dir_name).mkdir(exist_ok=True)

    print("✅ Directories created")


def setup_env_file():
    """Create .env file from example"""
    env_file = Path(".env")
    env_example = Path(".env.example")

    if env_file.exists():
        print("\n✅ .env file already exists")
        return

    if env_example.exists():
        print("\n⚙️  Setting up configuration...")

        # Copy example
        import shutil

        shutil.copy(env_example, env_file)

        print("✅ Created .env file from template")
        print("\n⚠️  IMPORTANT: Edit .env file to add your bot tokens:")
        print("   - TELEGRAM_BOT_TOKEN (get from @BotFather on Telegram)")
        print("   - DISCORD_BOT_TOKEN (get from Discord Developer Portal)")
    else:
        print("⚠️  .env.example not found")


def detect_hardware():
    """Detect system hardware specs"""
    import psutil

    ram_gb = psutil.virtual_memory().total / (1024**3)
    cpu_cores = psutil.cpu_count(logical=True)

    # Try to detect GPU
    gpu_mem_gb = 0
    has_gpu = False
    try:
        import subprocess

        result = subprocess.run(
            ["nvidia-smi", "--query-gpu=memory.total", "--format=csv,noheader,nounits"],
            capture_output=True,
            text=True,
        )
        if result.returncode == 0:
            gpu_mem_mb = int(result.stdout.strip().split("\n")[0])
            gpu_mem_gb = gpu_mem_mb / 1024
            has_gpu = True
    except:
        pass

    return {"ram_gb": ram_gb, "cpu_cores": cpu_cores, "gpu_mem_gb": gpu_mem_gb, "has_gpu": has_gpu}


def get_model_recommendations(specs):
    """Get model recommendations based on hardware"""
    models = []

    if specs["has_gpu"] and specs["gpu_mem_gb"] >= 20:
        models = [
            ("llama3.1:70b", "24GB VRAM - Best quality for high-end GPU"),
            ("llama3.1:8b", "5GB VRAM - Fast and reliable"),
            ("qwen2.5:7b", "4GB VRAM - Good reasoning"),
            ("llama3.2:3b", "2GB VRAM - Efficient"),
            ("gemma2:9b", "6GB VRAM - Fast reasoning"),
        ]
    elif specs["has_gpu"] and specs["gpu_mem_gb"] >= 8:
        models = [
            ("llama3.1:8b", "5GB VRAM - Balanced GPU performance"),
            ("qwen2.5:7b", "4GB VRAM - Good reasoning"),
            ("gemma2:9b", "6GB VRAM - Fast reasoning"),
            ("llama3.2:3b", "2GB VRAM - Efficient"),
            ("phi3:14b", "8GB VRAM - Advanced reasoning"),
        ]
    elif specs["ram_gb"] >= 32:
        models = [
            ("llama3.1:8b", "5GB RAM - Balanced"),
            ("qwen2.5:7b", "4GB RAM - Good reasoning"),
            ("gemma2:9b", "6GB RAM - Fast"),
            ("llama3.2:3b", "2GB RAM - Efficient"),
            ("phi3:14b", "8GB RAM - Advanced"),
        ]
    elif specs["ram_gb"] >= 8:
        models = [
            ("llama3.2:3b", "2GB RAM - Fast and capable"),
            ("gemma2:2b", "2GB RAM - Efficient"),
            ("qwen2.5:3b", "2GB RAM - Good reasoning"),
            ("phi3:3.8b", "3GB RAM - Compact"),
            ("llama3.2:1b", "1GB RAM - Ultra fast"),
        ]
    else:
        models = [
            ("llama3.2:1b", "1GB RAM - Ultra efficient"),
            ("qwen2.5:0.5b", "500MB RAM - Minimal"),
            ("gemma2:2b", "2GB RAM - Balanced"),
        ]

    return models


def pull_ollama_model():
    """Pull optimal Ollama model based on system"""
    print("\n🤖 Detecting system for optimal model selection...")

    try:
        specs = detect_hardware()
        print(f"\n   RAM: {specs['ram_gb']:.1f}GB | CPU Cores: {specs['cpu_cores']}")
        if specs["has_gpu"]:
            print(f"   GPU: NVIDIA with {specs['gpu_mem_gb']:.1f}GB VRAM")
        else:
            print("   GPU: None detected (CPU only)")

        models = get_model_recommendations(specs)

        # Auto-select optimal model (first in list)
        selected_model, desc = models[0]
        print(f"\n   🚀 Auto-selected: {selected_model} - {desc}")
        print("   📦 Agent will auto-download additional models as needed during runtime")

        # Check if already installed
        result = subprocess.run(["ollama", "list"], capture_output=True, text=True)

        if selected_model in result.stdout:
            print(f"✅ {selected_model} already installed")
        else:
            print(f"\n📥 Downloading {selected_model} (this may take a while)...")
            subprocess.run(["ollama", "pull", selected_model], check=True)
            print("✅ Model downloaded")

        # Update .env with selected model
        env_file = Path(".env")
        if env_file.exists():
            content = env_file.read_text()
            import re

            content = re.sub(r"DEFAULT_MODEL=.*", f"DEFAULT_MODEL={selected_model}", content)
            env_file.write_text(content)
            print(f"✅ Updated .env with model: {selected_model}")

        return True

    except (FileNotFoundError, subprocess.CalledProcessError) as e:
        print(f"⚠️  Could not pull Ollama model: {e}")
        return False


def print_next_steps():
    """Print what to do next"""
    os_type = platform.system()

    if os_type == "Windows":
        activate_cmd = "venv\\Scripts\\activate"
        run_cmd = "python -m opensable"
    else:
        activate_cmd = "source venv/bin/activate"
        run_cmd = "python -m opensable"

    print(f"""
╔═══════════════════════════════════════════════════════════╗
║                                                           ║
║   ✅ Installation Complete!                               ║
║                                                           ║
╚═══════════════════════════════════════════════════════════╝

📝 Next Steps:

1. Activate virtual environment:
   {activate_cmd}

2. Edit .env file with your bot token:
   - Get token from @BotFather on Telegram
   - Set: TELEGRAM_BOT_TOKEN=your_token_here

3. Start Open-Sable (recommended — runs in background with logging):
   ./start.sh start

   Or run directly in the foreground:
   {run_cmd}

   Useful commands:
   ./start.sh status    — Check if agent is running
   ./start.sh logs      — Follow live logs
   ./start.sh stop      — Stop the agent
   ./start.sh restart   — Restart the agent

📚 Documentation:
   - README.md - Feature overview & architecture
   - INSTALL.md - Detailed installation guide
   - docs/ - API reference, guides, security

🐛 Issues? https://github.com/IdeoaLabs/Open-Sable/issues

🎉 Enjoy your AI agent!
""")


def install_extras():
    """Ask user if they want extra features"""
    print("\n🎨 Optional Features:")
    print("   [1] Core only (minimal)")
    print("   [2] Core + Voice (speech-to-text, text-to-speech)")
    print("   [3] Core + Vision (image recognition, OCR)")
    print("   [4] All features (voice, vision, automation, monitoring)")

    choice = input("\n   Select option [1-4] (default: 1): ").strip() or "1"

    extras_map = {
        "1": "",
        "2": "[voice]",
        "3": "[vision]",
        "4": "[voice,vision,automation,database,monitoring]",
    }

    extras = extras_map.get(choice, "")

    if extras:
        print(f"\n📦 Installing extra features: {extras}...")
        venv_python = get_venv_python()
        try:
            subprocess.run(
                [str(venv_python), "-m", "pip", "install", "-e", f".{extras}"], check=True
            )
            print("✅ Extra features installed")
        except subprocess.CalledProcessError:
            print("⚠️  Some extras failed to install (you can install later)")


def main():
    """Main installation flow"""
    print_banner()

    # Check requirements
    check_python_version()

    # Create venv
    if not create_venv():
        print("\n❌ Installation failed: Could not create virtual environment")
        sys.exit(1)

    # Setup directories
    setup_directories()

    # Install dependencies
    if not install_dependencies():
        print("\n❌ Installation failed at dependencies")
        sys.exit(1)

    # Ask for extras
    install_extras()

    # Setup config
    setup_env_file()

    # Install Ollama automatically
    ollama_installed = install_ollama()
    if ollama_installed:
        pull_ollama_model()
    else:
        print("\n⚠️  Skipping model download - install Ollama manually later")

    # Optional playwright
    install_playwright()

    # Install Aggr.trade charts
    install_aggr()

    # Install React Dashboard
    install_dashboard()

    # Install Skills Marketplace
    install_marketplace()

    # Install Desktop Agent (optional)
    print("\n🖥️  Install Desktop Agent (Electron app)? (y/n): ", end="")
    if input().strip().lower() in ("y", "yes", ""):
        install_desktop()

    # Install Dev Studio (optional)
    print("\n🛠️  Install Dev Studio (AI app builder)? (y/n): ", end="")
    if input().strip().lower() in ("y", "yes", ""):
        install_dev_studio()

    # Install WhatsApp bridge
    install_whatsapp_bridge()

    # Done
    print_next_steps()


if __name__ == "__main__":
    main()

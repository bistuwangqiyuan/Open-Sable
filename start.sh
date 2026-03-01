#!/bin/bash
# Open-Sable — start / stop / status (all agents live in agents/)
# Usage:
#   ./start.sh                         → start default agent (sable)
#   ./start.sh stop                    → stop default agent (sable)
#   ./start.sh restart                 → restart default agent
#   ./start.sh status                  → check if running
#   ./start.sh logs                    → tail live logs
#   ./start.sh start --profile NAME    → start a named profile agent
#   ./start.sh stop --profile NAME     → stop a named profile agent
#   ./start.sh restart --profile NAME  → restart a named profile agent
#   ./start.sh status --profile NAME   → check if profile is running
#   ./start.sh logs --profile NAME     → tail profile logs
#   ./start.sh profiles               → list available profiles
#   ./start.sh restart --all           → restart ALL agent profiles
#   ./start.sh stop --all              → stop ALL agent profiles
#   ./start.sh start --all             → start ALL agent profiles

DIR="$(cd "$(dirname "$0")" && pwd)"

# Default profile — all agents live in agents/
DEFAULT_PROFILE="sable"

# Parse --profile and --all flags from any position
PROFILE=""
ACTION=""
ALL_PROFILES=0
for arg in "$@"; do
    if [[ "$arg" == "--profile" ]]; then
        NEXT_IS_PROFILE=1
        continue
    fi
    if [[ "$NEXT_IS_PROFILE" == "1" ]]; then
        PROFILE="$arg"
        NEXT_IS_PROFILE=0
        continue
    fi
    if [[ "$arg" == "--all" ]]; then
        ALL_PROFILES=1
        continue
    fi
    if [[ -z "$ACTION" ]]; then
        ACTION="$arg"
    fi
done
ACTION="${ACTION:-start}"

# If no profile specified, use default
PROFILE="${PROFILE:-$DEFAULT_PROFILE}"

# Set file paths based on profile
PIDFILE="$DIR/.sable-${PROFILE}.pid"
LOGFILE="$DIR/logs/sable-${PROFILE}.log"
PROFILE_DIR="$DIR/agents/$PROFILE"

cd "$DIR"

# Check venv
if [ ! -d "venv" ]; then
    echo "❌ Virtual environment not found. Run: python install.py"
    exit 1
fi
source venv/bin/activate

is_running() {
    if [ -f "$PIDFILE" ]; then
        pid=$(cat "$PIDFILE")
        if kill -0 "$pid" 2>/dev/null; then
            return 0
        fi
        rm -f "$PIDFILE"
    fi
    return 1
}

ensure_aggr() {
    # Auto-install Aggr.trade if not built yet
    local aggrdir="$DIR/aggr"
    if [ -f "$aggrdir/dist/index.html" ]; then
        return 0
    fi
    if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
        echo "⏭️  Aggr.trade skipped (Node.js not found)"
        return 0
    fi
    echo "📈 Installing Aggr.trade charts..."
    if [ ! -d "$aggrdir" ]; then
        git clone --depth=1 https://github.com/Tucsky/aggr.git "$aggrdir" || return 0
    fi
    if [ ! -d "$aggrdir/templates" ]; then
        git clone --depth=1 https://github.com/0xd3lbow/aggr.template.git "$aggrdir/templates" 2>/dev/null
    fi
    # Create .env.local with production CORS proxy
    if [ ! -f "$aggrdir/.env.local" ]; then
        cat > "$aggrdir/.env.local" << 'AGGRENV'
VITE_APP_PROXY_URL=https://cors.aggr.trade/
VITE_APP_API_URL=https://api.aggr.trade/
VITE_APP_LIB_URL=https://lib.aggr.trade/
VITE_APP_LIB_REPO_URL=https://github.com/Tucsky/aggr-lib
VITE_APP_BASE_PATH=/aggr/
VITE_APP_API_SUPPORTED_TIMEFRAMES=5,10,15,30,60,180,300,900,1260,1800,3600,7200,14400,21600,28800,43200,86400
AGGRENV
    fi
    (cd "$aggrdir" && npm install && npx vite build --base /aggr/) || {
        echo "⚠️  Aggr.trade build failed — continuing without it"
        return 0
    }
    # Strip tracking (GTM, analytics, etc)
    patch_aggr_tracking "$aggrdir"
    [ -f "$aggrdir/dist/index.html" ] && echo "✅ Aggr.trade ready" || echo "⚠️  Aggr.trade dist not found"
}

patch_aggr_tracking() {
    local dir="$1"
    for f in "$dir/index.html" "$dir/dist/index.html"; do
        [ -f "$f" ] || continue
        # Remove GTM script block
        sed -i '/<!-- Google Tag Manager -->/,/<!-- End Google Tag Manager -->/d' "$f"
        # Remove GTM noscript block
        sed -i '/<!-- Google Tag Manager (noscript) -->/,/<!-- End Google Tag Manager (noscript) -->/d' "$f"
        # Remove any remaining GTM iframes/scripts
        sed -i '/googletagmanager/d' "$f"
        # Remove google-analytics
        sed -i '/google-analytics/d' "$f"
        # Fix base href for /aggr/ subpath
        sed -i 's|<base href="/" />|<base href="/aggr/" />|g' "$f"
    done
    echo "   \U0001f6e1  Tracking stripped + base href fixed"
}

ensure_dashboard() {
    # Auto-build React dashboard if not built yet
    local dashdir="$DIR/dashboard"
    if [ -f "$dashdir/dist/index.html" ]; then
        return 0
    fi
    if [ ! -f "$dashdir/package.json" ]; then
        echo "⏭️  Dashboard skipped (folder not found)"
        return 0
    fi
    if ! command -v node &>/dev/null || ! command -v npm &>/dev/null; then
        echo "⏭️  Dashboard skipped (Node.js not found)"
        return 0
    fi
    echo "📊 Building React Dashboard..."
    (cd "$dashdir" && npm install && npm run build) || {
        echo "⚠️  Dashboard build failed — continuing without it"
        return 0
    }
    [ -f "$dashdir/dist/index.html" ] && echo "✅ Dashboard ready" || echo "⚠️  Dashboard dist not found"
}

ensure_marketplace() {
    # Auto-install marketplace server deps if needed
    local srvdir="$DIR/marketplace/server"
    local clidir="$DIR/marketplace/client"
    if [ ! -f "$srvdir/package.json" ]; then
        return 0
    fi
    if ! command -v node &>/dev/null; then
        return 0
    fi
    # Install server deps if node_modules missing
    if [ ! -d "$srvdir/node_modules" ]; then
        echo "🏪 Installing Marketplace server..."
        (cd "$srvdir" && npm install) || echo "⚠️  Marketplace server install failed"
    fi
    # Build client if not built
    if [ -f "$clidir/package.json" ] && [ ! -f "$clidir/build/index.html" ]; then
        echo "🏪 Building Marketplace client..."
        (cd "$clidir" && npm install && npm run build) || echo "⚠️  Marketplace client build failed"
    fi
}

start_desktop() {
    # Start the Sable Desktop Electron app if DESKTOP_ENABLED=true
    local desktop_enabled
    desktop_enabled=$(grep -E '^DESKTOP_ENABLED=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    if [ "$desktop_enabled" != "true" ]; then
        return 0
    fi

    local deskdir="$DIR/desktop"
    if [ ! -f "$deskdir/package.json" ]; then
        echo "⚠️  Desktop folder not found — set DESKTOP_ENABLED=false"
        return 0
    fi

    if ! command -v npm &>/dev/null; then
        echo "⚠️  npm not found — desktop requires Node.js"
        return 0
    fi

    if ! command -v electron &>/dev/null && [ ! -f "$deskdir/node_modules/.bin/electron" ]; then
        echo "🖥️  Installing Desktop dependencies..."
        (cd "$deskdir" && npm install --silent) || {
            echo "⚠️  Desktop npm install failed — skipping"
            return 0
        }
    fi

    # Auto-build renderer if not built
    if [ ! -f "$deskdir/dist/index.html" ]; then
        echo "🖥️  Building Desktop..."
        (cd "$deskdir" && npm run build) || {
            echo "⚠️  Desktop build failed — skipping"
            return 0
        }
    fi

    # Read gateway config
    local webchat_port webchat_host webchat_token
    webchat_port=$(grep -E '^WEBCHAT_PORT=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    webchat_host=$(grep -E '^WEBCHAT_HOST=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    webchat_token=$(grep -E '^WEBCHAT_TOKEN=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')

    echo "🖥️  Starting Desktop..."
    WEBCHAT_PORT="${webchat_port:-8789}" \
    WEBCHAT_HOST="${webchat_host:-localhost}" \
    WEBCHAT_TOKEN="${webchat_token}" \
    nohup "$deskdir/node_modules/.bin/electron" "$deskdir" >> "$DIR/logs/desktop.log" 2>&1 &
    echo $! > "$DIR/.desktop.pid"
    echo "✅ Desktop started (PID $(cat "$DIR/.desktop.pid"))"
}

stop_desktop() {
    local pidfile="$DIR/.desktop.pid"
    if [ -f "$pidfile" ]; then
        local pid
        pid=$(cat "$pidfile")
        if kill -0 "$pid" 2>/dev/null; then
            echo "🛑 Stopping Desktop Agent (PID $pid)..."
            kill "$pid" 2>/dev/null
            sleep 2
            kill -0 "$pid" 2>/dev/null && kill -9 "$pid" 2>/dev/null
        fi
        rm -f "$pidfile"
    fi
}

do_start() {
    if is_running; then
        echo "⚠️  Already running [$PROFILE] (PID $(cat "$PIDFILE"))"
        echo "   Use: ./start.sh stop --profile $PROFILE   or   ./start.sh restart --profile $PROFILE"
        exit 1
    fi

    # Validate profile directory exists
    if [[ ! -d "$PROFILE_DIR" ]]; then
        echo "❌ Profile '$PROFILE' not found at $PROFILE_DIR"
        echo "   Available profiles:"
        ls -1 "$DIR/agents/" 2>/dev/null | grep -v '^_' | grep -v '^\.' | sed 's/^/     /'
        echo ""
        echo "   Create one: cp -r agents/_template agents/$PROFILE"
        exit 1
    fi

    echo "👤 Profile: $PROFILE"

    # Ensure aggr/dashboard/marketplace are installed (only for primary agent)
    if [[ "$PROFILE" == "$DEFAULT_PROFILE" ]]; then
        ensure_aggr
        ensure_dashboard
        ensure_marketplace
    fi

    mkdir -p "$DIR/logs"
    echo "🚀 Starting Open-Sable [profile: $PROFILE]..."
    SABLE_PROFILE="$PROFILE" nohup python -m opensable --profile "$PROFILE" >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1

    if is_running; then
        echo "✅ Running (PID $(cat "$PIDFILE"))"
        echo "   Logs: ./start.sh logs --profile $PROFILE"
        echo "   Stop: ./start.sh stop --profile $PROFILE"

        # Start desktop agent if enabled (only for primary agent)
        if [[ "$PROFILE" == "$DEFAULT_PROFILE" ]]; then
            start_desktop
        fi
    else
        echo "❌ Failed to start. Check: tail -50 $LOGFILE"
        rm -f "$PIDFILE"
        exit 1
    fi
}

do_stop() {
    # Stop desktop agent (only for primary agent)
    if [[ "$PROFILE" == "$DEFAULT_PROFILE" ]]; then
        stop_desktop
    fi

    if ! is_running; then
        echo "ℹ️  Not running [$PROFILE]"
        return
    fi
    pid=$(cat "$PIDFILE")
    echo "🛑 Stopping [$PROFILE] (PID $pid)..."
    kill "$pid" 2>/dev/null
    # Wait up to 10s for graceful shutdown
    for i in $(seq 1 10); do
        if ! kill -0 "$pid" 2>/dev/null; then
            break
        fi
        sleep 1
    done
    # Force kill if still alive
    if kill -0 "$pid" 2>/dev/null; then
        echo "   Force killing..."
        kill -9 "$pid" 2>/dev/null
    fi
    rm -f "$PIDFILE"
    echo "✅ Stopped"
}

do_status() {
    if is_running; then
        pid=$(cat "$PIDFILE")
        uptime=$(ps -p "$pid" -o etime= 2>/dev/null | xargs)
        mem=$(ps -p "$pid" -o rss= 2>/dev/null | awk '{printf "%.0f", $1/1024}')
        echo "✅ Running [$PROFILE] (PID $pid, uptime: $uptime, mem: ${mem}MB)"
    else
        echo "⏹️  Not running [$PROFILE]"
    fi
}

do_list_profiles() {
    echo "📂 Agent profiles (agents/):"
    echo ""
    if [ -d "$DIR/agents" ]; then
        for d in "$DIR/agents"/*/; do
            name=$(basename "$d")
            [[ "$name" == _* ]] && continue
            [[ "$name" == .* ]] && continue
            soul="❌"
            [[ -f "$d/soul.md" ]] && soul="✅"
            env_count=$(grep -c '^[A-Z]' "$d/profile.env" 2>/dev/null || echo "0")
            tools_mode=$(python3 -c "import json; d=json.load(open('$d/tools.json')); print(d.get('mode','all'))" 2>/dev/null || echo "all")
            # Check if running
            pid_file="$DIR/.sable-${name}.pid"
            status="⏹️"
            if [ -f "$pid_file" ] && kill -0 "$(cat "$pid_file")" 2>/dev/null; then
                status="🟢"
            fi
            default_tag=""
            [[ "$name" == "$DEFAULT_PROFILE" ]] && default_tag=" (default)"
            echo "  $status $name$default_tag  — soul: $soul, env: ${env_count} vars, tools: $tools_mode"
        done
    else
        echo "  (none — create with: cp -r agents/_template agents/my_agent)"
    fi
    echo ""
}

# Helper: get list of all profile names (excluding _template)
get_all_profiles() {
    local profiles_dir="$DIR/agents"
    if [ -d "$profiles_dir" ]; then
        for d in "$profiles_dir"/*/; do
            local name=$(basename "$d")
            [[ "$name" == _* ]] && continue
            echo "$name"
        done
    fi
}

# Helper: run action for a single profile
run_for_profile() {
    local prof="$1"
    PROFILE="$prof"
    PIDFILE="$DIR/.sable-${PROFILE}.pid"
    LOGFILE="$DIR/logs/sable-${PROFILE}.log"
    PROFILE_DIR="$DIR/agents/$PROFILE"
}

case "$ACTION" in
    start)
        if [[ "$ALL_PROFILES" == "1" ]]; then
            echo "🚀 Starting ALL agents..."
            for p in $(get_all_profiles); do
                run_for_profile "$p"
                echo "── $p ──"
                do_start
            done
        else
            do_start
        fi
        ;;
    stop)
        if [[ "$ALL_PROFILES" == "1" ]]; then
            echo "⏹️  Stopping ALL agents..."
            for p in $(get_all_profiles); do
                run_for_profile "$p"
                echo "── $p ──"
                do_stop
            done
        else
            do_stop
        fi
        ;;
    restart)
        if [[ "$ALL_PROFILES" == "1" ]]; then
            echo "🔄 Restarting ALL agents..."
            for p in $(get_all_profiles); do
                run_for_profile "$p"
                echo "── stopping $p ──"
                do_stop
            done
            sleep 2
            for p in $(get_all_profiles); do
                run_for_profile "$p"
                echo "── starting $p ──"
                do_start
            done
        else
            do_stop
            sleep 2
            do_start
        fi
        ;;
    status)
        do_status
        ;;
    profiles|list)
        do_list_profiles
        ;;
    logs)
        if [ -f "$LOGFILE" ]; then
            tail -f "$LOGFILE"
        else
            echo "No log file yet for profile $PROFILE"
        fi
        ;;
    *)
        echo "Usage: ./start.sh [start|stop|restart|status|logs|profiles] [--profile NAME] [--all]"
        echo ""
        echo "Commands:"
        echo "  start              Start the agent (default: $DEFAULT_PROFILE)"
        echo "  stop               Stop the agent"
        echo "  restart            Restart the agent"
        echo "  status             Check if the agent is running"
        echo "  logs               Tail live logs"
        echo "  profiles           List all agent profiles"
        echo ""
        echo "Options:"
        echo "  --profile NAME     Target a specific agent profile (from agents/)"
        echo "  --all              Apply command to ALL agent profiles"
        echo ""
        echo "Examples:"
        echo "  ./start.sh restart --all          Restart every agent"
        echo "  ./start.sh stop --all             Stop every agent"
        echo "  ./start.sh start --profile analyst  Start just the analyst"
        echo ""
        echo "All agents live in agents/<name>/ with their own soul.md, profile.env, tools.json, and data/"
        ;;
esac

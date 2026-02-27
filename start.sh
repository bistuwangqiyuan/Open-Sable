#!/bin/bash
# Open-Sable — start / stop / status
# Usage:
#   ./start.sh          → start agent
#   ./start.sh stop     → stop agent
#   ./start.sh restart  → restart agent
#   ./start.sh status   → check if running
#   ./start.sh logs     → tail live logs

DIR="$(cd "$(dirname "$0")" && pwd)"
PIDFILE="$DIR/.sable.pid"
LOGFILE="$DIR/logs/sable.log"

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
    # Start the desktop Electron agent if DESKTOP_ENABLED=true
    local desktop_enabled
    desktop_enabled=$(grep -E '^DESKTOP_ENABLED=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]' | tr '[:upper:]' '[:lower:]')
    if [ "$desktop_enabled" != "true" ]; then
        return 0
    fi

    local deskdir="$DIR/desktop"
    if [ ! -f "$deskdir/package.json" ]; then
        echo "⚠️  Desktop agent folder not found — set DESKTOP_ENABLED=false or run install.py"
        return 0
    fi

    if ! command -v pnpm &>/dev/null; then
        echo "⚠️  pnpm not found — desktop agent requires pnpm"
        return 0
    fi

    # Auto-build if not built
    local dist_electron="$deskdir/apps/desktop/dist-electron"
    if [ ! -d "$dist_electron" ] || [ -z "$(ls -A "$dist_electron/main/" 2>/dev/null)" ]; then
        echo "🖥️  Building Desktop Agent..."
        (cd "$deskdir" && COREPACK_ENABLE_STRICT=0 pnpm install --no-frozen-lockfile && \
         pnpm -F @opensable/web build && \
         cd apps/desktop && npx tsc && npx vite build) || {
            echo "⚠️  Desktop agent build failed — skipping"
            return 0
        }
    fi

    # Read gateway config for the desktop app
    local api_url
    api_url=$(grep -E '^OPENSABLE_API_URL=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')
    local sable_token
    sable_token=$(grep -E '^WEBCHAT_TOKEN=' "$DIR/.env" 2>/dev/null | cut -d= -f2 | tr -d '[:space:]')

    echo "🖥️  Starting Desktop Agent..."
    OPENSABLE_API_URL="${api_url:-ws://127.0.0.1:8789}" \
    SABLE_TOKEN="${sable_token}" \
    nohup pnpm --dir "$deskdir" dev >> "$DIR/logs/desktop.log" 2>&1 &
    echo $! > "$DIR/.desktop.pid"
    echo "✅ Desktop Agent started (PID $(cat "$DIR/.desktop.pid"))"
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
        echo "⚠️  Already running (PID $(cat "$PIDFILE"))"
        echo "   Use: ./start.sh stop   or   ./start.sh restart"
        exit 1
    fi

    # Ensure aggr is installed
    ensure_aggr

    # Ensure React dashboard is built
    ensure_dashboard

    # Ensure marketplace is ready
    ensure_marketplace

    mkdir -p "$DIR/logs"
    echo "🚀 Starting Open-Sable..."
    nohup python -m opensable >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1

    if is_running; then
        echo "✅ Running (PID $(cat "$PIDFILE"))"
        echo "   Logs: ./start.sh logs"
        echo "   Stop: ./start.sh stop"

        # Start desktop agent if enabled
        start_desktop
    else
        echo "❌ Failed to start. Check: tail -50 $LOGFILE"
        rm -f "$PIDFILE"
        exit 1
    fi
}

do_stop() {
    # Stop desktop agent first
    stop_desktop

    if ! is_running; then
        echo "ℹ️  Not running"
        return
    fi
    pid=$(cat "$PIDFILE")
    echo "🛑 Stopping (PID $pid)..."
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
        echo "✅ Running (PID $pid, uptime: $uptime, mem: ${mem}MB)"
    else
        echo "⏹️  Not running"
    fi
}

case "${1:-start}" in
    start)
        do_start
        ;;
    stop)
        do_stop
        ;;
    restart)
        do_stop
        sleep 2
        do_start
        ;;
    status)
        do_status
        ;;
    logs)
        if [ -f "$LOGFILE" ]; then
            tail -f "$LOGFILE"
        else
            echo "No log file yet"
        fi
        ;;
    *)
        echo "Usage: ./start.sh [start|stop|restart|status|logs]"
        ;;
esac

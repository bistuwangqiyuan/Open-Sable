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

do_start() {
    if is_running; then
        echo "⚠️  Already running (PID $(cat "$PIDFILE"))"
        echo "   Use: ./start.sh stop   or   ./start.sh restart"
        exit 1
    fi

    mkdir -p "$DIR/logs"
    echo "🚀 Starting Open-Sable..."
    nohup python -m opensable >> "$LOGFILE" 2>&1 &
    echo $! > "$PIDFILE"
    sleep 1

    if is_running; then
        echo "✅ Running (PID $(cat "$PIDFILE"))"
        echo "   Logs: ./start.sh logs"
        echo "   Stop: ./start.sh stop"
    else
        echo "❌ Failed to start. Check: tail -50 $LOGFILE"
        rm -f "$PIDFILE"
        exit 1
    fi
}

do_stop() {
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

#!/bin/bash
# ProMo suite development control script
#
# Usage:
#   ./dev.sh start [service]      — start one or all services
#   ./dev.sh stop [service]       — stop one or all services
#   ./dev.sh restart [service]    — stop then start
#   ./dev.sh status               — show what is running
#   ./dev.sh wipe                 — delete all data files (ontology.trig etc.)
#   ./dev.sh wipe-restart         — wipe data then restart backend
#   ./dev.sh logs [service]       — tail the log file for a service
#
# Services: backend | ontology | equation | modeller | all (default)
#
# Log files are written to /tmp/promo-*.log

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${PROMO_DATA_DIR:-$REPO/data}"

BACKEND_PORT=8000
ONTOLOGY_PORT=3001
EQUATION_PORT=3002
BEHAVIOUR_PORT=3003
MODELLER_PORT=3004

LOG_DIR="$REPO/logs"
mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
ONTOLOGY_LOG="$LOG_DIR/ontology.log"
EQUATION_LOG="$LOG_DIR/equation.log"
BEHAVIOUR_LOG="$LOG_DIR/behaviour.log"
MODELLER_LOG="$LOG_DIR/modeller.log"

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

_pid_on_port() {
    lsof -ti tcp:"$1" 2>/dev/null || true
}

_is_running() {
    local pid
    pid=$(_pid_on_port "$1")
    [ -n "$pid" ]
}

_status_line() {
    local name="$1" port="$2" url="$3"
    if _is_running "$port"; then
        printf "  %-20s \033[32mRUNNING\033[0m  port %-5s  %s\n" "$name" "$port" "$url"
    else
        printf "  %-20s \033[31mSTOPPED\033[0m  port %-5s\n" "$name" "$port"
    fi
}

_kill_port() {
    local port="$1" name="$2" quiet="${3:-}"
    local pid
    pid=$(_pid_on_port "$port")
    if [ -n "$pid" ]; then
        echo "  Stopping $name (pid $pid)..."
        # unquoted: lsof may return several PIDs (wrapper + child)
        kill $pid 2>/dev/null || true
        sleep 0.5
    elif [ -z "$quiet" ]; then
        echo "  $name not running."
    fi
}

_warn_unsaved() {
    # Stopping/restarting the backend discards unsaved in-memory
    # triples — warn when the store is dirty.
    local status
    status=$(curl -s -m 2 "http://localhost:$BACKEND_PORT/api/ontology/status" 2>/dev/null || true)
    if echo "$status" | grep -q '"dirty"[[:space:]]*:[[:space:]]*true'; then
        echo "  WARNING: backend has UNSAVED ontology changes — they will be lost."
        echo "           Save first (editor Save button or POST /api/ontology/save)."
    fi
}

# ---------------------------------------------------------------------------
# Start helpers
# ---------------------------------------------------------------------------

_start_backend() {
    # Fresh start: kill any older instance first — guarded, since a
    # running backend may hold unsaved in-memory triples.
    _warn_unsaved
    _kill_port $BACKEND_PORT "backend" quiet
    echo "  Starting backend on :$BACKEND_PORT  (log: $BACKEND_LOG)"
    cd "$REPO"
    nohup uv run uvicorn backend.main:app --port $BACKEND_PORT --reload \
        > "$BACKEND_LOG" 2>&1 &
    sleep 1
    if _is_running $BACKEND_PORT; then
        echo "  Backend started."
    else
        echo "  Backend failed to start — check $BACKEND_LOG"
    fi
}

_ensure_backend() {
    # Dependency for app starts: bring the backend up if down, but
    # never bounce a running one (unsaved store would be lost).
    if ! _is_running $BACKEND_PORT; then
        _start_backend
    fi
}

_start_ontology() {
    _kill_port $ONTOLOGY_PORT "ontology-editor" quiet
    echo "  Starting ontology editor on :$ONTOLOGY_PORT  (log: $ONTOLOGY_LOG)"
    cd "$REPO"
    nohup npm run dev -w @promo/ontology-editor \
        > "$ONTOLOGY_LOG" 2>&1 &
    sleep 3
    if _is_running $ONTOLOGY_PORT; then
        echo "  Ontology editor started  →  http://localhost:$ONTOLOGY_PORT/ontology/"
    else
        echo "  Ontology editor failed — check $ONTOLOGY_LOG"
    fi
}

_start_equation() {
    _kill_port $EQUATION_PORT "equation-editor" quiet
    echo "  Starting equation editor on :$EQUATION_PORT  (log: $EQUATION_LOG)"
    cd "$REPO"
    nohup npm run dev:equation \
        > "$EQUATION_LOG" 2>&1 &
    sleep 3
    if _is_running $EQUATION_PORT; then
        echo "  Equation editor started  →  http://localhost:$EQUATION_PORT"
    else
        echo "  Equation editor failed — check $EQUATION_LOG"
    fi
}

_start_modeller() {
    _kill_port $MODELLER_PORT "modeller" quiet
    echo "  Starting modeller on :$MODELLER_PORT  (log: $MODELLER_LOG)"
    cd "$REPO"
    nohup npm run dev \
        > "$MODELLER_LOG" 2>&1 &
    sleep 3
    if _is_running $MODELLER_PORT; then
        echo "  Modeller started  →  http://localhost:$MODELLER_PORT"
    else
        echo "  Modeller failed — check $MODELLER_LOG"
    fi
}

# ---------------------------------------------------------------------------
# Commands
# ---------------------------------------------------------------------------

cmd_status() {
    echo ""
    echo "ProMo suite status:"
    _status_line "backend"          $BACKEND_PORT   "http://localhost:$BACKEND_PORT/api/health"
    _status_line "hub (entry point)" $BACKEND_PORT  "http://localhost:$BACKEND_PORT/"
    _status_line "ontology-editor"  $ONTOLOGY_PORT  "http://localhost:$ONTOLOGY_PORT/ontology/"
    _status_line "equation-editor"  $EQUATION_PORT  "http://localhost:$EQUATION_PORT"
    _status_line "behaviour-linker" $BEHAVIOUR_PORT "http://localhost:$BEHAVIOUR_PORT"
    _status_line "modeller"         $MODELLER_PORT  "http://localhost:$MODELLER_PORT"
    echo ""
    echo "  Data dir: $DATA_DIR"
    local trig_count
    trig_count=$(find "$DATA_DIR" -name "*.trig" 2>/dev/null | wc -l | tr -d ' ')
    echo "  Data files: $trig_count .trig file(s)"
    echo ""
}

cmd_start() {
    local service="${1:-all}"
    echo "Starting: $service"
    case "$service" in
        backend)  _start_backend ;;
        ontology) _ensure_backend; _start_ontology ;;
        equation) _ensure_backend; _start_equation ;;
        modeller) _ensure_backend; _start_modeller ;;
        all)
            _start_backend
            _start_ontology
            _start_equation
            _start_modeller
            ;;
        *) echo "Unknown service: $service"; exit 1 ;;
    esac
}

cmd_stop() {
    local service="${1:-all}"
    case "$service" in
        backend|all) _warn_unsaved ;;
    esac
    echo "Stopping: $service"
    case "$service" in
        backend)   _kill_port $BACKEND_PORT   "backend" ;;
        ontology)  _kill_port $ONTOLOGY_PORT  "ontology-editor" ;;
        equation)  _kill_port $EQUATION_PORT  "equation-editor" ;;
        behaviour) _kill_port $BEHAVIOUR_PORT "behaviour-linker" ;;
        modeller)  _kill_port $MODELLER_PORT  "modeller" ;;
        all)
            _kill_port $BACKEND_PORT   "backend"
            _kill_port $ONTOLOGY_PORT  "ontology-editor"
            _kill_port $EQUATION_PORT  "equation-editor"
            _kill_port $BEHAVIOUR_PORT "behaviour-linker"
            _kill_port $MODELLER_PORT  "modeller"
            ;;
        *) echo "Unknown service: $service"; exit 1 ;;
    esac
}

cmd_restart() {
    local service="${1:-all}"
    cmd_stop "$service"
    sleep 1
    cmd_start "$service"
}

cmd_wipe() {
    echo ""
    echo "  Data dir: $DATA_DIR"
    local files
    files=$(find "$DATA_DIR" -name "*.trig" -o -name "*.ttl" -o -name "*.jsonld" 2>/dev/null || true)
    if [ -z "$files" ]; then
        echo "  No data files to delete."
    else
        echo "  Deleting:"
        echo "$files" | while read -r f; do echo "    $f"; done
        echo "$files" | xargs rm -f
        echo "  Done. Backend will reseed on next start."
    fi
    echo ""
}

cmd_wipe_restart() {
    cmd_stop backend
    cmd_wipe
    sleep 1
    cmd_start backend
}

cmd_logs() {
    local service="${1:-backend}"
    case "$service" in
        backend)  tail -f "$BACKEND_LOG" ;;
        ontology)  tail -f "$ONTOLOGY_LOG" ;;
        equation)  tail -f "$EQUATION_LOG" ;;
        behaviour) tail -f "$BEHAVIOUR_LOG" ;;
        modeller)  tail -f "$MODELLER_LOG" ;;
        *) echo "Unknown service: $service"; exit 1 ;;
    esac
}

cmd_help() {
    echo ""
    echo "Usage: ./dev.sh <command> [service]"
    echo ""
    echo "Commands:"
    echo "  status              — show running services and data files"
    echo "  start   [service]   — start service(s)"
    echo "  stop    [service]   — stop service(s)"
    echo "  restart [service]   — restart service(s)"
    echo "  wipe                — delete all data files (backend reseeds on start)"
    echo "  wipe-restart        — wipe data + restart backend"
    echo "  logs    [service]   — tail log for a service"
    echo ""
    echo "Services: backend | ontology | equation | behaviour | modeller | all (default)"
    echo ""
    echo "URLs:"
    echo "  Hub (entry point)  http://localhost:$BACKEND_PORT/"
    echo "  Backend API        http://localhost:$BACKEND_PORT/api/health"
    echo "  Ontology Editor    http://localhost:$ONTOLOGY_PORT/ontology/"
    echo "  Equation Editor    http://localhost:$EQUATION_PORT"
    echo "  Behaviour Linker   http://localhost:$BEHAVIOUR_PORT"
    echo "  Modeller           http://localhost:$MODELLER_PORT"
    echo ""
}

# ---------------------------------------------------------------------------
# Dispatch
# ---------------------------------------------------------------------------

COMMAND="${1:-help}"
SERVICE="${2:-all}"

case "$COMMAND" in
    status)        cmd_status ;;
    start)         cmd_start "$SERVICE" ;;
    stop)          cmd_stop "$SERVICE" ;;
    restart)       cmd_restart "$SERVICE" ;;
    wipe)          cmd_wipe ;;
    wipe-restart)  cmd_wipe_restart ;;
    logs)          cmd_logs "$SERVICE" ;;
    help|--help|-h) cmd_help ;;
    *) echo "Unknown command: $COMMAND"; cmd_help; exit 1 ;;
esac

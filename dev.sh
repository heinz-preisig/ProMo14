#!/bin/bash
# ProMo suite development control script
#
# Usage:
#   ./dev.sh start [service]      — start one or all services
#   ./dev.sh stop [service]       — stop one or all services
#   ./dev.sh restart [service]    — stop then start
#   ./dev.sh status               — show what is running
#   ./dev.sh wipe                 — delete all data files (ontology.trig etc.)
#   ./dev.sh wipe-restart         — wipe data, reseed (seed + HAP ext), restart backend
#   ./dev.sh save                 — persist the in-memory store (one .trig per artefact line)
#   ./dev.sh sync                 — pick up the other machine: git pull + uv sync + npm install + build + start all
#   ./dev.sh build [service]      — rebuild the backend-served dist bundle(s) (dist/ is gitignored)
#   ./dev.sh logs [service]       — tail the log file for a service
#
# Services: backend | ontology | equation | behaviour | modeller | species | instantiation | all (default)
#
# Log files are written to logs/ in the repo root

set -euo pipefail

REPO="$(cd "$(dirname "$0")" && pwd)"
DATA_DIR="${PROMO_DATA_DIR:-$REPO/data}"

BACKEND_PORT=8000
ONTOLOGY_PORT=3001
EQUATION_PORT=3002
BEHAVIOUR_PORT=3003
MODELLER_PORT=3004
SPECIES_PORT=3005
INSTANTIATION_PORT=3006

LOG_DIR="$REPO/logs"
mkdir -p "$LOG_DIR"

BACKEND_LOG="$LOG_DIR/backend.log"
ONTOLOGY_LOG="$LOG_DIR/ontology.log"
EQUATION_LOG="$LOG_DIR/equation.log"
BEHAVIOUR_LOG="$LOG_DIR/behaviour.log"
MODELLER_LOG="$LOG_DIR/modeller.log"
SPECIES_LOG="$LOG_DIR/species.log"
INSTANTIATION_LOG="$LOG_DIR/instantiation.log"

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

_start_behaviour() {
    _kill_port $BEHAVIOUR_PORT "behaviour-linker" quiet
    echo "  Starting behaviour linker on :$BEHAVIOUR_PORT  (log: $BEHAVIOUR_LOG)"
    cd "$REPO"
    nohup npm run dev:behaviour \
        > "$BEHAVIOUR_LOG" 2>&1 &
    sleep 3
    if _is_running $BEHAVIOUR_PORT; then
        echo "  Behaviour linker started  →  http://localhost:$BEHAVIOUR_PORT"
    else
        echo "  Behaviour linker failed — check $BEHAVIOUR_LOG"
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

_start_species() {
    _kill_port $SPECIES_PORT "species" quiet
    echo "  Starting species editor on :$SPECIES_PORT  (log: $SPECIES_LOG)"
    cd "$REPO"
    nohup npm run dev:species \
        > "$SPECIES_LOG" 2>&1 &
    sleep 3
    if _is_running $SPECIES_PORT; then
        echo "  Species editor started  →  http://localhost:$SPECIES_PORT"
    else
        echo "  Species editor failed — check $SPECIES_LOG"
    fi
}

_start_instantiation() {
    _kill_port $INSTANTIATION_PORT "instantiation" quiet
    echo "  Starting instantiation app on :$INSTANTIATION_PORT  (log: $INSTANTIATION_LOG)"
    cd "$REPO"
    nohup npm run dev:instantiation \
        > "$INSTANTIATION_LOG" 2>&1 &
    sleep 3
    if _is_running $INSTANTIATION_PORT; then
        echo "  Instantiation app started  →  http://localhost:$INSTANTIATION_PORT"
    else
        echo "  Instantiation app failed — check $INSTANTIATION_LOG"
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
    _status_line "species"          $SPECIES_PORT   "http://localhost:$SPECIES_PORT"
    _status_line "instantiation"    $INSTANTIATION_PORT "http://localhost:$INSTANTIATION_PORT"
    echo ""
    echo "  Data dir: $DATA_DIR"
    local trig_count
    trig_count=$(find "$DATA_DIR" -name "*.trig" 2>/dev/null | wc -l | tr -d ' ')
    echo "  Data files: $trig_count .trig file(s)"

    if _is_running $BACKEND_PORT; then
        local status
        status=$(curl -s -m 2 "http://localhost:$BACKEND_PORT/api/ontology/status" 2>/dev/null || true)
        if echo "$status" | grep -q '"dirty"[[:space:]]*:[[:space:]]*true'; then
            echo "  Store: DIRTY — unsaved changes (run: ./dev.sh save)"
        else
            echo "  Store: clean"
        fi
        echo ""
        echo "  Artefact lines (hub: http://localhost:$BACKEND_PORT/):"
        curl -s -m 2 "http://localhost:$BACKEND_PORT/api/catalogue" | python3 -c '
import json, sys
try:
    d = json.load(sys.stdin)
except Exception:
    sys.exit(0)
for l in d.get("lines", []):
    vs = len(l.get("versions", []))
    pins = len(l.get("usesOntology", []))
    print("    %-20s %-10s %-7s %d version(s), %d pin(s)  %s" % (
        l.get("label") or "", l.get("type") or "",
        l.get("status") or "", vs, pins, l.get("iri") or ""))
' 2>/dev/null || true
    fi
    echo ""
}

cmd_start() {
    local service="${1:-all}"
    echo "Starting: $service"
    case "$service" in
        backend)  _start_backend ;;
        ontology) _ensure_backend; _start_ontology ;;
        equation) _ensure_backend; _start_equation ;;
        behaviour) _ensure_backend; _start_behaviour ;;
        modeller) _ensure_backend; _start_modeller ;;
        species)  _ensure_backend; _start_species ;;
        instantiation) _ensure_backend; _start_instantiation ;;
        all)
            _start_backend
            _start_ontology
            _start_equation
            _start_behaviour
            _start_modeller
            _start_species
            _start_instantiation
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
        species)   _kill_port $SPECIES_PORT   "species" ;;
        instantiation) _kill_port $INSTANTIATION_PORT "instantiation" ;;
        all)
            _kill_port $BACKEND_PORT   "backend"
            _kill_port $ONTOLOGY_PORT  "ontology-editor"
            _kill_port $EQUATION_PORT  "equation-editor"
            _kill_port $BEHAVIOUR_PORT "behaviour-linker"
            _kill_port $MODELLER_PORT  "modeller"
            _kill_port $SPECIES_PORT   "species"
            _kill_port $INSTANTIATION_PORT "instantiation"
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
    # Reseed = seed + HAP extensions.  The script runs offline: with no
    # .trig present its load() seeds fresh, extends, and writes
    # data/ontology.trig before the backend comes up.
    # Bare seed (no extensions): ./dev.sh wipe && ./dev.sh start backend
    if [ -f "$REPO/scripts/extend_ontology_hap.py" ]; then
        echo "  Reseeding: seed + HAP extensions (extend_ontology_hap.py)"
        (cd "$REPO" && uv run python scripts/extend_ontology_hap.py)
    fi
    cmd_start backend
}

cmd_save() {
    if ! _is_running $BACKEND_PORT; then
        echo "  Backend not running — nothing to save."
        return 1
    fi
    curl -s -m 5 -X POST "http://localhost:$BACKEND_PORT/api/ontology/save" \
        -H 'Content-Type: application/json' -d '{}'
    echo ""
}

_need_npm() {
    # node/npm live behind nvm and are not on PATH in a cold shell.
    if [ -f "$HOME/.nvm/nvm.sh" ]; then
        # shellcheck disable=SC1090
        . "$HOME/.nvm/nvm.sh" >/dev/null 2>&1
    fi
}

cmd_build() {
    # Rebuild the backend-served dist bundle(s).  dist/ is gitignored
    # build output — required whenever app source changes and the app
    # is viewed via the hub/backend rather than a Vite dev server.
    local service="${1:-all}"
    _need_npm
    cd "$REPO"
    case "$service" in
        backend)       echo "  backend is Python — nothing to build." ;;
        ontology)      npm run build -w @promo/ontology-editor ;;
        equation)      npm run build -w @promo/equation-editor ;;
        behaviour)     npm run build -w @promo/behaviour-linker ;;
        modeller)      npm run build -w @promo/modeller ;;
        species)       npm run build -w @promo/species ;;
        instantiation) npm run build -w @promo/instantiation ;;
        all)           npm run build --workspaces --if-present ;;
        *) echo "Unknown service: $service"; exit 1 ;;
    esac
}

cmd_sync() {
    # Machine-to-machine pickup: pull what the other machine pushed,
    # re-sync both dependency sets, rebuild dist bundles, restart every
    # service with fresh code.  --ff-only fails loudly on divergence.
    cd "$REPO"
    echo "Pulling..."
    git pull --ff-only || {
        echo "  git pull failed — local commits or dirty tracked files;"
        echo "  resolve manually (./dev.sh save + commit, or stash)."
        exit 1
    }
    echo "Syncing Python deps..."
    uv sync
    _need_npm
    echo "Installing node deps..."
    npm install --no-audit --no-fund
    cmd_build all
    cmd_start all
}

cmd_logs() {
    local service="${1:-backend}"
    case "$service" in
        backend)  tail -f "$BACKEND_LOG" ;;
        ontology)  tail -f "$ONTOLOGY_LOG" ;;
        equation)  tail -f "$EQUATION_LOG" ;;
        behaviour) tail -f "$BEHAVIOUR_LOG" ;;
        modeller)  tail -f "$MODELLER_LOG" ;;
        species)   tail -f "$SPECIES_LOG" ;;
        instantiation) tail -f "$INSTANTIATION_LOG" ;;
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
    echo "  wipe-restart        — wipe data + reseed (seed + HAP ext) + restart backend"
    echo "                        (bare seed: ./dev.sh wipe && ./dev.sh start backend)"
    echo "  save                — persist in-memory store (one .trig per artefact line)"
    echo "  sync                — pick up the other machine: pull + deps + build + start all"
    echo "  build   [service]   — rebuild backend-served dist bundle(s)"
    echo "  logs    [service]   — tail log for a service"
    echo ""
    echo "Services: backend | ontology | equation | behaviour | modeller | species | instantiation | all (default)"
    echo ""
    echo "URLs:"
    echo "  Hub (entry point)  http://localhost:$BACKEND_PORT/"
    echo "  Backend API        http://localhost:$BACKEND_PORT/api/health"
    echo "  Ontology Editor    http://localhost:$ONTOLOGY_PORT/ontology/"
    echo "  Equation Editor    http://localhost:$EQUATION_PORT"
    echo "  Behaviour Linker   http://localhost:$BEHAVIOUR_PORT"
    echo "  Modeller           http://localhost:$MODELLER_PORT"
    echo "  Species Editor     http://localhost:$SPECIES_PORT"
    echo "  Instantiation      http://localhost:$INSTANTIATION_PORT"
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
    save)          cmd_save ;;
    sync)          cmd_sync ;;
    build)         cmd_build "$SERVICE" ;;
    logs)          cmd_logs "$SERVICE" ;;
    help|--help|-h) cmd_help ;;
    *) echo "Unknown command: $COMMAND"; cmd_help; exit 1 ;;
esac

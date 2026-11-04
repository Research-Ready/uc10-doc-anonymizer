#!/usr/bin/env bash
# ==============================================================================
# UC10 Document Anonymizer — Start Web Control Dashboard
# Serves on http://localhost:5050 (100% Local / Offline)
# Supports macOS and Linux
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

# Helper to open browser cross-platform
open_browser() {
    local url="$1"
    if command -v open >/dev/null 2>&1; then
        open "$url" 2>/dev/null || true
    elif command -v xdg-open >/dev/null 2>&1; then
        xdg-open "$url" 2>/dev/null || true
    else
        echo "Open in your browser: $url"
    fi
}

# Determine Docker Compose location
if [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    COMPOSE_DIR="$SCRIPT_DIR"
elif [ -d "/home/chris/Nextcloud/Github/InstallLocalAiPackage/docker/localstack" ]; then
    COMPOSE_DIR="/home/chris/Nextcloud/Github/InstallLocalAiPackage/docker/localstack"
else
    COMPOSE_DIR="$SCRIPT_DIR"
fi

# Check if backend services are running on port 5010
if ! curl -s --connect-timeout 2 http://localhost:5010/health | grep -q "ok"; then
    echo "Starting local docker containers (Docling + Presidio)..."
    (cd "$COMPOSE_DIR" && docker compose -f docker-compose.yml up -d)
fi

# Check if dashboard is already running on port 5050
if curl -s --connect-timeout 1 http://localhost:5050/api/status >/dev/null 2>&1; then
    echo "Dashboard is already running on http://localhost:5050"
else
    echo "Starting dashboard on http://localhost:5050..."
    nohup python3 "$SCRIPT_DIR/scripts/web_dashboard.py" </dev/null > "$SCRIPT_DIR/dashboard.log" 2>&1 &
    disown
    
    # Wait up to 5 seconds for dashboard to become ready
    for i in {1..10}; do
        if curl -s --connect-timeout 1 http://localhost:5050/api/status >/dev/null 2>&1; then
            break
        fi
        sleep 0.5
    done
fi

echo "Opening http://localhost:5050 in your browser..."
open_browser "http://localhost:5050"
echo "Dashboard live at http://localhost:5050"

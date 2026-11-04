#!/usr/bin/env bash
# ==============================================================================
# UC10 Document Anonymizer — One-Click Runner ("GO")
# 100% Local Processing — Zero Cloud LLMs — Local spaCy & Docling Models Only
# Supports macOS and Linux
# ==============================================================================
set -e

# Detect directories
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_DIR="$SCRIPT_DIR"

# Determine Docker Compose location
if [ -f "$SCRIPT_DIR/docker-compose.yml" ]; then
    COMPOSE_DIR="$SCRIPT_DIR"
elif [ -d "/home/chris/Nextcloud/Github/InstallLocalAiPackage/docker/localstack" ]; then
    COMPOSE_DIR="/home/chris/Nextcloud/Github/InstallLocalAiPackage/docker/localstack"
else
    COMPOSE_DIR="$SCRIPT_DIR"
fi

# Helper to open folder cross-platform
open_folder() {
    local target="$1"
    if command -v open >/dev/null 2>&1; then
        open "$target" 2>/dev/null || true
    elif [ -n "$DISPLAY" ] || [ -n "$WAYLAND_DISPLAY" ]; then
        xdg-open "$target" 2>/dev/null || true
    fi
}

# Handle --ui or --web flag
if [[ "$1" == "--ui" || "$1" == "--web" ]]; then
    exec "$REPO_DIR/dashboard.sh"
fi

# Text styles
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}======================================================${RESET}"
echo -e "${BOLD}${CYAN}   UC10 DOCUMENT ANONYMIZER (100% Local Pipeline)     ${RESET}"
echo -e "${BOLD}${CYAN}======================================================${RESET}"
echo -e "${GREEN}✓ Local NER Models:${RESET} spaCy nl_core_news_lg + en_core_web_lg"
echo -e "${GREEN}✓ Local Parser:${RESET}     Docling CPU (local container)"
echo -e "${GREEN}✓ Privacy Guarantee:${RESET} Completely offline / zero cloud API calls"
echo ""

# 1. Check if backend service is running on port 5010
echo -e "${BLUE}[1/4] Checking backend services...${RESET}"
if ! curl -s --connect-timeout 2 http://localhost:5010/health | grep -q "ok"; then
    echo -e "${YELLOW}  Backend service not running. Starting local Docker stack...${RESET}"
    if [ -d "$COMPOSE_DIR" ]; then
        (cd "$COMPOSE_DIR" && docker compose -f docker-compose.yml up -d)
    else
        echo -e "${RED}Error: Compose directory not found at $COMPOSE_DIR${RESET}"
        exit 1
    fi

    echo -n "  Waiting for local models to load"
    MAX_WAIT=60
    WAIT_COUNT=0
    while ! curl -s --connect-timeout 2 http://localhost:5010/health | grep -q "ok"; do
        sleep 2
        echo -n "."
        WAIT_COUNT=$((WAIT_COUNT + 2))
        if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
            echo ""
            echo -e "${RED}  Timed out waiting for service at http://localhost:5010${RESET}"
            echo -e "${YELLOW}  Check container logs with: docker compose logs uc10-anonymizer${RESET}"
            exit 1
        fi
    done
    echo ""
fi
echo -e "${GREEN}  ✓ Anonymizer service healthy on http://localhost:5010${RESET}"

# 2. Check Docling service on port 5001
if curl -s --connect-timeout 2 http://localhost:5001/health | grep -q "ok"; then
    echo -e "${GREEN}  ✓ Docling document parser healthy on http://localhost:5001${RESET}"
else
    echo -e "${YELLOW}  Note: Docling is starting or not responding; fallback plain-text extractor will be used if needed.${RESET}"
fi

# 3. Check Input Folder
echo -e "${BLUE}[2/4] Checking input documents...${RESET}"
INPUT_DIR="$REPO_DIR/input"
OUTPUT_DIR="$REPO_DIR/output"
KEYS_DIR="$REPO_DIR/keys"

# Count files with supported extensions: pdf, docx, txt, md
FILE_COUNT=$(find "$INPUT_DIR" -maxdepth 1 -type f \( -iname "*.pdf" -o -iname "*.docx" -o -iname "*.txt" -o -iname "*.md" \) ! -name "README.md" ! -name "targets.txt" 2>/dev/null | wc -l || echo 0)

if [ "$FILE_COUNT" -eq 0 ]; then
    echo -e "${YELLOW}  No documents found in ${INPUT_DIR}${RESET}"
    echo -e "  Please put your documents (.pdf, .docx, .txt, .md) into the input folder."
    echo -e "  Opening the input folder for you now..."
    open_folder "$INPUT_DIR"
    echo ""
    echo -e "${CYAN}Once you've placed your files in input/, run ./go.sh again.${RESET}"
    exit 0
fi

echo -e "${GREEN}  Found ${FILE_COUNT} document(s) to process in input/${RESET}"

# Check targets.txt
if [ -f "$INPUT_DIR/targets.txt" ]; then
    TARGET_LINES=$(grep -v '^[[:space:]]*#' "$INPUT_DIR/targets.txt" | grep -v '^[[:space:]]*$' || true)
    if [ -n "$TARGET_LINES" ]; then
        echo -e "${CYAN}  Target organisation(s) to mask:${RESET}"
        echo "$TARGET_LINES" | while read -r line; do
            echo -e "    - ${YELLOW}$line${RESET}"
        done
    else
        echo -e "${YELLOW}  Note: targets.txt is empty; only personal identities will be masked.${RESET}"
    fi
else
    echo -e "${YELLOW}  Note: No input/targets.txt found; only personal identities will be masked.${RESET}"
fi

# 4. Run Anonymization
echo ""
echo -e "${BLUE}[3/4] Running local anonymization pipeline...${RESET}"
python3 "$REPO_DIR/scripts/anonymize_folder.py" "$@"

# 5. Summary & Open Output
echo ""
echo -e "${BOLD}${GREEN}======================================================${RESET}"
echo -e "${BOLD}${GREEN}                 ANONYMIZATION FINISHED               ${RESET}"
echo -e "${BOLD}${GREEN}======================================================${RESET}"
echo -e "${BOLD}Output folder:${RESET} $OUTPUT_DIR"
echo -e "${BOLD}Keys folder:${RESET}   $KEYS_DIR (keep secure/separate from outputs!)"
echo ""

open_folder "$OUTPUT_DIR"

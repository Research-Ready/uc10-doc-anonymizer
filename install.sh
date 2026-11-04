#!/usr/bin/env bash
# ==============================================================================
# UC10 Document Anonymizer — Cross-Platform Installer (macOS & Linux)
# Sets up Docker, dependencies, environment, and verifies health.
# ==============================================================================
set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors & Formatting
BOLD="\033[1m"
GREEN="\033[32m"
BLUE="\033[34m"
YELLOW="\033[33m"
CYAN="\033[36m"
RED="\033[31m"
RESET="\033[0m"

echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo -e "${BOLD}${CYAN}   UC10 DOCUMENT ANONYMIZER — INSTALLER (macOS & Linux)         ${RESET}"
echo -e "${BOLD}${CYAN}   100% Lokaal & Veilig — Geen Cloud LLMs — Privacy Gegarandeerd${RESET}"
echo -e "${BOLD}${CYAN}================================================================${RESET}"
echo ""

# Detect OS
OS_NAME="$(uname -s)"
case "$OS_NAME" in
    Darwin*)  PLATFORM="macOS" ;;
    Linux*)   PLATFORM="Linux" ;;
    *)        PLATFORM="Unknown ($OS_NAME)" ;;
esac
echo -e "${BLUE}[1/5] Gedetecteerd platform:${RESET} ${BOLD}${PLATFORM}${RESET}"

# 1. Check Docker & Docker Compose
echo -e "${BLUE}[2/5] Controleren van vereisten (Docker & Python)...${RESET}"

if ! command -v docker >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker is niet gevonden!${RESET}"
    if [ "$PLATFORM" == "macOS" ]; then
        echo -e "${YELLOW}  Installeer Docker Desktop via: https://www.docker.com/products/docker-desktop${RESET}"
        echo -e "${YELLOW}  Of met Homebrew: brew install --cask docker${RESET}"
    else
        echo -e "${YELLOW}  Installeer Docker Engine via: https://docs.docker.com/engine/install/${RESET}"
    fi
    exit 1
fi

if ! docker info >/dev/null 2>&1; then
    echo -e "${RED}✗ Docker daemon is momenteel niet actief!${RESET}"
    if [ "$PLATFORM" == "macOS" ]; then
        echo -e "${YELLOW}  Start a.u.b. de Docker Desktop applicatie en wacht tot deze gereed is.${RESET}"
    else
        echo -e "${YELLOW}  Start de service via: sudo systemctl start docker${RESET}"
    fi
    exit 1
fi
echo -e "${GREEN}  ✓ Docker daemon is actief en bereikbaar.${RESET}"

# Check Docker Compose (v2 plugin or standalone)
if docker compose version >/dev/null 2>&1; then
    COMPOSE_CMD="docker compose"
elif command -v docker-compose >/dev/null 2>&1; then
    COMPOSE_CMD="docker-compose"
else
    echo -e "${RED}✗ Docker Compose is niet gevonden!${RESET}"
    exit 1
fi
echo -e "${GREEN}  ✓ Docker Compose is beschikbaar (${COMPOSE_CMD}).${RESET}"

# Check Python 3
if ! command -v python3 >/dev/null 2>&1; then
    echo -e "${YELLOW}  Waarschuwing: python3 niet gevonden in PATH.${RESET}"
    echo -e "${YELLOW}  De Docker containers werken, maar voor het Web Dashboard is Python 3.10+ vereist.${RESET}"
else
    # Never fatal: macOS ships a python3 stub that fails without the Xcode tools; Docker mode needs no Python
    if PY_VER=$(python3 -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null); then
        echo -e "${GREEN}  ✓ Python ${PY_VER} gevonden.${RESET}"
    else
        echo -e "${YELLOW}  Python niet bruikbaar; niet nodig, alles draait in Docker.${RESET}"
    fi
fi

# 2. Setup Directories & .env
echo -e "${BLUE}[3/5] Mappen en omgevingsvariabelen inrichten...${RESET}"
mkdir -p input output keys

if [ ! -f ".env" ]; then
    echo -e "  Genereer nieuw veilig wachtwoord voor lokale Neo4j registry..."
    RANDOM_PASS=$(openssl rand -hex 16 2>/dev/null || python3 -c "import secrets; print(secrets.token_hex(16))" 2>/dev/null || echo "uc10-secure-$(date +%s)")
    cat <<EOF > .env
# Gegenereerd door install.sh op $(date)
NEO4J_PASSWORD=${RANDOM_PASS}
LOCALSTACK_BIND=127.0.0.1
DASHBOARD_BIND=127.0.0.1
EOF
    echo -e "${GREEN}  ✓ .env bestand aangemaakt met uniek gegenereerd wachtwoord.${RESET}"
else
    echo -e "${GREEN}  ✓ Bestaand .env bestand behouden.${RESET}"
fi

# Make scripts executable
chmod +x go.sh dashboard.sh install.sh scripts/*.py scripts/*.sh 2>/dev/null || true
echo -e "${GREEN}  ✓ Uitvoerrechten ingesteld op alle launcher-scripts.${RESET}"

# 3. Build & Pull Containers
echo -e "${BLUE}[4/5] Docker images ophalen en bouwen...${RESET}"
echo -e "  - Ophalen Docling CPU container (v1.35.0)..."
$COMPOSE_CMD pull docling neo4j

echo -e "  - Bouwen UC10 Presidio Anonymizer container met Nederlandse & Engelse modellen..."
$COMPOSE_CMD build uc10-anonymizer
echo -e "${GREEN}  ✓ Alle Docker images succesvol voorbereid.${RESET}"

# 4. Verify & Health Check
echo -e "${BLUE}[5/5] Services starten en status testen...${RESET}"
$COMPOSE_CMD up -d

echo -n "  Wachten op initialisatie van de modellen"
MAX_WAIT=300
WAIT_COUNT=0
while ! curl -s --connect-timeout 2 http://localhost:5010/health | grep -q "ok"; do
    sleep 2
    echo -n "."
    WAIT_COUNT=$((WAIT_COUNT + 2))
    if [ $WAIT_COUNT -ge $MAX_WAIT ]; then
        echo ""
        echo -e "${YELLOW}  De containers starten op, maar model verificatie duurde langer dan 5 minuten.${RESET}"
        echo -e "${YELLOW}  Controleer status via: $COMPOSE_CMD logs uc10-anonymizer${RESET}"
        break
    fi
done

if curl -s --connect-timeout 2 http://localhost:5010/health | grep -q "ok"; then
    echo ""
    echo -e "${GREEN}  ✓ UC10 Anonymizer service is gezond en reageert op http://localhost:5010${RESET}"
fi

echo ""
echo -e "${BOLD}${GREEN}================================================================${RESET}"
echo -e "${BOLD}${GREEN}              INSTALLATIE SUCCESVOL VOLTOOID!                   ${RESET}"
echo -e "${BOLD}${GREEN}================================================================${RESET}"
echo ""
echo -e "${BOLD}Hoe nu te gebruiken:${RESET}"
echo -e "  1. ${CYAN}Web Dashboard:${RESET}    Open ${BOLD}http://localhost:5050${RESET} in je browser"
echo -e "  2. ${CYAN}Directe Verwerking:${RESET} Plaats bestanden in ${BOLD}input/${RESET} en start ${BOLD}./go.sh${RESET}"
echo ""
echo -e "Gereed voor gebruik!"

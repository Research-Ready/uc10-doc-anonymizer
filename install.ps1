# ==============================================================================
# UC10 Document Anonymizer — Windows PowerShell Installer
# Run in PowerShell: .\install.ps1
# Requires: Docker Desktop for Windows (WSL2 backend)
# ==============================================================================

Write-Host "================================================================" -ForegroundColor Cyan
Write-Host "   UC10 DOCUMENT ANONYMIZER — WINDOWS INSTALLER                " -ForegroundColor Cyan
Write-Host "   100% Lokaal & Veilig — Geen Cloud LLMs                      " -ForegroundColor Cyan
Write-Host "================================================================" -ForegroundColor Cyan
Write-Host ""

# 1. Check Docker
Write-Host "[1/4] Controleren van Docker Desktop..." -ForegroundColor Blue
if (-not (Get-Command docker -ErrorAction SilentlyContinue)) {
    Write-Host "✗ Docker is niet gevonden!" -ForegroundColor Red
    Write-Host "  Installeer a.u.b. Docker Desktop via: https://www.docker.com/products/docker-desktop" -ForegroundColor Yellow
    exit 1
}

try {
    $dockerInfo = docker info 2>&1
    if ($LASTEXITCODE -ne 0) {
        Write-Host "✗ Docker Desktop is momenteel niet actief!" -ForegroundColor Red
        Write-Host "  Start Docker Desktop en wacht tot het walvis-icoon groen is." -ForegroundColor Yellow
        exit 1
    }
} catch {
    Write-Host "✗ Kon geen verbinding maken met Docker daemon." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Docker Desktop is actief." -ForegroundColor Green

# 2. Setup Directories & .env
Write-Host "[2/4] Mappen en configuratie inrichten..." -ForegroundColor Blue
New-Item -ItemType Directory -Force -Path "input", "output", "keys" | Out-Null

if (-not (Test-Path ".env")) {
    $bytes = New-Object byte[] 16
    $rng = [System.Security.Cryptography.RandomNumberGenerator]::Create()
    $rng.GetBytes($bytes)
    $rndPass = -join ($bytes | ForEach-Object { "{0:x2}" -f $_ })
    
    $envContent = @"
# Gegenereerd door install.ps1
NEO4J_PASSWORD=$rndPass
LOCALSTACK_BIND=0.0.0.0
"@
    Set-Content -Path ".env" -Value $envContent -Encoding UTF8
    Write-Host "  ✓ .env bestand aangemaakt met veilig Neo4j wachtwoord." -ForegroundColor Green
} else {
    Write-Host "  ✓ Bestaand .env bestand behouden." -ForegroundColor Green
}

# 3. Pull & Build Containers
Write-Host "[3/4] Docker images ophalen en bouwen..." -ForegroundColor Blue
docker compose pull docling neo4j
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fout bij ophalen van base images." -ForegroundColor Red
    exit 1
}

docker compose build uc10-anonymizer
if ($LASTEXITCODE -ne 0) {
    Write-Host "✗ Fout bij bouwen van UC10 Anonymizer container." -ForegroundColor Red
    exit 1
}
Write-Host "  ✓ Images succesvol gereedgemaakt." -ForegroundColor Green

# 4. Start & Health Check
Write-Host "[4/4] Services starten en controleren..." -ForegroundColor Blue
docker compose up -d

Write-Host "Wachten op initialisatie van modellen..." -NoNewline
$maxWait = 60
$waited = 0
$isHealthy = $false

while ($waited -lt $maxWait) {
    Start-Sleep -Seconds 2
    Write-Host "." -NoNewline
    $waited += 2
    try {
        $resp = Invoke-RestMethod -Uri "http://localhost:5010/health" -TimeoutSec 2 -ErrorAction SilentlyContinue
        if ($resp.status -eq "ok") {
            $isHealthy = $true
            break
        }
    } catch {}
}

Write-Host ""
if ($isHealthy) {
    Write-Host "  ✓ UC10 Anonymizer is gezond en operationeel op http://localhost:5010" -ForegroundColor Green
} else {
    Write-Host "  De containers zijn gestart; controleer status via: docker compose logs uc10-anonymizer" -ForegroundColor Yellow
}

Write-Host ""
Write-Host "================================================================" -ForegroundColor Green
Write-Host "              INSTALLATIE SUCCESVOL VOLTOOID!                   " -ForegroundColor Green
Write-Host "================================================================" -ForegroundColor Green
Write-Host ""
Write-Host "Starten van het Web Dashboard:"
Write-Host "  python scripts\web_dashboard.py" -ForegroundColor Cyan
Write-Host "Of open http://localhost:5050 in de browser."

# PULSE — Script de demarrage
# Usage: .\start.ps1           -> demarrage normal
#        .\start.ps1 -Update   -> verifie et met a jour les composants avant

param(
    [switch]$Update
)

$ErrorActionPreference = "Stop"
$ROOT = Split-Path -Parent $MyInvocation.MyCommand.Path

function Write-Step($msg) { Write-Host "`n>>> $msg" -ForegroundColor Cyan }
function Write-OK($msg)   { Write-Host "    OK  $msg" -ForegroundColor Green }
function Write-Warn($msg) { Write-Host "    >>  $msg" -ForegroundColor Yellow }
function Write-Fail($msg) { Write-Host "    ERR $msg" -ForegroundColor Red }

Write-Host ""
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "   PULSE OS - Demarrage                   " -ForegroundColor Magenta
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host ""

# ============================================================
# MISES A JOUR (optionnel : .\start.ps1 -Update)
# ============================================================
if ($Update) {
    Write-Step "Mode mise a jour active (-Update)"

    # --- npm ---
    Write-Host "    npm : verification..." -ForegroundColor Yellow
    try {
        $npmCurrent = (npm --version 2>&1).Trim()
        $npmLatest  = (npm view npm version 2>&1).Trim()
        if ($npmCurrent -ne $npmLatest) {
            Write-Warn "npm $npmCurrent -> $npmLatest  (mise a jour en cours...)"
            npm install -g npm@latest 2>&1 | Out-Null
            Write-OK "npm mis a jour vers $npmLatest"
        } else {
            Write-OK "npm $npmCurrent est a jour"
        }
    } catch {
        Write-Warn "Impossible de verifier npm (Node.js installe ?)"
    }

    # --- pip dans le venv ---
    $backendPy = Join-Path $ROOT "backend\venv\Scripts\python.exe"
    if (Test-Path $backendPy) {
        Write-Host "    pip (venv) : verification..." -ForegroundColor Yellow
        try {
            $pipOut = & $backendPy -m pip install --upgrade pip 2>&1
            if ($pipOut -match "Successfully installed pip-(.+)") {
                Write-OK "pip mis a jour vers $($Matches[1])"
            } else {
                $pipVer = (& $backendPy -m pip --version 2>&1) -replace "pip (.+?) from.*", '$1'
                Write-OK "pip $pipVer est a jour"
            }
        } catch {
            Write-Warn "Impossible de mettre a jour pip dans le venv"
        }
    } else {
        Write-Warn "Venv introuvable, pip non verifie"
    }

    # --- Docker Desktop ---
    Write-Host "    Docker Desktop : verification..." -ForegroundColor Yellow
    try {
        $dockerVer = (docker version --format "{{.Client.Version}}" 2>&1).Trim()
        Write-OK "Docker Desktop $dockerVer"
        Write-Warn "Mise a jour Docker Desktop : ouvrez Docker Desktop > Settings > Software updates"
    } catch {
        Write-Warn "Docker non accessible pour la verification"
    }

    Write-Host ""
    Write-Host "    Mises a jour terminees. Demarrage de PULSE..." -ForegroundColor Cyan
}

# ============================================================
# DEMARRAGE
# ============================================================

# --- 1. Docker Desktop ---
Write-Step "Verification de Docker Desktop..."

$dockerRunning = $false
try {
    docker ps 2>&1 | Out-Null
    $dockerRunning = $true
    Write-OK "Docker Desktop deja en cours d'execution"
} catch {}

if (-not $dockerRunning) {
    Write-Warn "Docker Desktop n'est pas demarre. Lancement..."

    $dockerExe = "C:\Program Files\Docker\Docker\Docker Desktop.exe"
    if (-not (Test-Path $dockerExe)) {
        Write-Fail "Docker Desktop introuvable : $dockerExe"
        Write-Host "    Installez Docker Desktop depuis docker.com" -ForegroundColor Yellow
        Read-Host "Appuyez sur Entree pour quitter"
        exit 1
    }

    Start-Process $dockerExe
    Write-Host "    Attente du daemon Docker (60s max)..." -ForegroundColor Yellow

    $maxWait = 60
    $elapsed = 0
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds 3
        $elapsed += 3
        try {
            docker ps 2>&1 | Out-Null
            $msg = "Docker Desktop pret (" + $elapsed + "s)"
            Write-OK $msg
            $dockerRunning = $true
            break
        } catch {}
        $msg = "    attente " + $elapsed + "/" + $maxWait + "s"
        Write-Host $msg -ForegroundColor DarkGray
    }

    if (-not $dockerRunning) {
        Write-Fail "Docker Desktop n'a pas repondu en 60s."
        Read-Host "Appuyez sur Entree pour quitter"
        exit 1
    }
}

# --- 2. Base de donnees TimescaleDB ---
Write-Step "Demarrage de la base de donnees TimescaleDB..."
Set-Location $ROOT

$dbRunning = docker ps --filter "name=pulse-db" --filter "status=running" -q 2>&1
if ($dbRunning) {
    Write-OK "pulse-db deja en cours d'execution"
} else {
    docker-compose up -d 2>&1 | Out-Null
    Start-Sleep -Seconds 4

    $dbRunning = docker ps --filter "name=pulse-db" --filter "status=running" -q 2>&1
    if ($dbRunning) {
        Write-OK "pulse-db demarre"
    } else {
        Write-Fail "Echec du demarrage de pulse-db"
        docker-compose logs db
        Read-Host "Appuyez sur Entree pour quitter"
        exit 1
    }
}

# --- 3. Backend FastAPI ---
Write-Step "Demarrage du backend FastAPI (port 8000)..."

$backendPython = Join-Path $ROOT "backend\venv\Scripts\python.exe"
if (-not (Test-Path $backendPython)) {
    Write-Fail "Venv Python introuvable : $backendPython"
    Write-Host "    Executez dans un terminal :" -ForegroundColor Yellow
    Write-Host "      python -m venv backend\venv" -ForegroundColor Yellow
    Write-Host "      backend\venv\Scripts\pip install -r backend\requirements.txt" -ForegroundColor Yellow
    Read-Host "Appuyez sur Entree pour quitter"
    exit 1
}

$backendRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) { $backendRunning = $true }
} catch {}

if ($backendRunning) {
    Write-OK "Backend deja en cours d'execution sur :8000"
} else {
    Start-Process -FilePath $backendPython `
        -ArgumentList "-m", "uvicorn", "backend.main:app", "--reload", "--host", "127.0.0.1", "--port", "8000" `
        -WorkingDirectory $ROOT `
        -WindowStyle Normal

    Write-Host "    Attente du backend..." -ForegroundColor Yellow
    $maxWait = 20
    $elapsed = 0
    while ($elapsed -lt $maxWait) {
        Start-Sleep -Seconds 2
        $elapsed += 2
        try {
            $resp = Invoke-WebRequest -Uri "http://127.0.0.1:8000/api/health" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
            if ($resp.StatusCode -eq 200) {
                $msg = "Backend pret sur http://127.0.0.1:8000 (" + $elapsed + "s)"
                Write-OK $msg
                break
            }
        } catch {}
        $msg = "    attente " + $elapsed + "/" + $maxWait + "s"
        Write-Host $msg -ForegroundColor DarkGray
    }
}

# --- 4. Frontend Vite ---
Write-Step "Demarrage du frontend Vite (port 5173)..."

$frontendPath = Join-Path $ROOT "frontend"
$viteScript   = Join-Path $frontendPath "node_modules\vite\bin\vite.js"

if (-not (Test-Path $viteScript)) {
    Write-Fail "node_modules introuvable."
    Write-Host "    Executez : cd frontend ; npm install" -ForegroundColor Yellow
    Read-Host "Appuyez sur Entree pour quitter"
    exit 1
}

$frontendRunning = $false
try {
    $resp = Invoke-WebRequest -Uri "http://127.0.0.1:5173" -TimeoutSec 2 -UseBasicParsing -ErrorAction SilentlyContinue
    if ($resp.StatusCode -eq 200) { $frontendRunning = $true }
} catch {}

if ($frontendRunning) {
    Write-OK "Frontend deja en cours d'execution sur :5173"
} else {
    Start-Process -FilePath "node" `
        -ArgumentList $viteScript, $frontendPath, "--port", "5173" `
        -WorkingDirectory $frontendPath `
        -WindowStyle Normal

    Start-Sleep -Seconds 3
    Write-OK "Frontend demarre sur http://127.0.0.1:5173"
}

# --- Resume ---
Write-Host ""
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host "   PULSE OS est pret !" -ForegroundColor Green
Write-Host "==========================================" -ForegroundColor Magenta
Write-Host ""
Write-Host "   Frontend  : http://127.0.0.1:5173" -ForegroundColor White
Write-Host "   Backend   : http://127.0.0.1:8000" -ForegroundColor White
Write-Host "   API docs  : http://127.0.0.1:8000/docs" -ForegroundColor White
Write-Host "   DB        : localhost:5432  user=pulse  db=pulse" -ForegroundColor White
Write-Host ""
Write-Host "   Tip: .\start.ps1 -Update  pour mettre a jour npm/pip/Docker" -ForegroundColor DarkGray
Write-Host ""

$url = "http://127.0.0.1:5173"
Start-Process $url

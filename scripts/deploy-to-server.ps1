<#
.SYNOPSIS
    Sube código local al servidor y reconstruye los workers Docker.

.DESCRIPTION
    Sincroniza el código fuente (services/, shared/) al servidor y opcionalmente
    reconstruye los contenedores Docker especificados.

.PARAMETER Workers
    Qué workers reconstruir después de subir: fb, yt, arxiv, all, none (default: none)

.EXAMPLE
    .\scripts\deploy-to-server.ps1                      # solo sube código
    .\scripts\deploy-to-server.ps1 -Workers fb           # sube + rebuild fb-worker
    .\scripts\deploy-to-server.ps1 -Workers all          # sube + rebuild todos
#>

param(
    [ValidateSet("fb", "yt", "arxiv", "all", "none")]
    [string]$Workers = "none"
)

$ErrorActionPreference = "Stop"

# ── Configuración ────────────────────────────────────────────────────────────
$SERVER = "danilo@192.168.100.18"
$REMOTE_BASE = "~/personal-agent"
$LOCAL_BASE = Split-Path -Parent $PSScriptRoot

# ── Upload código ────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "🚀 Deploy al servidor ($SERVER)" -ForegroundColor White
Write-Host "   $(Get-Date -Format 'yyyy-MM-dd HH:mm:ss')" -ForegroundColor DarkGray
Write-Host ""

# Subir shared/
Write-Host "📤 Subiendo shared/..." -ForegroundColor Cyan
scp -r "$LOCAL_BASE\shared\shared\*" "${SERVER}:${REMOTE_BASE}/shared/shared/" 2>&1
Write-Host "   ✅ shared/ subido" -ForegroundColor Green

# Subir services/
$services = @("fb", "youtube", "arxiv")
foreach ($svc in $services) {
    $localSvc = "$LOCAL_BASE\services\$svc"
    if (Test-Path "$localSvc") {
        $workerName = Get-ChildItem -Path $localSvc -Directory | Where-Object { $_.Name -like "*_worker" } | Select-Object -First 1
        if ($workerName) {
            Write-Host "📤 Subiendo services/$svc/$($workerName.Name)/..." -ForegroundColor Cyan
            scp -r "$localSvc\$($workerName.Name)\*" "${SERVER}:${REMOTE_BASE}/services/$svc/$($workerName.Name)/" 2>&1
            Write-Host "   ✅ $svc subido" -ForegroundColor Green
        }
    }
}

# Subir docker-compose.yml
Write-Host "📤 Subiendo docker-compose.yml..." -ForegroundColor Cyan
scp "$LOCAL_BASE\docker-compose.yml" "${SERVER}:${REMOTE_BASE}/" 2>&1
Write-Host "   ✅ docker-compose.yml subido" -ForegroundColor Green

# ── Rebuild Docker (opcional) ────────────────────────────────────────────────

if ($Workers -ne "none") {
    Write-Host ""

    $workerMap = @{
        "fb"    = "fb-worker"
        "yt"    = "yt-worker"
        "arxiv" = "arxiv-worker"
    }

    $toBuild = if ($Workers -eq "all") { @("fb", "yt", "arxiv") } else { @($Workers) }

    foreach ($w in $toBuild) {
        $dockerName = $workerMap[$w]
        Write-Host "🔨 Reconstruyendo $dockerName..." -ForegroundColor Cyan
        ssh $SERVER "cd $REMOTE_BASE && docker compose build $dockerName 2>&1 | tail -5"
        if ($LASTEXITCODE -eq 0) {
            Write-Host "   ✅ $dockerName reconstruido" -ForegroundColor Green

            Write-Host "🔄 Reiniciando $dockerName..." -ForegroundColor Cyan
            ssh $SERVER "cd $REMOTE_BASE && docker compose up -d $dockerName 2>&1"
            Write-Host "   ✅ $dockerName reiniciado" -ForegroundColor Green
        } else {
            Write-Host "   ❌ Error construyendo $dockerName" -ForegroundColor Red
        }
    }
}

# ── Status ───────────────────────────────────────────────────────────────────

Write-Host ""
Write-Host "📊 Estado actual de los contenedores:" -ForegroundColor White
ssh $SERVER "docker ps --format 'table {{.Names}}\t{{.Status}}' 2>&1"

Write-Host ""
Write-Host "✅ Deploy completado" -ForegroundColor Green
Write-Host ""

# ═══════════════════════════════════════════════════════════════════════════════
# deploy.ps1 — Deploy personal-agent to remote server via SSH (Windows)
#
# Usage:
#   .\deploy.ps1                 # Full deploy (build + transfer + launch)
#   .\deploy.ps1 -Action build   # Only build and transfer image
#   .\deploy.ps1 -Action start   # Only (re)start containers on server
#   .\deploy.ps1 -Action logs    # Tail agent logs on server
#   .\deploy.ps1 -Action status  # Check container status
#   .\deploy.ps1 -Action ssh     # Open SSH session to server
#   .\deploy.ps1 -Action stop    # Stop containers
# ═══════════════════════════════════════════════════════════════════════════════

param(
    [ValidateSet("deploy", "build", "start", "logs", "status", "ssh", "stop")]
    [string]$Action = "deploy"
)

$ErrorActionPreference = "Stop"

# ── Configuration ────────────────────────────────────────────────────────────
$REMOTE_USER = "danilo"
$REMOTE_HOST = "192.168.100.18"
$REMOTE_DIR  = "/home/$REMOTE_USER/personal-agent"
$IMAGE_NAME  = "personal-agent-agent"
$ARCHIVE     = "personal-agent-image.tar.gz"
$SSH_TARGET  = "${REMOTE_USER}@${REMOTE_HOST}"

function Write-Log   { param($msg) Write-Host "[DEPLOY] $msg" -ForegroundColor Green }
function Write-Warn  { param($msg) Write-Host "[WARN]   $msg" -ForegroundColor Yellow }
function Write-Err   { param($msg) Write-Host "[ERROR]  $msg" -ForegroundColor Red }

function Invoke-SSH {
    param([string]$Command)
    ssh -o ConnectTimeout=10 -o ServerAliveInterval=30 $SSH_TARGET $Command
    if ($LASTEXITCODE -ne 0) { throw "SSH command failed: $Command" }
}

function Test-Connection {
    Write-Log "Testing SSH connection to $SSH_TARGET ..."
    ssh -o ConnectTimeout=10 $SSH_TARGET "echo 'Connection OK'"
    if ($LASTEXITCODE -ne 0) {
        Write-Err "Cannot connect to $REMOTE_HOST. Check SSH config."
        exit 1
    }
}

function Build-Image {
    Write-Log "Building Docker image locally ..."
    docker compose build
    if ($LASTEXITCODE -ne 0) { throw "Docker build failed" }

    Write-Log "Saving image to $ARCHIVE ..."
    docker save "${IMAGE_NAME}:latest" | & gzip > $ARCHIVE
    $size = (Get-Item $ARCHIVE).Length / 1MB
    Write-Log "Image archive: $([math]::Round($size, 1)) MB"
}

function Transfer-Files {
    Write-Log "Creating remote directory $REMOTE_DIR ..."
    Invoke-SSH "mkdir -p ${REMOTE_DIR}/{vault,profiles,logs}"

    Write-Log "Transferring image archive ..."
    scp -o ConnectTimeout=10 $ARCHIVE "${SSH_TARGET}:${REMOTE_DIR}/"
    if ($LASTEXITCODE -ne 0) { throw "SCP failed for archive" }

    Write-Log "Transferring docker-compose.yml and .env ..."
    scp -o ConnectTimeout=10 docker-compose.yml "${SSH_TARGET}:${REMOTE_DIR}/"
    scp -o ConnectTimeout=10 .env "${SSH_TARGET}:${REMOTE_DIR}/"

    # Transfer browser profiles if they exist
    if (Test-Path "./profiles" -PathType Container) {
        $profiles = Get-ChildItem -Path "./profiles" -ErrorAction SilentlyContinue
        if ($profiles) {
            Write-Log "Transferring browser profiles ..."
            scp -o ConnectTimeout=10 -r ./profiles/* "${SSH_TARGET}:${REMOTE_DIR}/profiles/"
        } else {
            Write-Warn "No browser profiles found — you'll need to create them."
        }
    }
}

function Start-Remote {
    Write-Log "Loading image on remote server ..."
    Invoke-SSH "cd ${REMOTE_DIR} && docker load < ${ARCHIVE}"

    Write-Log "Stopping old containers ..."
    ssh -o ConnectTimeout=10 $SSH_TARGET "cd ${REMOTE_DIR} && docker compose down 2>/dev/null; true"

    Write-Log "Starting containers ..."
    Invoke-SSH "cd ${REMOTE_DIR} && docker compose up -d"

    Write-Log "Waiting 10s for services to initialize ..."
    Start-Sleep -Seconds 10

    Write-Log "Container status:"
    Invoke-SSH "cd ${REMOTE_DIR} && docker compose ps"
}

function Show-Logs {
    ssh -o ConnectTimeout=10 -o ServerAliveInterval=30 $SSH_TARGET "cd ${REMOTE_DIR} && docker compose logs -f --tail=50 agent"
}

function Show-Status {
    Invoke-SSH "cd ${REMOTE_DIR} && docker compose ps && echo '---' && docker compose logs --tail=10 agent"
}

# ── Main ─────────────────────────────────────────────────────────────────────

switch ($Action) {
    "deploy" {
        Test-Connection
        Build-Image
        Transfer-Files
        Start-Remote
        if (Test-Path $ARCHIVE) { Remove-Item $ARCHIVE -Force }
        Write-Log "✓ Deployment complete! Agent running on $REMOTE_HOST"
        Write-Log "  View logs: .\deploy.ps1 -Action logs"
        Write-Log "  Status:    .\deploy.ps1 -Action status"
        Write-Log "  Vault:     ${REMOTE_DIR}/vault/Agent-Research/"
    }
    "build" {
        Build-Image
        Test-Connection
        Transfer-Files
        if (Test-Path $ARCHIVE) { Remove-Item $ARCHIVE -Force }
        Write-Log "✓ Image transferred. Run '.\deploy.ps1 -Action start' to launch."
    }
    "start" {
        Test-Connection
        Start-Remote
    }
    "logs" {
        Test-Connection
        Show-Logs
    }
    "status" {
        Test-Connection
        Show-Status
    }
    "ssh" {
        ssh -o ConnectTimeout=10 -o ServerAliveInterval=30 $SSH_TARGET
    }
    "stop" {
        Test-Connection
        Invoke-SSH "cd ${REMOTE_DIR} && docker compose down"
        Write-Log "✓ Containers stopped."
    }
}

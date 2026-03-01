#!/usr/bin/env bash
# ═══════════════════════════════════════════════════════════════════════════════
# deploy.sh — Deploy personal-agent to remote server via SSH
#
# Usage:
#   ./deploy.sh              # Full deploy (build + transfer + launch)
#   ./deploy.sh build-only   # Only build and transfer image
#   ./deploy.sh start        # Only (re)start containers on server
#   ./deploy.sh logs         # Tail agent logs on server
#   ./deploy.sh status       # Check container status
#   ./deploy.sh ssh          # Open SSH session to server
# ═══════════════════════════════════════════════════════════════════════════════

set -euo pipefail

# ── Configuration ────────────────────────────────────────────────────────────
REMOTE_USER="danilo"
REMOTE_HOST="192.168.100.18"
REMOTE_DIR="/home/${REMOTE_USER}/personal-agent"
IMAGE_NAME="personal-agent-agent"
ARCHIVE="personal-agent-image.tar.gz"
SSH_OPTS="-o ConnectTimeout=10 -o ServerAliveInterval=30"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m'

log()  { echo -e "${GREEN}[DEPLOY]${NC} $1"; }
warn() { echo -e "${YELLOW}[WARN]${NC} $1"; }
err()  { echo -e "${RED}[ERROR]${NC} $1" >&2; }

ssh_cmd() {
    ssh ${SSH_OPTS} "${REMOTE_USER}@${REMOTE_HOST}" "$@"
}

scp_cmd() {
    scp ${SSH_OPTS} "$@"
}

# ── Functions ────────────────────────────────────────────────────────────────

check_connection() {
    log "Testing SSH connection to ${REMOTE_USER}@${REMOTE_HOST} ..."
    if ! ssh_cmd "echo 'Connection OK'"; then
        err "Cannot connect to ${REMOTE_HOST}. Check SSH config."
        exit 1
    fi
}

build_image() {
    log "Building Docker image locally ..."
    docker compose build

    log "Saving image to ${ARCHIVE} ..."
    docker save "${IMAGE_NAME}:latest" | gzip > "${ARCHIVE}"
    local size
    size=$(du -h "${ARCHIVE}" | cut -f1)
    log "Image archive: ${size}"
}

transfer_files() {
    log "Creating remote directory ${REMOTE_DIR} ..."
    ssh_cmd "mkdir -p ${REMOTE_DIR}/{vault,profiles,logs}"

    log "Transferring image archive ..."
    scp_cmd "${ARCHIVE}" "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

    log "Transferring docker-compose.yml and .env ..."
    scp_cmd docker-compose.yml "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"
    scp_cmd .env "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/"

    # Transfer browser profiles if they exist
    if [ -d "./profiles" ] && [ "$(ls -A ./profiles 2>/dev/null)" ]; then
        log "Transferring browser profiles ..."
        scp_cmd -r ./profiles/* "${REMOTE_USER}@${REMOTE_HOST}:${REMOTE_DIR}/profiles/"
    else
        warn "No browser profiles found in ./profiles — you'll need to create them later."
    fi
}

load_and_start() {
    log "Loading image on remote server ..."
    ssh_cmd "cd ${REMOTE_DIR} && docker load < ${ARCHIVE}"

    log "Stopping old containers (if running) ..."
    ssh_cmd "cd ${REMOTE_DIR} && docker compose down 2>/dev/null || true"

    log "Starting containers ..."
    ssh_cmd "cd ${REMOTE_DIR} && docker compose up -d"

    log "Waiting 10s for services to initialize ..."
    sleep 10

    log "Container status:"
    ssh_cmd "cd ${REMOTE_DIR} && docker compose ps"
}

show_logs() {
    ssh_cmd "cd ${REMOTE_DIR} && docker compose logs -f --tail=50 agent"
}

show_status() {
    ssh_cmd "cd ${REMOTE_DIR} && docker compose ps && echo '---' && docker compose logs --tail=5 agent"
}

cleanup_local() {
    if [ -f "${ARCHIVE}" ]; then
        log "Cleaning up local archive ..."
        rm -f "${ARCHIVE}"
    fi
}

# ── Main ─────────────────────────────────────────────────────────────────────

ACTION="${1:-deploy}"

case "${ACTION}" in
    deploy)
        check_connection
        build_image
        transfer_files
        load_and_start
        cleanup_local
        log "✓ Deployment complete! Agent is running on ${REMOTE_HOST}"
        log "  View logs: ./deploy.sh logs"
        log "  Status:    ./deploy.sh status"
        log "  Vault:     ${REMOTE_DIR}/vault/Agent-Research/"
        ;;
    build-only)
        build_image
        check_connection
        transfer_files
        cleanup_local
        log "✓ Image transferred. Run './deploy.sh start' to launch."
        ;;
    start)
        check_connection
        load_and_start
        ;;
    logs)
        check_connection
        show_logs
        ;;
    status)
        check_connection
        show_status
        ;;
    ssh)
        ssh ${SSH_OPTS} "${REMOTE_USER}@${REMOTE_HOST}"
        ;;
    stop)
        check_connection
        ssh_cmd "cd ${REMOTE_DIR} && docker compose down"
        log "✓ Containers stopped."
        ;;
    *)
        echo "Usage: $0 {deploy|build-only|start|stop|logs|status|ssh}"
        exit 1
        ;;
esac

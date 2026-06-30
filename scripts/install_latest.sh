#!/bin/bash
set -euo pipefail

INSTALL_DIR="/opt/adsbledmatrix"
REPO="BChenery/adsbledmatrix"
API_URL="https://api.github.com/repos/${REPO}/releases/latest"
SERVICE_USER="adsb"
LOG_FILE="/var/log/adsbledmatrix-update.log"
HEALTH_URL="http://127.0.0.1:8080/api/health"

log() {
    echo "[$(date -Iseconds)] $*" | tee -a "$LOG_FILE"
}

if [ "$(id -u)" -ne 0 ]; then
    log "This script must be run as root"
    exit 1
fi

mkdir -p "$(dirname "$LOG_FILE")"
touch "$LOG_FILE"

if [ -d "${INSTALL_DIR}/venv" ]; then
    MODE="update"
    log "Detected existing install; running in update mode"
else
    MODE="fresh"
    log "No existing venv found; running in fresh-install mode"
fi

fetch_release() {
    cd /tmp
    LATEST=$(curl -s "$API_URL" | python3 -c "import sys,json; print(json.load(sys.stdin)['tag_name'])")
    log "Latest release: $LATEST"

    ARCHIVE="adsbledmatrix-${LATEST}.tar.gz"
    CHECKSUM="${ARCHIVE}.sha256"
    BASE_URL="https://github.com/${REPO}/releases/download/${LATEST}"

    curl -L -o "$ARCHIVE" "$BASE_URL/$ARCHIVE"
    curl -L -o "$CHECKSUM" "$BASE_URL/$CHECKSUM"
    sha256sum -c "$CHECKSUM"

    rm -rf /tmp/adsbledmatrix
    tar -xzf "$ARCHIVE" -C /tmp
}

ensure_service_user() {
    if ! id -u "$SERVICE_USER" >/dev/null 2>&1; then
        log "Creating ${SERVICE_USER} user"
        useradd -r -s /usr/sbin/nologin "$SERVICE_USER" || useradd -r -s /bin/false "$SERVICE_USER"
    fi
}

install_os_deps() {
    log "Installing OS dependencies"
    export DEBIAN_FRONTEND=noninteractive
    apt-get update
    apt-get install -y \
        python3 \
        python3-venv \
        python3-dev \
        python3-pip \
        libssl-dev \
        libffi-dev \
        build-essential \
        git \
        curl
}

build_rgb_matrix() {
    local python_bin="$1"
    log "Building rpi-rgb-led-matrix Python bindings"
    local rgb_dir="/tmp/rpi-rgb-led-matrix"
    if [ ! -d "$rgb_dir" ]; then
        git clone --depth 1 https://github.com/hzeller/rpi-rgb-led-matrix.git "$rgb_dir"
    fi
    cd "$rgb_dir/bindings/python"
    make build-python PYTHON="$python_bin"
    make install-python PYTHON="$python_bin"
}

ensure_venv_and_requirements() {
    if [ ! -d "${INSTALL_DIR}/venv" ]; then
        log "Creating Python venv"
        python3 -m venv "${INSTALL_DIR}/venv"
    fi
    log "Installing/updating Python requirements"
    "${INSTALL_DIR}/venv/bin/pip" install --upgrade pip
    "${INSTALL_DIR}/venv/bin/pip" install -r "${INSTALL_DIR}/backend/requirements.txt"
}

ensure_rgbmatrix() {
    if "${INSTALL_DIR}/venv/bin/python3" -c "import rgbmatrix" 2>/dev/null; then
        log "rgbmatrix already installed"
        return 0
    fi
    build_rgb_matrix "${INSTALL_DIR}/venv/bin/python3"
}

install_or_update_code() {
    if [ "$MODE" = "fresh" ]; then
        log "Copying release to ${INSTALL_DIR}"
        mkdir -p "$INSTALL_DIR"
        rm -rf "${INSTALL_DIR:?}/"*
        cp -a /tmp/adsbledmatrix/. "$INSTALL_DIR/"
    else
        BACKUP_DIR="${INSTALL_DIR}-backup-$(date +%Y%m%d%H%M%S)"
        log "Backing up current install to $BACKUP_DIR"
        cp -a "$INSTALL_DIR" "$BACKUP_DIR"

        log "Updating files in $INSTALL_DIR (preserving venv, .env, and SQLite DBs)"
        rsync -a --delete \
            --exclude='venv' \
            --exclude='.env' \
            --exclude='*.db' \
            --exclude='*.sqlite' \
            --exclude='*.sqlite3' \
            /tmp/adsbledmatrix/ "$INSTALL_DIR/"
    fi
}

install_systemd_units() {
    log "Installing systemd units"
    cp "${INSTALL_DIR}/systemd/"*.service /etc/systemd/system/ 2>/dev/null || true
    cp "${INSTALL_DIR}/systemd/"*.timer /etc/systemd/system/ 2>/dev/null || true
    systemctl daemon-reload
    systemctl enable adsbledmatrix.service || true
    systemctl enable adsbledmatrix-update.timer || true
    systemctl enable adsbledmatrix-update.service || true
    systemctl enable readsb.service 2>/dev/null || true
}

fix_ownership() {
    log "Setting ownership"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/venv"
    chown -R "${SERVICE_USER}:${SERVICE_USER}" "${INSTALL_DIR}/data"
    chown -R root:root "${INSTALL_DIR}/backend" "${INSTALL_DIR}/hardware" "${INSTALL_DIR}/scripts" "${INSTALL_DIR}/systemd" "${INSTALL_DIR}/docs" 2>/dev/null || true
    chown root:root "${INSTALL_DIR}/README.md" "${INSTALL_DIR}/VERSION" 2>/dev/null || true
}

wait_for_health() {
    local timeout_secs=120
    local interval=5
    local elapsed=0
    while [ "$elapsed" -lt "$timeout_secs" ]; do
        if curl -s --max-time 3 "$HEALTH_URL" | grep -q '"status":"ok"'; then
            log "Health check passed"
            return 0
        fi
        sleep "$interval"
        elapsed=$((elapsed + interval))
    done
    log "Health check failed after ${timeout_secs}s"
    return 1
}

rollback() {
    if [ -z "${BACKUP_DIR:-}" ] || [ ! -d "$BACKUP_DIR" ]; then
        log "No backup available for rollback"
        return 1
    fi
    log "Rolling back from $BACKUP_DIR"
    systemctl stop adsbledmatrix.service || true
    rm -rf "${INSTALL_DIR:?}/"*
    cp -a "${BACKUP_DIR}/." "$INSTALL_DIR/"
    fix_ownership
    systemctl start adsbledmatrix.service || true
    if wait_for_health; then
        log "Rollback succeeded"
        return 0
    else
        log "Rollback failed"
        return 1
    fi
}

prune_backups() {
    log "Pruning old backups (keeping last 2)"
    ls -1dt "${INSTALL_DIR}-backup-"* 2>/dev/null | tail -n +3 | xargs -r rm -rf
}

main() {
    fetch_release

    if [ "$MODE" = "fresh" ]; then
        ensure_service_user
        install_os_deps
        install_or_update_code
        ensure_venv_and_requirements
        ensure_rgbmatrix
        install_systemd_units
    else
        install_or_update_code
        ensure_venv_and_requirements
        ensure_rgbmatrix
        install_systemd_units
    fi

    fix_ownership

    log "Starting services"
    systemctl start adsbledmatrix.service || true
    systemctl start readsb.service 2>/dev/null || true

    if wait_for_health; then
        log "Install/update completed successfully"
        if [ "$MODE" = "update" ]; then
            prune_backups
        fi
    else
        log "Install/update failed health check"
        if [ "$MODE" = "update" ]; then
            rollback
        fi
        exit 1
    fi
}

main "$@"

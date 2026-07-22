#!/usr/bin/env bash
set -Eeuo pipefail

readonly SCRIPT_DIR="$(cd -- "$(dirname -- "${BASH_SOURCE[0]}")" && pwd)"
readonly DEFAULT_APP_DIR="$(cd -- "$SCRIPT_DIR/.." && pwd)"

APP_DIR="${APP_DIR:-$DEFAULT_APP_DIR}"
APP_USER="${APP_USER:-$(stat -c '%U' "$APP_DIR")}"
APP_GROUP="${APP_GROUP:-$(id -gn "$APP_USER")}"
VENV_DIR="${VENV_DIR:-$APP_DIR/.venv}"
SERVER_NAME="${SERVER_NAME:-}"

readonly ENV_FILE="/etc/watch-yellow-house.env"
readonly STATIC_DIR="/var/www/watch-yellow-house/static"
readonly PREVIEW_DIR="/var/lib/watch-yellow-house/previews"
readonly DJANGO_UNIT="watch-yellow-house-django.service"
readonly YOLO_UNIT="watch-yellow-house-yolo.service"
readonly NGINX_SITE="watch-yellow-house.conf"

log() {
    printf '[deploy] %s\n' "$*"
}

fail() {
    printf '[deploy] ERROR: %s\n' "$*" >&2
    exit 1
}

elevate_if_needed() {
    if [[ $EUID -eq 0 ]]; then
        return
    fi
    command -v sudo >/dev/null 2>&1 || fail "sudo is required to install services."
    log "Requesting sudo access for deployment"
    exec sudo -- env \
        APP_DIR="$APP_DIR" \
        APP_USER="$APP_USER" \
        APP_GROUP="$APP_GROUP" \
        VENV_DIR="$VENV_DIR" \
        SERVER_NAME="$SERVER_NAME" \
        bash "$SCRIPT_DIR/deploy.sh"
}

detect_server_names() {
    [[ -z "$SERVER_NAME" ]] || return

    if [[ -r "$APP_DIR/.env" ]]; then
        SERVER_NAME="$(
            sed -n 's/^DJANGO_ALLOWED_HOSTS=//p' "$APP_DIR/.env" \
                | head -n 1 \
                | tr ',' ' '
        )"
    elif [[ -r "$ENV_FILE" ]]; then
        SERVER_NAME="$(
            sed -n 's/^DJANGO_ALLOWED_HOSTS=//p' "$ENV_FILE" \
                | head -n 1 \
                | tr ',' ' '
        )"
    fi

    if [[ -z "$SERVER_NAME" ]]; then
        local hostname_value
        local ipv4_values
        hostname_value="$(hostname -f 2>/dev/null || hostname)"
        ipv4_values="$(
            { hostname -I 2>/dev/null || true; } \
                | tr ' ' '\n' \
                | sed -n '/^[0-9][0-9.]*$/p' \
                | tr '\n' ' '
        )"
        SERVER_NAME="$hostname_value $ipv4_values"
    fi

    SERVER_NAME="$(printf '%s' "$SERVER_NAME" | xargs)"
    [[ -n "$SERVER_NAME" ]] || fail "Could not detect a hostname or IPv4 address."
}

validate_configuration() {
    [[ -n "$SERVER_NAME" ]] || fail \
        "SERVER_NAME is required (a domain name or server IP address)."
    [[ "$APP_DIR" == /* ]] || fail "APP_DIR must be an absolute path."
    [[ "$VENV_DIR" == /* ]] || fail "VENV_DIR must be an absolute path."
    [[ "$APP_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "APP_DIR contains unsupported characters."
    [[ "$VENV_DIR" =~ ^/[A-Za-z0-9._/-]+$ ]] || fail "VENV_DIR contains unsupported characters."
    [[ "$APP_USER" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || fail "Invalid APP_USER."
    [[ "$APP_GROUP" =~ ^[A-Za-z_][A-Za-z0-9_-]*$ ]] || fail "Invalid APP_GROUP."
    [[ "$SERVER_NAME" =~ ^[-A-Za-z0-9._\ ]+$ ]] || fail "Invalid SERVER_NAME."
    [[ -f "$APP_DIR/manage.py" ]] || fail "manage.py was not found in APP_DIR."
    [[ -f "$APP_DIR/requirements.txt" ]] || fail "requirements.txt was not found."
    [[ -f "$APP_DIR/.env" ]] || fail \
        "Create $APP_DIR/.env from .env.example before deploying."
    grep -q '^DJANGO_SECRET_KEY=..' "$APP_DIR/.env" || fail \
        "DJANGO_SECRET_KEY must be set in $APP_DIR/.env."
    grep -q '^DJANGO_ALLOWED_HOSTS=..' "$APP_DIR/.env" || fail \
        "DJANGO_ALLOWED_HOSTS must be set in $APP_DIR/.env."
    id "$APP_USER" >/dev/null 2>&1 || fail "APP_USER does not exist."
}

ensure_system_packages() {
    local packages=()
    command -v nginx >/dev/null 2>&1 || packages+=(nginx)
    command -v openssl >/dev/null 2>&1 || packages+=(openssl)
    command -v ffmpeg >/dev/null 2>&1 || packages+=(ffmpeg)
    command -v python3 >/dev/null 2>&1 || packages+=(python3 python3-venv)
    if command -v python3 >/dev/null 2>&1 && ! python3 -c 'import venv' 2>/dev/null; then
        packages+=(python3-venv)
    fi

    if (( ${#packages[@]} > 0 )); then
        log "Installing required system packages: ${packages[*]}"
        apt-get update
        DEBIAN_FRONTEND=noninteractive apt-get install -y "${packages[@]}"
    fi

    command -v nginx >/dev/null 2>&1 || fail "nginx installation failed."
    command -v openssl >/dev/null 2>&1 || fail "openssl is required."
    command -v ffmpeg >/dev/null 2>&1 || fail "ffmpeg is required."
    command -v runuser >/dev/null 2>&1 || fail "runuser is required."
    command -v systemctl >/dev/null 2>&1 || fail "systemd is required."
    [[ -d /run/systemd/system ]] || fail "This machine is not booted with systemd."
    getent group www-data >/dev/null 2>&1 || fail "The Nginx www-data group is missing."
    command -v nvidia-smi >/dev/null 2>&1 || fail "The NVIDIA driver is required."
    nvidia-smi >/dev/null 2>&1 || fail "The NVIDIA GPU is not available."
}

run_as_app() {
    runuser -u "$APP_USER" -- "$@"
}

prepare_application() {
    if [[ ! -x "$VENV_DIR/bin/python" ]]; then
        log "Creating Python virtual environment"
        run_as_app python3 -m venv "$VENV_DIR"
    fi

    log "Installing Python requirements"
    run_as_app "$VENV_DIR/bin/python" -m pip install -r "$APP_DIR/requirements.txt"

    log "Applying database migrations"
    run_as_app "$VENV_DIR/bin/python" "$APP_DIR/manage.py" migrate --noinput

    log "Collecting static files"
    install -d -m 0755 -o "$APP_USER" -g www-data "$STATIC_DIR"
    run_as_app env DJANGO_DEBUG=false DJANGO_STATIC_ROOT="$STATIC_DIR" \
        "$VENV_DIR/bin/python" "$APP_DIR/manage.py" collectstatic --noinput

    log "Running Django deployment checks"
    run_as_app env \
        DJANGO_DEBUG=false \
        DJANGO_SECRET_KEY=deployment-check-only \
        DJANGO_ALLOWED_HOSTS="${SERVER_NAME// /,}" \
        "$VENV_DIR/bin/python" "$APP_DIR/manage.py" check --deploy

    [[ -f "$APP_DIR/models/yolo26x.pt" ]] || log \
        "WARNING: yolo26x.pt is absent and will be downloaded on first use."
}

install_environment() {
    local temp_env
    temp_env="$(mktemp -t watch-yellow-house-env.XXXXXXXX)"

    log "Updating $ENV_FILE from $APP_DIR/.env"
    chmod 0600 "$APP_DIR/.env"
    install -m 0600 "$APP_DIR/.env" "$temp_env"
    {
        printf '\n# Production overrides managed by deploy.sh\n'
        printf 'DJANGO_DEBUG=false\n'
        printf 'DJANGO_STATIC_ROOT=%s\n' "$STATIC_DIR"
        printf 'YOLO_PREVIEW_ROOT=%s\n' "$PREVIEW_DIR"
    } >> "$temp_env"
    install -d -m 0750 -o "$APP_USER" -g www-data "$PREVIEW_DIR"
    install -m 0600 "$temp_env" "$ENV_FILE"
    unlink "$temp_env"
}

render_template() {
    local source="$1"
    local destination="$2"
    sed \
        -e "s|@@APP_DIR@@|$APP_DIR|g" \
        -e "s|@@APP_USER@@|$APP_USER|g" \
        -e "s|@@APP_GROUP@@|$APP_GROUP|g" \
        -e "s|@@VENV_DIR@@|$VENV_DIR|g" \
        -e "s|@@SERVER_NAME@@|$SERVER_NAME|g" \
        -e "s|@@STATIC_DIR@@|$STATIC_DIR|g" \
        "$source" > "$destination"
}

install_configuration() {
    local temp_dir
    temp_dir="$(mktemp -d -t watch-yellow-house-deploy.XXXXXXXX)"

    render_template "$SCRIPT_DIR/systemd/$DJANGO_UNIT" "$temp_dir/$DJANGO_UNIT"
    render_template "$SCRIPT_DIR/systemd/$YOLO_UNIT" "$temp_dir/$YOLO_UNIT"
    render_template "$SCRIPT_DIR/nginx/$NGINX_SITE" "$temp_dir/$NGINX_SITE"

    log "Installing systemd unit files"
    install -m 0644 "$temp_dir/$DJANGO_UNIT" "/etc/systemd/system/$DJANGO_UNIT"
    install -m 0644 "$temp_dir/$YOLO_UNIT" "/etc/systemd/system/$YOLO_UNIT"

    log "Installing Nginx site"
    install -m 0644 "$temp_dir/$NGINX_SITE" "/etc/nginx/sites-available/$NGINX_SITE"
    ln -sfn "/etc/nginx/sites-available/$NGINX_SITE" \
        "/etc/nginx/sites-enabled/$NGINX_SITE"

    nginx -t
    rm -r -- "$temp_dir"
}

activate_services() {
    log "Reloading systemd and enabling reboot persistence"
    systemctl daemon-reload
    systemctl enable --now nginx
    systemctl enable "$DJANGO_UNIT" "$YOLO_UNIT"
    systemctl restart "$DJANGO_UNIT"
    systemctl restart "$YOLO_UNIT"
    systemctl reload nginx
}

main() {
    elevate_if_needed
    detect_server_names
    validate_configuration
    ensure_system_packages
    prepare_application
    install_environment
    install_configuration
    activate_services

    log "Deployment complete: http://${SERVER_NAME%% *}/"
    log "Django logs: journalctl -u $DJANGO_UNIT -f"
    log "YOLO logs:   journalctl -u $YOLO_UNIT -f"
}

main "$@"

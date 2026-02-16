#!/usr/bin/env bash
source /dev/stdin <<< "$FUNCTIONS_FILE_PATH"
color
verb_ip6
catch_errors

APP="AI Agents Hub"
APP_DIR="/opt/ai-agents-hub"
DATA_DIR="/var/lib/ai-agents-hub"
CONFIG_DIR="/etc/ai-agents-hub"
SERVICE_NAME="ai-agents-hub"
REPO_URL="${REPO_URL:-https://github.com/zigamilek/ai-agents-hub.git}"
REPO_REF="${REPO_REF:-master}"

if [[ "${VERBOSE:-no}" == "yes" ]]; then
  set -x
  msg_info "Verbose mode enabled: full installer output active."
fi

msg_info "Updating package index"
$STD apt-get update
msg_ok "Updated package index"

msg_info "Installing dependencies"
$STD apt-get install -y git python3 python3-venv python3-pip rsync ca-certificates curl
msg_ok "Installed dependencies"

msg_info "Creating service user"
if ! id -u aihub >/dev/null 2>&1; then
  $STD useradd --system --home "${APP_DIR}" --shell /usr/sbin/nologin aihub
fi
msg_ok "Service user ready"

msg_info "Preparing directories"
$STD mkdir -p "${APP_DIR}" "${DATA_DIR}/memories" "${DATA_DIR}/obsidian" "${CONFIG_DIR}/prompts/specialists" /var/log/ai-agents-hub
msg_ok "Directories prepared"

msg_info "Cloning repository"
if [[ -d "${APP_DIR}/.git" ]]; then
  $STD rm -rf "${APP_DIR}"
fi
if [[ -n "${REPO_REF}" && "${REPO_REF}" != "HEAD" ]]; then
  $STD git clone --depth 1 --branch "${REPO_REF}" "${REPO_URL}" "${APP_DIR}"
else
  $STD git clone --depth 1 "${REPO_URL}" "${APP_DIR}"
fi
msg_ok "Repository cloned"

msg_info "Building Python environment"
$STD python3 -m venv "${APP_DIR}/.venv"
$STD "${APP_DIR}/.venv/bin/pip" install --upgrade pip
$STD "${APP_DIR}/.venv/bin/pip" install -e "${APP_DIR}"
msg_ok "Python environment ready"

msg_info "Installing configuration"
if [[ ! -f "${CONFIG_DIR}/config.yaml" ]]; then
  $STD cp "${APP_DIR}/config.yaml" "${CONFIG_DIR}/config.yaml"
fi
if [[ ! -f "${CONFIG_DIR}/ai-agents-hub.env" ]]; then
  cat <<'EOF' > "${CONFIG_DIR}/ai-agents-hub.env"
OPENAI_API_KEY=
GEMINI_API_KEY=
AI_AGENTS_HUB_API_KEY=change-me
EOF
fi
$STD chmod 600 "${CONFIG_DIR}/ai-agents-hub.env"

for prompt_file in "${APP_DIR}/prompts/specialists/"*.md; do
  prompt_name="$(basename "${prompt_file}")"
  [[ -f "${CONFIG_DIR}/prompts/specialists/${prompt_name}" ]] || $STD cp "${prompt_file}" "${CONFIG_DIR}/prompts/specialists/${prompt_name}"
done
msg_ok "Configuration installed"

msg_info "Installing systemd service"
$STD cp "${APP_DIR}/deploy/systemd/ai-agents-hub.service" "/etc/systemd/system/${SERVICE_NAME}.service"

msg_info "Applying ownership"
$STD chown -R aihub:aihub "${APP_DIR}" "${DATA_DIR}" "${CONFIG_DIR}" /var/log/ai-agents-hub
msg_ok "Ownership applied"

$STD systemctl daemon-reload
$STD systemctl enable -q --now "${SERVICE_NAME}"
msg_ok "Service installed and started"

msg_ok "Installation complete"
msg_ok "Run 'ai-agents-hub onboard' to configure keys and settings."

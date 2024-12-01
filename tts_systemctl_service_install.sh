#!/bin/bash
# install.sh

set -e

SCRIPT_DIR=$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)
SERVICE_NAME="piper-tts-service"
VENV_PATH="${SCRIPT_DIR}/.venv"
LOG_DIR="/var/log/piper-tts"

# Create service file
cat > /tmp/${SERVICE_NAME}.service << EOF
[Unit]
Description=Piper TTS Service
After=network.target sound.target

[Service]
Type=simple
User=$USER
Group=$USER
WorkingDirectory=${SCRIPT_DIR}
Environment=PATH=${VENV_PATH}/bin:/usr/local/sbin:/usr/local/bin:/usr/sbin:/usr/bin
Environment=PYTHONUNBUFFERED=1

# Performance optimizations
Nice=-10
IOSchedulingClass=realtime
IOSchedulingPriority=0
CPUSchedulingPolicy=fifo
CPUSchedulingPriority=99
CPUQuota=80%

# Audio access
SupplementaryGroups=audio gpio

ExecStart=${VENV_PATH}/bin/python ${SCRIPT_DIR}/piper_tts_service.py
Restart=always
RestartSec=5

# Security
PrivateTmp=true
ProtectSystem=full
NoNewPrivileges=false

[Install]
WantedBy=multi-user.target
EOF

# Create systemd override
mkdir -p /etc/systemd/system/${SERVICE_NAME}.service.d/
cat > /etc/systemd/system/${SERVICE_NAME}.service.d/override.conf << EOF
[Service]
LimitRTPRIO=infinity
LimitNICE=-20
LimitMEMLOCK=infinity
EOF

# Install python3-full and setup venv
sudo apt install -y python3-full
python3 -m venv ${VENV_PATH}
source ${VENV_PATH}/bin/activate
${VENV_PATH}/bin/pip install -r ${SCRIPT_DIR}/requirements.txt

# Setup log directory
sudo mkdir -p ${LOG_DIR}
sudo chown $USER:$USER ${LOG_DIR}

# Install service
sudo mv /tmp/${SERVICE_NAME}.service /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable ${SERVICE_NAME}
sudo systemctl start ${SERVICE_NAME}

echo "Installation complete. Check status with: systemctl status ${SERVICE_NAME}"
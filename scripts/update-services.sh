#!/bin/bash
cat > /etc/systemd/system/hermes.service << 'EOF'
[Unit]
Description=Hermes Gateway
After=network.target

[Service]
User=laia-arch
WorkingDirectory=/home/laia-arch/LAIA/.laia-arch
ExecStart=/home/laia-arch/LAIA/.laia-arch/venv/bin/hermes gateway run
Restart=always
RestartSec=5
Environment=HOME=/home/laia-arch
Environment=HERMES_HOME=/home/laia-arch/LAIA

[Install]
WantedBy=multi-user.target
EOF

cat > /etc/systemd/system/workspace-ui.service << 'EOF'
[Unit]
Description=Workspace UI (LAIA)
After=network.target hermes.service

[Service]
User=laia-arch
WorkingDirectory=/home/laia-arch/LAIA/.laia-arch/workspace-ui/backend
ExecStart=/home/laia-arch/LAIA/.laia-arch/venv/bin/uvicorn main:app --host 0.0.0.0 --port 8077
Restart=always
RestartSec=5
Environment=HOME=/home/laia-arch
Environment=HERMES_HOME=/home/laia-arch/LAIA
Environment=HERMES_VENV=/home/laia-arch/LAIA/.laia-arch/venv

[Install]
WantedBy=multi-user.target
EOF

systemctl daemon-reload
echo "Servicios actualizados OK"

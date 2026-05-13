#!/usr/bin/env bash
cd /home/laia-hermes/LAIA/services/agora-backend
exec .venv/bin/uvicorn app.main:app --host 0.0.0.0 --port 8088

#!/bin/bash
# Script para que Hermes inicie los servidores MLX (visión + TTS)
# Uso: bash ~/.hermes/scripts/start_mlx_servers.sh

set -e

DIR="$HOME/.hermes/mlx-servers"
LOG="$HOME/.hermes/logs/mlx_servers.log"

if [ ! -d "$DIR/.venv" ]; then
  echo "ERROR: El entorno MLX no existe. Ejecuta primero: cd $DIR && ./setup.sh"
  exit 1
fi

mkdir -p "$DIR/logs"

# Verificar si ya están corriendo
if curl -s http://localhost:8080/v1/models > /dev/null 2>&1; then
  echo "VISION server ya esta corriendo en puerto 8080"
else
  echo "Iniciando servidor de vision..."
  "$DIR/.venv/bin/python" -m mlx_vlm.server \
    --model "mlx-community/Qwen2.5-VL-3B-Instruct-4bit" \
    --port 8080 \
    >> "$DIR/logs/vision.log" 2>&1 &
  echo "VISION server iniciado (PID $!)"
fi

if curl -s --max-time 2 http://localhost:8081/v1/audio/speech > /dev/null 2>&1; then
  echo "TTS server ya esta corriendo en puerto 8081"
else
  echo "Iniciando servidor TTS..."
  "$DIR/.venv/bin/python" -m mlx_audio.server \
    --port 8081 \
    >> "$DIR/logs/tts.log" 2>&1 &
  echo "TTS server iniciado (PID $!)"
fi

echo "Listo. Revisando estado..."
sleep 2
curl -s http://localhost:8080/v1/models | python3 -c "import sys,json; d=json.load(sys.stdin); print('VISION OK:', [m['id'] for m in d.get('data',[])])" 2>/dev/null || echo "VISION: esperando..."
echo "TTS: corriendo en http://localhost:8081"
echo "Logs: $DIR/logs/"

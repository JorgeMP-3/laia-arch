# MLX Local Servers (Vision + TTS)

Gestión de los servidores MLX locales para visión y síntesis de voz en el Mac mini.

## Estado actual

Los servidores MLX ya están configurados y funcionando:
- **Visión:** `http://localhost:8080/v1/chat/completions` — modelo `mlx-community/Qwen2.5-VL-3B-Instruct-4bit`
- **TTS:** `http://localhost:8081/v1/audio/speech` — modelo `mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit`

## Config en `~/.hermes/config.yaml`

```yaml
auxiliary:
  vision:
    provider: custom
    model: mlx-community/Qwen2.5-VL-3B-Instruct-4bit
    base_url: http://localhost:8080/v1
    api_key: local
    timeout: 120

tts:
  provider: openai
  openai:
    model: mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit
    voice: default
    base_url: http://localhost:8081/v1
```

## Scripts disponibles

| Script | Función |
|--------|---------|
| `~/.hermes/mlx-servers/start_all.sh` | Inicia visión + TTS con Qwen3-VL-8B |
| `~/.hermes/mlx-servers/start_vision.sh [modelo] [puerto]` | Solo servidor visión |
| `~/.hermes/mlx-servers/start_tts.sh [puerto]` | Solo servidor TTS |
| `~/.hermes/mlx-servers/stop_all.sh` | Detiene ambos |
| `~/.hermes/mlx-servers/status.sh` | Muestra estado |
| `~/.hermes/scripts/start_mlx_servers.sh` | Para Hermes: inicia ambos verificando si ya están corriendo |

## Iniciar servidores (lo que Hermes ejecuta)

```bash
bash ~/.hermes/scripts/start_mlx_servers.sh
```

## Verificar que funcionan

```bash
# Visión
curl -s http://localhost:8080/v1/models | python3 -c "import sys,json; print([m['id'] for m in json.load(sys.stdin)['data']])"

# TTS
curl -s --max-time 2 http://localhost:8081/v1/audio/speech > /dev/null && echo "TTS OK" || echo "TTS no responde"
```

## Si los servidores no responden

1. Ver logs: `tail -f ~/.hermes/mlx-servers/logs/vision.log` / `tts.log`
2. Reinciar: `bash ~/.hermes/mlx-servers/stop_all.sh && bash ~/.hermes/scripts/start_mlx_servers.sh`
3. Si modelo no existe: descargar con `~/.hermes/mlx-servers/.venv/bin/mlx_lm.download mlx-community/Qwen2.5-VL-3B-Instruct-4bit`

## Nota sobre modelos

- Visión por defecto: `Qwen2.5-VL-3B-Instruct-4bit` (más rápido que el 8B)
- Para mejor calidad, cambiar a `Qwen3-VL-8B-Instruct-4bit` en start_vision.sh
- TTS: `Qwen3-TTS-12Hz-0.6B-Base-4bit` es rápido y razonable en calidad

---
name: mlx-servers
description: Manage local MLX inference servers for vision (Qwen2.5-VL, port 8080) and TTS (Qwen3-TTS, port 8081). Start, stop, restart or check status.
version: 1.1.0
---

# MLX Servers Manager

Use this skill when the user asks to start, stop, restart or check the status of the local MLX vision or TTS servers.

## Server locations
- **Vision**: `http://localhost:8080/v1/chat/completions` — Qwen2.5-VL-3B-Instruct-4bit
- **TTS**: `http://localhost:8081/v1/audio/speech` — Qwen3-TTS-12Hz-0.6B-Base-4bit
- **Scripts**: `~/.hermes/mlx-servers/`
- **Logs**: `~/.hermes/mlx-servers/logs/`

## Agent workflow

The agent can manage servers using these scripts via `terminal()`:

### To START servers:
```bash
bash ~/.hermes/mlx-servers/start_servers.sh
```

### To STOP servers:
```bash
bash ~/.hermes/mlx-servers/stop_servers.sh
```

### To CHECK status:
```bash
bash ~/.hermes/mlx-servers/status_servers.sh
```

### To RESTART servers:
```bash
bash ~/.hermes/mlx-servers/restart_servers.sh
```

## Hermes config reference
Hermes `~/.hermes/config.yaml` points to these servers:
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

## Quick API test
Test vision:
```bash
curl -s http://localhost:8080/v1/chat/completions \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen2.5-VL-3B-Instruct-4bit","messages":[{"role":"user","content":"hello"}],"max_tokens":20}'
```

Test TTS:
```bash
curl -s -X POST http://localhost:8081/v1/audio/speech \
  -H "Content-Type: application/json" \
  -d '{"model":"mlx-community/Qwen3-TTS-12Hz-0.6B-Base-4bit","input":"test","voice":"default"}' \
  --output /tmp/test.mp3 && afplay /tmp/test.mp3
```

## Troubleshooting
- If servers won't start: check logs in `~/.hermes/mlx-servers/logs/`
- If Hermes can't reach servers: verify ports 8080 and 8081 are free
- To change models: modify `start_servers.sh` and restart servers

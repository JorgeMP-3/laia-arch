# Hermes Core — Voice System

## Metadata

- ID: `79`
- Slug: `hermes-core-voice-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-voice-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:24:30.114224+00:00`
- Updated at: `2026-05-08T08:24:30.114224+00:00`
- Aliases: `hermes-core-voice-detail`

## Summary

Voice mode: captura de audio, STT con Whisper, TTS multi-provider y soporte Termux/gateway

## Body

# Hermes Core — Voice System

Voice mode para CLI con captura de audio, STT, y TTS playback.

## voice_mode.py (1017 líneas)

### Dependencies Opcionales
- sounddevice + numpy (PortAudio)
- Install: pip install sounddevice numpy o pip install hermes-agent[voice]

### Lazy Audio Imports
Audio libs nunca se importan a nivel módulo:
```python
def _import_audio():
    import sounddevice as sd
    import numpy as np
    return sd, np
```
Previene crashes en headless (SSH, Docker, WSL).

### Audio Detection
_audio_available() — True si sounddevice + numpy disponibles
_is_termux_environment() — Termux-specific handling

### Termux Support
- termux-microphone-record command
- Termux API app detection
- pkg install python-numpy portaudio && python -m pip install sounddevice

## Voice Capture

- Push-to-talk recording
- WAV encoding (stdlib wave)
- Temporary file cleanup
- Thread-safe capture

## STT Dispatch

tools/transcription_tools.py:
- Whisper (OpenAI) — general-purpose speech recognition
- Fallback providers
- Supports local y cloud Whisper endpoints

## TTS Playback

tools/tts_tool.py:
- Edge TTS (default, Nous subscription)
- Nous TTS
- Gemini TTS
- Mistral TTS
- speed control

### TTS Config (config.yaml)
```yaml
auxiliary:
  tts:
    provider: edge   # edge, nous, gemini, mistral
    voice: en-US-AriaNeural
    speed: 1.0
```

### Lazy Import
TTS libs no se importan hasta que se necesitan (headless-safe)

## Voice in Gateway

gateway/platforms/ — voice channel support:
- Discord voice
- Telegram voice messages
- Platform-specific audio handling

## Integration Points

- voice_mode tool: push-to-talk en CLI
- transcription_tools tool: audio → text
- tts_tool tool: text → speech
- send_message_tool: platform-specific voice response

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Voice System

# Hermes Core — Voice System

Voice mode para CLI con captura de audio, STT, y TTS playback.

## voice_mode.py (1017 líneas)

### Dependencies Opcionales
- sounddevice + numpy (PortAudio)
- Install: pip install sounddevice numpy o pip install hermes-agent[voice]

### Lazy Audio Imports
Audio libs nunca se importan a nivel módulo:
```python
def _import_audio():
    import sounddevice as sd
    import numpy as np
    return sd, np
```
Previene crashes en headless (SSH, Docker, WSL).

### Audio Detection
_audio_available() — True si sounddevice + numpy disponibles
_is_termux_environment() — Termux-specific handling

### Termux Support
- termux-microphone-record command
- Termux API app detection
- pkg install python-numpy portaudio && python -m pip install sounddevice

## Voice Capture

- Push-to-talk recording
- WAV encoding (stdlib wave)
- Temporary file cleanup
- Thread-safe capture

## STT Dispatch

tools/transcription_tools.py:
- Whisper (OpenAI) — general-purpose speech recognition
- Fallback providers
- Supports local y cloud Whisper endpoints

## TTS Playback

tools/tts_tool.py:
- Edge TTS (default, Nous subscription)
- Nous TTS
- Gemini TTS
- Mistral TTS
- speed control

### TTS Config (config.yaml)
```yaml
auxiliary:
  tts:
    provider: edge   # edge, nous, gemini, mistral
    voice: en-US-AriaNeural
    speed: 1.0
```

### Lazy Import
TTS libs no se importan hasta que se necesitan (headless-safe)

## Voice in Gateway

gateway/platforms/ — voice channel support:
- Discord voice
- Telegram voice messages
- Platform-specific audio handling

## Integration Points

- voice_mode tool: push-to-talk en CLI
- transcription_tools tool: audio → text
- tts_tool tool: text → speech
- send_message_tool: platform-specific voice response

> 📅 Documentado: 2026-05-08

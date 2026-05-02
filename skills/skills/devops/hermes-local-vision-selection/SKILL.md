---
name: hermes-local-vision-selection
description: Choose a lightweight local vision model for Hermes on resource-constrained Macs and know when to prefer local vision over cloud vision.
version: 1.1.0
---

# Hermes local vision selection

Use this when the user wants Hermes to analyze images locally on a Mac mini or other resource-constrained machine.

## What actually worked on a 16 GB Mac mini
- **Moondream** is the light default for local image understanding.
- **Qwen2.5VL 3B** is the better option when the image contains lots of text, screenshots, UI, or documents.
- The exact Ollama tags that worked were:
  - `moondream:latest`
  - `qwen2.5vl:3b`
- The Ollama library page for Qwen2.5-VL exposes the official family tag as `qwen2.5vl` with sub-tags like `3b`, `7b`, `32b`, and `72b`.
- Avoid inventing tags like `qwen2.5-vl:3b-instruct`; that tag did not exist in Ollama and failed to pull.

## MLX vision option that worked
- **MLX-VLM** can be used with Hermes via an OpenAI-compatible shim server.
- Public Hugging Face repos that worked/verified for Qwen2.5-VL MLX:
  - `mlx-community/Qwen2.5-VL-3B-Instruct-4bit`
  - `mlx-community/Qwen2.5-VL-7B-Instruct-4bit`
- On a 16 GB Mac mini, start with **7B 4bit only if you are okay with slower startup and more RAM pressure**; otherwise use 3B 4bit.
- `mlx_vlm.generate` works as a CLI, but Hermes needs an OpenAI-style endpoint. A tiny FastAPI + uvicorn shim can expose `/v1/models` and `/v1/chat/completions` backed by `mlx_vlm`.
- Working local endpoint pattern:
```bash
python3 ~/.hermes/scripts/mlx_vision_server.py
# serves at http://127.0.0.1:8000/v1
```
- Hermes config pattern for MLX vision:
```yaml
auxiliary:
  vision:
    provider: custom
    model: mlx-community/Qwen2.5-VL-7B-Instruct-4bit
    base_url: http://127.0.0.1:8000/v1
    api_key: mlx-local
```
- This is **MLX**, not GGUF. Ollama remains GGUF-only.
- A Hugging Face 401 on a different repo/model did **not** mean MLX was broken; it meant that specific repo/path was not accessible as used.

## Vision confirmed working (April 2026)
- Backend: Ollama `qwen2.5vl:7b` at `http://127.0.0.1:11434/v1`
- Hermes vision config:
```yaml
auxiliary:
  vision:
    provider: custom
    model: qwen2.5vl:7b
    base_url: http://127.0.0.1:11434/v1
    api_key: ollama-local
    timeout: 120
```
- Latency: ~15-20 seconds per image. Do NOT optimize — this is acceptable.
- Procedure: use `vision_analyze` tool with `image_url` (local path in `/home/familiamp/.hermes/image_cache/`) and `question` in Spanish.
- MLX path was tried and abandoned (failed with "Only returning PyTorch tensors is currently supported"). Ollama is the stable path.
- Model auto-downloads on first use.


## Selection heuristic
- If the machine has about **2 GB free RAM or less**, choose the smallest practical vision model.
- If the user cares about responsiveness and stability, choose the lightest model that still answers image questions adequately.
- If the image is mostly natural scene understanding, use **Moondream** first.
- If the image contains dense text, screens, dialogs, or forms, use **Qwen2.5VL 3B** first.
- Avoid 7B+ vision models on 16 GB Macs unless you have verified memory headroom.

## Memory and disk guidance
- **Moondream** is lightweight and suitable as the default fallback.
- **Qwen2.5VL 7B** also pulls successfully in Ollama in this environment.
- The 7B pull downloaded about **6.0 GB** of model data, so expect a much larger footprint than 3B.

## Configuration pattern for Hermes
- Point Hermes vision at local Ollama when cloud vision is unavailable or undesirable.
- Working config pattern:
```yaml
auxiliary:
  vision:
    provider: custom
    model: qwen2.5vl:3b
    base_url: http://127.0.0.1:11434/v1
    api_key: ollama-local
```
- Use `moondream:latest` instead of `qwen2.5vl:3b` when you want the lightest fallback.

## MLX path that worked in this environment
- MLX vision models are usable through **`mlx-vlm`**, but Hermes needs a small local OpenAI-compatible server wrapper; `mlx_vlm.generate` alone is only a CLI.
- The public MLX repo that worked in this setup was:
  - `mlx-community/Qwen2.5-VL-7B-Instruct-4bit`
- A minimal local server wrapper can expose `/v1/models` and `/v1/chat/completions` on `http://127.0.0.1:8000/v1` and call `mlx_vlm.utils.load(...)/generate(...)` under the hood.
- First load may take a long time because Hugging Face cache downloads can sit in `~/.cache/huggingface/hub` and create `.incomplete` blobs until complete.
- The first inference on Qwen2.5-VL-7B MLX required installing both **PyTorch** and **torchvision** in the Python used by the server; without them, `AutoVideoProcessor` failed during model load.
- After installing dependencies, the server needed a **restart** before the imports were visible to the running process.
- Once loaded, the model endpoint responded and the process RSS was about ~1.1 GB, which is manageable on a 16 GB Mac mini.

## Verification checklist
- Confirm the local model is installed and listed by Ollama (`ollama list`).
- Run a quick image description test on a sample image.
- Test a text-heavy screenshot separately from a natural photo.
- Check that the model can answer in the user’s language.
- Watch for memory pressure or swapping after the first inference.
- For MLX specifically: verify `/v1/models` responds, then send a tiny image request and watch the server log for processor/import errors.

## Pitfalls
- Don’t assume cloud vision is available just because chat works.
- Don’t load a large vision model on a 16 GB machine without checking other resident processes.
- Don’t assume a tag from another registry or blog post exists in Ollama.
- If the user wants on-device processing, explicitly choose the local model path and avoid accidental cloud fallback.
- For MLX vision servers, missing `torchvision` or `torch` can surface as `AutoVideoProcessor` import errors on the first request; install them and restart the server.
- If the server returns 500 on the first request, check the process log before changing the model — the failure may be dependency-related rather than model-related.
- If the user decides to abandon MLX, clean up the wrapper script, uninstall `mlx`/`mlx-vlm`/`mlx-metal`, restore Hermes to Ollama, and verify no MLX cache or background server is left behind.

## Rollback to Ollama after MLX experiments
Use this when the MLX route is unstable, not worth the extra complexity, or the user explicitly wants a clean return to Ollama.

1. Restore Hermes vision config to Ollama, e.g.:
```yaml
auxiliary:
  vision:
    provider: custom
    model: qwen2.5vl:7b
    base_url: http://127.0.0.1:11434/v1
    api_key: ollama-local
```
2. Stop the MLX server process if it is still running.
3. Remove the local wrapper script, for example `~/.hermes/scripts/mlx_vision_server.py`.
4. Uninstall MLX-related Python packages from the active Python environment:
```bash
python3 -m pip uninstall -y mlx-vlm mlx mlx-metal torchvision
```
5. Remove the MLX Hugging Face cache directory if the user wants no leftover model files.
6. Verify the cleanup:
   - Hermes config points to Ollama, not `http://127.0.0.1:8000/v1`
   - `python3 -m pip list` no longer shows MLX packages
   - no MLX wrapper script remains in `~/.hermes/scripts/`
   - Ollama vision still answers image requests

## Good defaults
- For a Mac mini with 16 GB RAM, use **Moondream** as the light default.
- For screenshots, OCR-ish tasks, and text-heavy images, use **Qwen2.5VL 3B** as the stronger local option.
- If the user explicitly wants MLX and can tolerate a slower startup, **Qwen2.5-VL-7B-Instruct-4bit** is a good local choice after the wrapper/server is in place.

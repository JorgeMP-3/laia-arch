# Hermes Core — Vision System

## Metadata

- ID: `78`
- Slug: `hermes-core-vision-detail`
- Kind: `doc`
- Status: `active`
- Filename: `hermes-core-vision-detail.md`
- Parent: `hermes-core-components`
- Source kind: `manual`
- Created at: `2026-05-08T08:24:21.438346+00:00`
- Updated at: `2026-05-08T08:24:21.438346+00:00`
- Aliases: `hermes-core-vision-detail`

## Summary

Sistema de visión: vision_analyze, image generation, browser vision y routing de providers

## Body

# Hermes Core — Vision System

Sistema de visión con análisis de imágenes y generación.

## vision_tools.py (794 líneas)

### vision_analyze_tool
Analiza imágenes desde URLs:
- Download image → base64 para API compatibility
- Custom user prompts
- Comprehensive image description
- Context-aware analysis
- Automatic temp file cleanup
- Debug logging support

### Image URL Validation
_validate_image_url() — basic URL format validation
Only http/https schemes allowed.

### Download Security
- _VISION_DOWNLOAD_TIMEOUT = 30s default (configurable via config o env)
- _VISION_MAX_DOWNLOAD_BYTES = 50MB — previene OOM from decompression bombs
- HTTP timeout enforcement

### Routing (auxiliary_client.py)
Centralized vision router selecciona:
- OpenRouter
- Nous
- Codex
- Native Anthropic (Claude vision)
- Custom OpenAI-compatible endpoint

## image_generation_tool.py

Stable Diffusion image generation:
- FAL provider (Nous subscription)
- Text-to-image con prompts
- Style options
- Resolution control

## Browser Vision

browser_tool.py + browser_cdp_tool.py:
- browser_vision — vision_analyze en page completo
- browser_get_images — extrae imágenes de page
- CDP (Chrome DevTools Protocol) para browser automation

### Camofox Provider
browser_camofox.py:
- headless browser automation
- State persistence
- Cloud fallback

## Vision Config

```yaml
auxiliary:
  vision:
    provider: openrouter  # openrouter, nous, anthropic, openai, custom
    model: Llama-3.2-90B-Vision
    download_timeout: 30
```

## Vision Tool Schemas

Available tools:
- vision_analyze — analyze image from URL
- image_generate — generate image from text
- browser_vision — analyze current browser page
- browser_get_images — extract images from page

## Usage Example

```python
result = await vision_analyze_tool(
    image_url="https://example.com/photo.jpg",
    user_prompt="What architectural style is this?"
)
```

> 📅 Documentado: 2026-05-08

## Relaciones salientes

- _(sin relaciones salientes)_

## Relaciones entrantes

- `contains` ← `hermes-core-components` (Hermes Core Components) [peso=1.00]

## Artefactos asociados

- _(sin artefactos asociados)_

## Render Markdown

# Hermes Core — Vision System

# Hermes Core — Vision System

Sistema de visión con análisis de imágenes y generación.

## vision_tools.py (794 líneas)

### vision_analyze_tool
Analiza imágenes desde URLs:
- Download image → base64 para API compatibility
- Custom user prompts
- Comprehensive image description
- Context-aware analysis
- Automatic temp file cleanup
- Debug logging support

### Image URL Validation
_validate_image_url() — basic URL format validation
Only http/https schemes allowed.

### Download Security
- _VISION_DOWNLOAD_TIMEOUT = 30s default (configurable via config o env)
- _VISION_MAX_DOWNLOAD_BYTES = 50MB — previene OOM from decompression bombs
- HTTP timeout enforcement

### Routing (auxiliary_client.py)
Centralized vision router selecciona:
- OpenRouter
- Nous
- Codex
- Native Anthropic (Claude vision)
- Custom OpenAI-compatible endpoint

## image_generation_tool.py

Stable Diffusion image generation:
- FAL provider (Nous subscription)
- Text-to-image con prompts
- Style options
- Resolution control

## Browser Vision

browser_tool.py + browser_cdp_tool.py:
- browser_vision — vision_analyze en page completo
- browser_get_images — extrae imágenes de page
- CDP (Chrome DevTools Protocol) para browser automation

### Camofox Provider
browser_camofox.py:
- headless browser automation
- State persistence
- Cloud fallback

## Vision Config

```yaml
auxiliary:
  vision:
    provider: openrouter  # openrouter, nous, anthropic, openai, custom
    model: Llama-3.2-90B-Vision
    download_timeout: 30
```

## Vision Tool Schemas

Available tools:
- vision_analyze — analyze image from URL
- image_generate — generate image from text
- browser_vision — analyze current browser page
- browser_get_images — extract images from page

## Usage Example

```python
result = await vision_analyze_tool(
    image_url="https://example.com/photo.jpg",
    user_prompt="What architectural style is this?"
)
```

> 📅 Documentado: 2026-05-08

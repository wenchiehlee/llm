# llm

Unified LLM client library supporting **Gemini API** (round-robin key rotation), **Codex-API-Server** (ChatGPT Pro bridge), and **MLX** (local Apple Silicon inference), with optional **Amplitude** analytics.

## Features

- **Auto fallback chain**: `codex → gemini → mlx`
- **Gemini multi-key rotation**: Supports up to 20 keys with daily quota handling and round-robin selection.
- **Local MLX inference**: High-performance inference via `MLX-API-Server` (e.g., `Qwen3.5-9B`, `Gemma-4`).
- **Amplitude Analytics**: Automatic tracking of every `llm_call` (provider, model, duration, tokens, etc.).
- **JSON Mode**: Native support for structured data extraction across all providers.
- **Prompt Validation**: Integrated safety check for prompt length (max 20,000 characters).

---

## Installation

### Option A — Local path (NAS / local dev)

```toml
# pyproject.toml
dependencies = [
    "llm @ file:///${PROJECT_ROOT}/../llm",
]
```

Or with uv:
```bash
uv add --editable "../llm"
```

### Option B — GitHub URL (CI/CD, GitHub Actions)

```toml
# pyproject.toml
dependencies = [
    "llm @ git+https://github.com/wenchiehlee/llm.git",
]
```

---

## Environment Variables

Copy `.env.example` to `.env`. **Important: Avoid using `#` characters in API keys as they may be interpreted as comments.**

```env
# Gemini — primary key + up to 19 rotation keys (GEMINI_API_KEY_1 … GEMINI_API_KEY_19)
GEMINI_API_KEY=AIza...
GEMINI_API_KEY_1=AIza...
# GEMINI_SKIP_KEYS=GEMINI_API_KEY_7

# Codex-API-Server (Mac-mini / Synology NAS)
CODEX_API_URL=https://api.wenchiehlee.synology.me:8443
SERVER_API_KEY=your-key-without-hash

# MLX-API-Server (Mac-mini / Apple Silicon)
MLX_API_URL=http://mac-mini.local:5001
MLX_SERVER_API_KEY=your-mlx-key
# MLX_MODEL=mlx-qwen3

# Amplitude (optional)
AMPLITUDE_API_KEY=your-amplitude-key
LLM_APP_NAME=my-app-name
```

---

## Usage

```python
from llm import LLMClient

# Auto-detect providers (default fallback: codex → gemini → mlx)
client = LLMClient(app_name="MyApp")

# Plain text response
text = client.generate("分析台積電近期新聞...")

# JSON response (returns a dict or list)
data = client.generate_json("分析此公司並以 JSON 格式回傳：{score: 0-5, reason: str}")

# Override provider/model per call
text = client.generate(prompt, provider="gemini", model="gemini-2.0-flash")

# Inspect last call metadata
print(f"Used {client.last_provider} ({client.last_model})")
```

---

## Testing & Verification

You can verify the integration with `CodexAPIServer` using the provided test script:

```bash
python test_codex.py
```

This script checks:
- Connection to the Codex API Server.
- `SERVER_API_KEY` authentication.
- Plain text and JSON mode generation.

---

## Providers

| Provider | Model (Default) | Requirements |
|----------|-----------------|--------------|
| `codex` | `chatgpt-pro` | `CODEX_API_URL` + `SERVER_API_KEY` |
| `gemini` | `gemini-2.5-flash` | `GEMINI_API_KEY` (supports rotation) |
| `mlx` | `mlx-qwen3` / `mlx-gemma4` | `MLX_API_URL` + `MLX_SERVER_API_KEY` |

---

## Amplitude Events (`llm_call`)

| Property | Description |
|----------|-------------|
| `provider` | `gemini` / `codex` / `mlx` |
| `model` | The specific model name used |
| `key_used` | The env var name (e.g., `GEMINI_API_KEY_3`) |
| `success` | `true` / `false` |
| `duration_sec` | Response time in seconds |
| `app_name` | Identifier from `LLM_APP_NAME` |

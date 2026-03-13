# llm

Unified LLM client library supporting **Gemini API** (with round-robin key rotation) and **Codex-API-Server** (Mac-mini ChatGPT Pro bridge), with optional **Amplitude** analytics.

## Features

- Auto fallback chain: `codex → gemini`
- Gemini multi-key round-robin rotation with daily quota handling
- Single `llm_call` Amplitude event per request (provider, model, input preview, output preview, duration)
- Prompt length validation (8,000 chars max)
- Silent degradation when Amplitude key is absent

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

Then:
```bash
uv sync
# or: pip install -e .
```

### Optional: Amplitude support

```bash
uv add amplitude-analytics
# or: pip install amplitude-analytics
```

---

## Environment Variables

Copy `.env.example` to `.env` and fill in:

```env
# Gemini — primary key + up to 19 rotation keys
GEMINI_API_KEY=AIza...
GEMINI_API_KEY_1=AIza...
GEMINI_API_KEY_2=AIza...
# Pre-skip exhausted keys (comma-separated env var names)
# GEMINI_SKIP_KEYS=GEMINI_API_KEY_7

# Codex-API-Server (Mac-mini)
CODEX_API_URL=https://your-server/exec
CODEX_API_KEY=your-key

# Amplitude (optional — omit to disable tracking)
AMPLITUDE_API_KEY=your-amplitude-key

# App name shown in Amplitude user_id
LLM_APP_NAME=your-app-name
```

---

## Usage

```python
from llm import LLMClient

# Auto-detect providers (codex → gemini fallback)
client = LLMClient(app_name="MyApp")

# Select provider at init
client = LLMClient(providers=["gemini"])
client = LLMClient(providers=["codex", "gemini"])  # explicit fallback order

# Select Gemini model at init
client = LLMClient(model="gemini-2.0-flash")
client = LLMClient(providers=["gemini"], model="gemini-2.5-pro")

# Plain text response
text = client.generate("分析台積電近期新聞...")

# JSON response (parsed automatically)
data = client.generate_json("回傳 JSON：{score: 0-5, reason: str}")

# Override provider / model per call (without rebuilding client)
text = client.generate(prompt, provider="gemini")
text = client.generate(prompt, model="gemini-2.0-flash")
text = client.generate(prompt, provider="gemini", model="gemini-2.5-pro")
data = client.generate_json(prompt, provider="gemini", model="gemini-2.0-flash")
```

---

## Provider Selection Logic

```
CODEX_API_URL + CODEX_API_KEY set?  ──yes──► use Codex first
                                     ──no───► skip Codex
GEMINI_API_KEY set?                 ──yes──► use Gemini
                                     ──no───► skip Gemini
No providers available?             ──────► raise RuntimeError
```

If Codex fails at runtime, automatically falls back to Gemini.

---

## Amplitude Events

Each `generate()` / `generate_json()` call emits one `llm_call` event:

| Property | Example |
|----------|---------|
| `provider` | `gemini` / `codex` |
| `model` | `gemini-2.5-flash` / `chatgpt-pro` |
| `input_preview` | first 100 chars of prompt |
| `output_preview` | first 100 words of response |
| `duration_ms` | `1843` |
| `success` | `true` / `false` |
| `error_type` | `rate_limit` / `auth_error` / `timeout` / ... |
| `app_name` | value of `LLM_APP_NAME` |

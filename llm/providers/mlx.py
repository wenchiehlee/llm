"""MLX-API-Server provider — HTTP client for Mac-mini MLX inference server."""
from __future__ import annotations

import logging
import os
import re

import httpx

from . import BaseProvider

logger = logging.getLogger(__name__)

_CONNECT_TIMEOUT = 10
_READ_TIMEOUT    = 900   # MLX 大模型推理最長 15 分鐘

_MODEL_ALIASES = {
    "mlx-qwen3":  "mlx-community/Qwen3.5-9B-MLX-4bit",
    "qwen3-mlx":  "mlx-community/Qwen3.5-9B-MLX-4bit",
    "mlx-gemma4": "mlx-community/gemma-4-31b-it-4bit",
}


def _parse_mlx_output(raw: str) -> str:
    """Extract clean answer from mlx_lm output.

    mlx_lm output format:
        ==========
        Thinking Process: ...
        </think>

        ANSWER HERE
        ==========
        Prompt: X tokens, ...
    """
    # Strip trailing stats block (==========\nPrompt: ...)
    raw = re.sub(r"\n=+\nPrompt:.*$", "", raw, flags=re.DOTALL).strip()
    # Strip leading ========== separator
    raw = re.sub(r"^=+\n", "", raw).strip()
    # Strip thinking section up to and including </think>
    if "</think>" in raw:
        raw = raw.split("</think>", 1)[1].strip()
    return raw


class MLXProvider(BaseProvider):
    name = "mlx"

    def __init__(self, model: str | None = None, url: str | None = None, api_key: str | None = None):
        self.url     = (url     or os.getenv("MLX_API_URL",        "")).rstrip("/")
        self.api_key = api_key  or os.getenv("MLX_SERVER_API_KEY", "")
        if not self.url:
            raise RuntimeError("Missing env var: MLX_API_URL (e.g. http://mac-mini.tail28f10.ts.net:5001)")
        if not self.api_key:
            raise RuntimeError("Missing env var: MLX_SERVER_API_KEY")

        alias = model or os.getenv("MLX_MODEL", "mlx-qwen3")
        self.model      = alias
        self.model_repo = _MODEL_ALIASES.get(alias, alias)

    def generate(self, prompt: str, *, json_mode: bool = False, max_tokens: int = 8192) -> str:
        if json_mode:
            prompt = prompt + "\n\nRespond with valid JSON only, no markdown fences, no explanation."

        payload: dict = {"prompt": prompt, "model": self.model}

        resp = httpx.post(
            f"{self.url}/exec",
            json=payload,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT,
                                  write=_CONNECT_TIMEOUT, pool=_CONNECT_TIMEOUT),
        )
        resp.raise_for_status()
        raw = resp.json().get("output", "")
        return _parse_mlx_output(raw)

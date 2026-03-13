"""Codex-API-Server provider（Mac-mini Flask bridge to ChatGPT Pro）。"""
from __future__ import annotations

import logging
import os

import httpx

from . import BaseProvider

logger = logging.getLogger(__name__)

MAX_PROMPT_LENGTH = 20_000  # 與 Codex-API-Server CODEX_MAX_PROMPT_LENGTH 一致
_CONNECT_TIMEOUT = 10       # 連線建立上限（秒）
_READ_TIMEOUT = 180         # codex exec 最長執行時間（秒）


class CodexProvider(BaseProvider):
    name = "codex"
    model = "chatgpt-pro"

    def __init__(self, url: str | None = None, api_key: str | None = None):
        self.url = (url or os.getenv("CODEX_API_URL", "")).rstrip("/")
        self.api_key = api_key or os.getenv("CODEX_API_KEY", "")
        if not self.url:
            raise RuntimeError("Missing env var: CODEX_API_URL")
        if not self.api_key:
            raise RuntimeError("Missing env var: CODEX_API_KEY")

    def generate(self, prompt: str, *, json_mode: bool = False, max_tokens: int = 8192) -> str:
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"Prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")

        # json_mode 透過獨立欄位傳遞，不拼接進 prompt（避免 prompt injection）
        payload: dict = {"prompt": prompt, "json_mode": json_mode}

        resp = httpx.post(
            f"{self.url}/exec",
            json=payload,
            headers={"X-API-Key": self.api_key, "Content-Type": "application/json"},
            timeout=httpx.Timeout(connect=_CONNECT_TIMEOUT, read=_READ_TIMEOUT,
                                  write=_CONNECT_TIMEOUT, pool=_CONNECT_TIMEOUT),
        )
        resp.raise_for_status()
        return resp.json().get("output", "")

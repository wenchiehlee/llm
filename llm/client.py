"""Unified LLM client with provider fallback chain."""
from __future__ import annotations

import json
import logging
import os
from typing import Sequence

from .providers import BaseProvider
from .analytics.amplitude import LLMCallTracker, configure as amplitude_configure

logger = logging.getLogger(__name__)

_DEFAULT_CHAIN = ["codex", "gemini"]  # 優先順序
MAX_PROMPT_LENGTH = 20_000


def _build_provider(name: str) -> BaseProvider:
    if name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider()
    if name == "codex":
        from .providers.codex import CodexProvider
        return CodexProvider()
    raise ValueError(f"Unknown provider: {name}")


def _detect_available(chain: list[str]) -> list[BaseProvider]:
    providers: list[BaseProvider] = []
    for name in chain:
        try:
            providers.append(_build_provider(name))
        except RuntimeError as e:
            logger.debug("跳過 %s（%s）", name, e)
    return providers


class LLMClient:
    """
    使用方式：
        from llm import LLMClient
        client = LLMClient()                               # 自動偵測
        client = LLMClient(providers=["gemini"])           # 強制指定
        client = LLMClient(app_name="GoogleAlertManager")  # Amplitude app 名稱
    """

    def __init__(
        self,
        providers: Sequence[str] | None = None,
        app_name: str | None = None,
    ):
        chain = list(providers) if providers else _DEFAULT_CHAIN
        self._providers = _detect_available(chain)
        if not self._providers:
            raise RuntimeError(f"沒有可用的 LLM provider（嘗試過：{chain}）")
        logger.info(
            "LLMClient 初始化，可用 provider：%s",
            ", ".join(p.name for p in self._providers),
        )
        amplitude_configure(app_name or os.getenv("LLM_APP_NAME", "llm"))

    def generate(self, prompt: str, *, max_tokens: int = 8192) -> str:
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt 不能為空")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")
        last_exc: Exception | None = None
        for provider in self._providers:
            tracker = LLMCallTracker(provider.name, provider.model, prompt)
            with tracker:
                try:
                    result = provider.generate(prompt, max_tokens=max_tokens)
                    tracker.result = result
                    tracker.key_used = getattr(provider, "last_key_used", "")
                    return result
                except Exception as e:
                    logger.warning("%s 失敗，嘗試下一個 provider：%s", provider.name, e)
                    last_exc = e
        raise RuntimeError("所有 provider 均失敗") from last_exc

    def generate_json(self, prompt: str, *, max_tokens: int = 8192) -> dict | list:
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt 不能為空")
        if len(prompt) > MAX_PROMPT_LENGTH:
            raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")
        last_exc: Exception | None = None
        for provider in self._providers:
            tracker = LLMCallTracker(provider.name, provider.model, prompt)
            with tracker:
                try:
                    text = provider.generate(prompt, json_mode=True, max_tokens=max_tokens)
                    tracker.result = text
                    tracker.key_used = getattr(provider, "last_key_used", "")
                    return json.loads(text)
                except json.JSONDecodeError as e:
                    logger.warning("%s 回傳非 JSON：%s", provider.name, e)
                    last_exc = e
                except Exception as e:
                    logger.warning("%s 失敗：%s", provider.name, e)
                    last_exc = e
        raise RuntimeError("所有 provider 均失敗") from last_exc

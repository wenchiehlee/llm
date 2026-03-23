"""Unified LLM client with provider fallback chain."""
from __future__ import annotations

import json
import logging
import os
from typing import Sequence

from .providers import BaseProvider
from .analytics.amplitude import LLMCallTracker, configure as amplitude_configure

logger = logging.getLogger(__name__)

_DEFAULT_CHAIN = ["codex", "gemini", "mlx"]  # 優先順序：codex → gemini → mlx(本機)
MAX_PROMPT_LENGTH = 30_000


def _build_provider(name: str, model: str | None = None) -> BaseProvider:
    if name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model=model)
    if name == "codex":
        from .providers.codex import CodexProvider
        return CodexProvider()
    if name == "mlx":
        from .providers.mlx import MLXProvider
        return MLXProvider(model=model)
    raise ValueError(f"Unknown provider: {name}")


def _detect_available(chain: list[str], model: str | None = None) -> list[BaseProvider]:
    providers: list[BaseProvider] = []
    for name in chain:
        try:
            providers.append(_build_provider(name, model=model))
        except RuntimeError as e:
            logger.debug("跳過 %s（%s）", name, e)
    return providers


class LLMClient:
    """
    使用方式：
        from llm import LLMClient

        # 自動偵測 provider（codex → gemini）
        client = LLMClient()

        # 指定 provider
        client = LLMClient(providers=["gemini"])
        client = LLMClient(providers=["codex", "gemini"])

        # 指定 Gemini 模型
        client = LLMClient(model="gemini-2.0-flash")
        client = LLMClient(providers=["gemini"], model="gemini-2.5-pro")

        # Amplitude app 名稱
        client = LLMClient(app_name="GoogleAlertManager")

    呼叫時也可臨時覆寫 provider / model：
        client.generate(prompt, provider="gemini", model="gemini-2.0-flash")
    """

    def __init__(
        self,
        providers: Sequence[str] | None = None,
        model: str | None = None,
        app_name: str | None = None,
    ):
        self._chain = list(providers) if providers else _DEFAULT_CHAIN
        self._default_model = model
        self._providers = _detect_available(self._chain, model=model)
        if not self._providers:
            raise RuntimeError(f"沒有可用的 LLM provider（嘗試過：{self._chain}）")
        self.last_provider: str = self._providers[0].name  # updated after each successful call
        logger.info(
            "LLMClient 初始化，可用 provider：%s",
            ", ".join(p.name for p in self._providers),
        )
        amplitude_configure(app_name or os.getenv("LLM_APP_NAME", "llm"))

    def _resolve_providers(self, provider: str | None, model: str | None) -> list[BaseProvider]:
        """若呼叫時指定 provider/model，臨時建立；否則使用預設清單。"""
        if provider is None and model is None:
            return self._providers
        chain = [provider] if provider else self._chain
        override = _detect_available(chain, model=model or self._default_model)
        if not override:
            raise RuntimeError(f"指定的 provider '{provider}' 不可用")
        return override

    def generate(
        self,
        prompt: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """
        Args:
            prompt:   輸入文字
            provider: 臨時指定 provider（"gemini" / "codex"），覆寫初始化設定
            model:    臨時指定模型（如 "gemini-2.0-flash"），僅對 gemini 有效
            max_tokens: 最大輸出 token 數
        """
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt 不能為空")

        providers = self._resolve_providers(provider, model)
        if len(prompt) > MAX_PROMPT_LENGTH:
            p = providers[0]
            with LLMCallTracker(p.name, p.model, prompt):
                raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")

        last_exc: Exception | None = None
        for p in providers:
            try:
                with LLMCallTracker(p.name, p.model, prompt) as tracker:
                    result = p.generate(prompt, max_tokens=max_tokens)
                    tracker.result = result
                    tracker.key_used = getattr(p, "last_key_used", "")
                    self.last_provider = p.name
                    return result
            except Exception as e:
                logger.warning("%s 失敗，嘗試下一個 provider：%s", p.name, e)
                last_exc = e
        raise RuntimeError("所有 provider 均失敗") from last_exc

    def generate_json(
        self,
        prompt: str,
        *,
        provider: str | None = None,
        model: str | None = None,
        max_tokens: int = 8192,
    ) -> dict | list:
        """同 generate()，但自動解析 JSON 回傳。"""
        if not prompt or not isinstance(prompt, str):
            raise ValueError("prompt 不能為空")

        providers = self._resolve_providers(provider, model)
        if len(prompt) > MAX_PROMPT_LENGTH:
            p = providers[0]
            with LLMCallTracker(p.name, p.model, prompt):
                raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")

        last_exc: Exception | None = None
        for p in providers:
            try:
                with LLMCallTracker(p.name, p.model, prompt) as tracker:
                    text = p.generate(prompt, json_mode=True, max_tokens=max_tokens)
                    tracker.result = text
                    tracker.key_used = getattr(p, "last_key_used", "")
                    self.last_provider = p.name
                    return json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning("%s 回傳非 JSON：%s", p.name, e)
                last_exc = e
            except Exception as e:
                logger.warning("%s 失敗：%s", p.name, e)
                last_exc = e
        raise RuntimeError("所有 provider 均失敗") from last_exc

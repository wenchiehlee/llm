"""Unified LLM client with provider fallback chain."""
from __future__ import annotations

import json
import logging
import os
from typing import Sequence

from .providers import BaseProvider
from .analytics.amplitude import LLMCallTracker, configure as amplitude_configure
from .routing import RoutingManager

logger = logging.getLogger(__name__)

_DEFAULT_CHAIN = ["codex", "gemini", "mlx"]  # 優先順序：codex → gemini → mlx(本機)
MAX_PROMPT_LENGTH = 20_000


def _build_provider(name: str, model: str | None = None) -> BaseProvider:
    if name == "gemini":
        from .providers.gemini import GeminiProvider
        return GeminiProvider(model=model)
    if name == "codex":
        from .providers.codex import CodexProvider
        return CodexProvider(model=model)
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
        routing_file: str | None = None,
        min_samples: int = 10,
        threshold: float = 0.8,
    ):
        self._chain = list(providers) if providers else _DEFAULT_CHAIN
        self._default_model = model
        self._providers = _detect_available(self._chain, model=model)
        if not self._providers:
            raise RuntimeError(f"沒有可用的 LLM provider（嘗試過：{self._chain}）")
        self.last_provider: str = self._providers[0].name  # updated after each successful call
        self.last_model: str = self._providers[0].model
        self.last_model_repo: str = getattr(self._providers[0], "model_repo", "")

        self.routing = RoutingManager(routing_file, min_samples=min_samples, threshold=threshold)

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

    def generate_smart(
        self,
        task_name: str,
        prompt: str,
        *,
        draft_provider: str = "mlx",
        draft_model: str | None = None,
        judge_provider: str | None = None,
        judge_model: str | None = None,
        max_tokens: int = 8192,
    ) -> str:
        """
        智慧路由模式：
        1. 檢查 task_name 是否已達標 (晉升至 draft_provider)。
        2. 若已達標：直接呼叫 draft_provider 並回傳。
        3. 若未達標：
           a. 呼叫 draft_provider 取得草稿。
           b. 將草稿送給強大模型 (Gemini/Codex) 評審。
           c. 若評審回傳 "OK"，紀錄成功並回傳草稿。
           d. 若評審回傳其他內容，紀錄失敗並回傳該內容 (重新生成的答案)。
        """
        promoted = self.routing.get_promoted_provider(task_name)

        # 狀態 A: 已達標，且達標的 provider 正是我們這次要求的 draft_provider
        if promoted == draft_provider:
            try:
                return self.generate(prompt, provider=draft_provider, model=draft_model, max_tokens=max_tokens)
            except Exception as e:
                logger.warning("SmartRoute [%s] %s 失敗，退回標準流程: %s", task_name, draft_provider, e)
                return self.generate(prompt, max_tokens=max_tokens)

        # 狀態 B: 評估階段 (Judging) 或達標 provider 不同

        # --- 效能優化 (Server-Side Smart Routing) ---
        # 如果 draft_provider 是 codex，且未指定特定評審者，
        # 我們優先將整個「草稿+評審」流程交給 NAS 伺服器端處理，以消除網路延遲。
        if draft_provider == "codex" and judge_provider is None:
            try:
                codex_p = next((p for p in self._providers if p.name == "codex"), None)
                if codex_p and hasattr(codex_p, "generate_smart"):
                    # 使用伺服器預設的評審邏輯 (gemini-cli -> gemini-cli)
                    result = codex_p.generate_smart(
                        task_name, prompt, model=draft_model, max_tokens=max_tokens
                    )
                    self.last_provider = getattr(codex_p, "last_provider_used", "codex")
                    return result
            except Exception as e:
                logger.warning("SmartRoute [%s] Server-side 失敗，退回 Client-side: %s", task_name, e)

        # --- 標準流程 (Client-Side Smart Routing) ---
        # 1. 取得草稿
        draft_result = ""
        try:
            draft_result = self.generate(prompt, provider=draft_provider, model=draft_model, max_tokens=max_tokens)
        except Exception as e:
            logger.warning("SmartRoute [%s] 評估階段 %s 取得失敗: %s", task_name, draft_provider, e)
            self.routing.record(task_name, success=False, provider=draft_provider)
            return self.generate(prompt, max_tokens=max_tokens)

        # 2. 準備評審 Prompt
        judge_prompt = (
            f"你是評審員。以下是使用者的問題與本地模型的回答。\n"
            f"如果本地模型的回答已經達到你的水準（正確、完整且格式正確），請回覆：OK\n"
            f"如果本地模型的回答不夠好，請直接回覆你認為正確的完整答案。\n\n"
            f"問題：{prompt}\n"
            f"本地回答：{draft_result}"
        )

        # 3. 挑選強大模型進行評審
        strong_provider = judge_provider
        if not strong_provider:
            for p in self._providers:
                # 避開直接呼叫 API 的 gemini，優先選擇 codex (NAS CLI)，以節省 API 配額
                if p.name not in ("mlx", "gemini"):
                    strong_provider = p.name
                    break
            # 若沒找到 codex，才勉強用其他非 mlx 的 (可能是 gemini API)
            if not strong_provider:
                for p in self._providers:
                    if p.name != "mlx":
                        strong_provider = p.name
                        break

        if not strong_provider:
            logger.error("SmartRoute [%s] 找不到可用於評審的強大模型", task_name)
            return draft_result

        judge_response = self.generate(
            judge_prompt,
            provider=strong_provider,
            model=judge_model,
            max_tokens=max_tokens
        ).strip()

        # 4. 判斷結果 (容忍 OK 後面帶有標點符號或換行)
        if judge_response.upper() == "OK" or judge_response.upper().startswith("OK"):
            self.routing.record(task_name, success=True, provider=draft_provider)
            logger.info("SmartRoute [%s] %s 通過評審", task_name, draft_provider)
            # 確保 last_provider 停留在 draft_provider (因為最終回傳的是 draft_result)
            self.last_provider = draft_provider
            return draft_result
        else:
            self.routing.record(task_name, success=False, provider=draft_provider)
            logger.info("SmartRoute [%s] %s 評審失敗，使用強大模型回傳", task_name, draft_provider)
            # last_provider 會自動停留在 strong_provider (由最後一次 generate 填入)
            return judge_response

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
            with LLMCallTracker(p.name, p.model, prompt, model_repo=getattr(p, "model_repo", "")):
                raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")

        last_exc: Exception | None = None
        for p in providers:
            try:
                with LLMCallTracker(p.name, p.model, prompt, model_repo=getattr(p, "model_repo", "")) as tracker:
                    result = p.generate(prompt, max_tokens=max_tokens)
                    tracker.result = result
                    tracker.key_used = getattr(p, "last_key_used", "")
                    self.last_provider = p.name
                    self.last_model = p.model
                    self.last_model_repo = getattr(p, "model_repo", "")
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
            with LLMCallTracker(p.name, p.model, prompt, model_repo=getattr(p, "model_repo", "")):
                raise ValueError(f"prompt 超過長度上限（{len(prompt)} > {MAX_PROMPT_LENGTH}）")

        last_exc: Exception | None = None
        for p in providers:
            try:
                with LLMCallTracker(p.name, p.model, prompt, model_repo=getattr(p, "model_repo", "")) as tracker:
                    text = p.generate(prompt, json_mode=True, max_tokens=max_tokens)
                    tracker.result = text
                    tracker.key_used = getattr(p, "last_key_used", "")
                    self.last_provider = p.name
                    self.last_model = p.model
                    self.last_model_repo = getattr(p, "model_repo", "")
                    return json.loads(text)
            except json.JSONDecodeError as e:
                logger.warning("%s 回傳非 JSON：%s", p.name, e)
                last_exc = e
            except Exception as e:
                logger.warning("%s 失敗：%s", p.name, e)
                last_exc = e
        raise RuntimeError("所有 provider 均失敗") from last_exc

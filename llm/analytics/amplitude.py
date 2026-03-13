"""Amplitude event tracking for LLM usage（靜默降級：無 key 時不報錯）。"""
from __future__ import annotations

import logging
import os
import time
from typing import Any

logger = logging.getLogger(__name__)

_client = None          # Amplitude instance，或 False（表示已確認不可用）
_app_name: str = "unknown"


def _get_client():
    global _client
    if _client is False:
        return None
    if _client is not None:
        return _client
    try:
        # 支援 python-dotenv（若已安裝）
        try:
            from dotenv import load_dotenv
            load_dotenv()
        except ImportError:
            pass

        from amplitude import Amplitude
        api_key = os.getenv("AMPLITUDE_API_KEY", "")
        if not api_key:
            _client = False
            return None
        _client = Amplitude(api_key)
        logger.debug("Amplitude 已初始化（API key 來自 .env）")
        return _client
    except ImportError:
        _client = False
        return None


def configure(app_name: str) -> None:
    global _app_name
    _app_name = app_name


def _classify_error(exc_type: type) -> str:
    """將 exception 類型映射成通用類別，不洩漏內部實作細節。"""
    name = exc_type.__name__.lower()
    if "auth" in name or "permission" in name or "forbidden" in name or "403" in name:
        return "auth_error"
    if "quota" in name or "ratelimit" in name or "429" in name:
        return "rate_limit"
    if "timeout" in name:
        return "timeout"
    if "connect" in name or "network" in name or "http" in name:
        return "network_error"
    if "json" in name or "decode" in name or "parse" in name:
        return "parse_error"
    if "value" in name or "type" in name:
        return "input_error"
    return "provider_error"


def _first_n_chars(text: str, n: int) -> str:
    return text[:n] if text else ""


def _first_n_words(text: str, n: int) -> str:
    words = text.split()
    return " ".join(words[:n]) if words else ""


class LLMCallTracker:
    """context manager：呼叫結束後送出單一 llm_call event。

    屬性（可在 with 區塊內設定）：
        result  (str)  — provider 回傳的文字，用於記錄前 100 words
    """

    def __init__(self, provider: str, model: str, prompt: str):
        self.provider = provider
        self.model = model
        self.prompt = prompt
        self.result: str = ""
        self.key_used: str = ""  # 由 client.py 在成功後填入
        self._start: float = 0.0

    def __enter__(self) -> "LLMCallTracker":
        self._start = time.monotonic()
        return self

    def __exit__(self, exc_type, exc_val, exc_tb):
        client = _get_client()
        if client is None:
            return False

        duration_sec = round(time.monotonic() - self._start, 2)
        success = exc_type is None

        props: dict[str, Any] = {
            "provider":       self.provider,
            "model":          self.model,
            "app_name":       _app_name,
            "key_used":       self.key_used,
            "input_preview":  _first_n_chars(self.prompt, 100),
            "output_preview": _first_n_words(self.result, 100),
            "duration_sec":   duration_sec,
            "success":        success,
        }
        if not success and exc_type is not None:
            props["error_type"] = _classify_error(exc_type)

        try:
            from amplitude import BaseEvent
            client.track(BaseEvent(
                event_type="llm_call",
                user_id=_app_name,
                event_properties=props,
            ))
        except Exception as e:
            logger.debug("Amplitude track 失敗（靜默）：%s", e)

        return False  # 不吃掉例外

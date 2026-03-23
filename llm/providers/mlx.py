"""Local MLX LLM provider（Apple Silicon only）。"""
from __future__ import annotations

import json
import logging
import os
import re

from . import BaseProvider

logger = logging.getLogger(__name__)

_DEFAULT_MODEL = "mlx-community/Qwen3-14B-4bit"
_MAX_TOKENS = 4096


class MLXProvider(BaseProvider):
    name = "mlx"

    def __init__(self, model: str | None = None):
        self.model = model or os.getenv("MLX_MODEL", _DEFAULT_MODEL)
        try:
            from mlx_lm import load, generate  # noqa: F401
        except ImportError:
            raise RuntimeError("mlx-lm not installed — run: pip install mlx-lm")
        self._load()

    def _load(self):
        from mlx_lm import load
        logger.info("[mlx] loading model %s …", self.model)
        self._mlx_model, self._mlx_tokenizer = load(self.model)
        logger.info("[mlx] model ready")

    def generate(self, prompt: str, *, json_mode: bool = False, max_tokens: int = _MAX_TOKENS) -> str:
        from mlx_lm import generate

        if json_mode:
            prompt = prompt + "\n\nRespond with valid JSON only, no markdown fences."

        messages = [{"role": "user", "content": prompt}]
        if hasattr(self._mlx_tokenizer, "apply_chat_template"):
            formatted = self._mlx_tokenizer.apply_chat_template(
                messages, tokenize=False, add_generation_prompt=True
            )
        else:
            formatted = prompt

        result = generate(
            self._mlx_model,
            self._mlx_tokenizer,
            prompt=formatted,
            max_tokens=max_tokens,
            verbose=False,
        )

        if json_mode:
            # strip markdown fences if model still adds them
            result = re.sub(r"^```(?:json)?\s*|\s*```$", "", result.strip())

        return result

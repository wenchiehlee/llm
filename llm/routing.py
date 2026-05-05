from __future__ import annotations

import json
import logging
import os
from pathlib import Path
from threading import Lock

logger = logging.getLogger(__name__)

class RoutingManager:
    """
    管理任務路由狀態，決定是否可以安全切換到特定 Provider (例如 MLX 或 Gemini-CLI)。
    """
    def __init__(self, storage_path: str | None = None, min_samples: int = 10, threshold: float = 0.8):
        self.path = Path(storage_path or os.getenv("LLM_ROUTING_FILE", ".llm_routing.json"))
        self.min_samples = min_samples
        self.threshold = threshold
        self._data: dict[str, dict] = {}
        self._lock = Lock()
        self._load()

    def _load(self):
        if self.path.exists():
            try:
                with open(self.path, "r", encoding="utf-8") as f:
                    self._data = json.load(f)
            except Exception as e:
                logger.error("無法載入路由檔案 %s: %s", self.path, e)
                self._data = {}

    def _save(self):
        try:
            with open(self.path, "w", encoding="utf-8") as f:
                json.dump(self._data, f, indent=2, ensure_ascii=False)
        except Exception as e:
            logger.error("無法儲存路由檔案 %s: %s", self.path, e)

    def get_status(self, task_name: str) -> str:
        """
        [舊方法] 回傳 'mlx_only' 或 'judging'。
        為了相容舊版代碼，若 promoted_to 為 'mlx' 也回傳 'mlx_only'。
        """
        provider = self.get_promoted_provider(task_name)
        if provider == "mlx":
            return "mlx_only"
        return "judging"

    def get_promoted_provider(self, task_name: str) -> str | None:
        """回傳被晉升的 Provider 名稱，若未晉等則回傳 None。"""
        with self._lock:
            stats = self._data.get(task_name)
            if not stats:
                return None
            
            # 向下相容
            if stats.get("is_permanently_mlx"):
                return "mlx"
            
            return stats.get("promoted_to")

    def record(self, task_name: str, success: bool, provider: str = "mlx"):
        """紀錄一次評估結果。"""
        with self._lock:
            if task_name not in self._data:
                self._data[task_name] = {"success": 0, "fail": 0, "promoted_to": None}
            
            stats = self._data[task_name]
            if success:
                stats["success"] = stats.get("success", 0) + 1
            else:
                stats["fail"] = stats.get("fail", 0) + 1
            
            # 檢查是否達到切換門檻
            total = stats["success"] + stats["fail"]
            if not stats.get("promoted_to") and not stats.get("is_permanently_mlx") and total >= self.min_samples:
                if (stats["success"] / total) >= self.threshold:
                    stats["promoted_to"] = provider
                    if provider == "mlx":
                        stats["is_permanently_mlx"] = True
                    logger.info("任務 '%s' 成功率達標 (%.1f%%)，已晉升至 Provider: %s", 
                                task_name, (stats["success"] / total) * 100, provider)
            
            self._save()

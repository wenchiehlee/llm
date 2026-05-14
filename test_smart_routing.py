"""Test for Smart Routing feature (Stateless & Amplitude-based)."""
import logging
import os
import sys
import time

logging.basicConfig(level=logging.INFO, format="%(levelname)s: %(message)s")

try:
    import dotenv
    dotenv.load_dotenv(override=True)
except ImportError:
    pass

from llm import LLMClient


def main():
    print("=== Smart Routing Test (Stateless) ===\n")
    
    # 初始化客戶端 (不再需要 routing 參數)
    client = LLMClient(
        app_name="SmartTestStateless"
    )

    task = "SimpleTranslation"
    prompt = "Translate 'Apple' to Traditional Chinese."

    print(f"--- Calling generate_smart (Expected: Draft -> Judge) ---")
    for i in range(2):
        print(f"\n[Call {i+1}]")
        result = client.generate_smart(task, prompt, draft_provider="mlx")
        print(f"Result: {result}")
        print(f"Last Provider: {client.last_provider}")
        # 注意：現在沒有 client.routing 了，所有紀錄請至 Amplitude 查看。
        time.sleep(1)

    print("\n--- Test Finished ---")
    print("Note: Local JSON routing is removed. Check Amplitude for performance data.")


if __name__ == "__main__":
    main()

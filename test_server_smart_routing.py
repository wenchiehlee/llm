"""Test for Server-Side Smart Routing (reflection on NAS)."""
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
    print("=== Server-Side Smart Routing Test (Gemini-CLI Reflection) ===\n")
    
    url = os.getenv("CODEX_API_URL")
    if not url:
        print("[SKIP] Missing CODEX_API_URL.")
        return

    # 初始化客戶端
    # 注意：伺服器端的 routing 門檻是在伺服器端設定的，
    # 這裡我們主要是測試通訊路徑是否正確。
    client = LLMClient(
        app_name="ServerSmartTest",
        providers=["codex"]
    )

    # 任務名稱：伺服器端會紀錄此名稱
    # 建議加上 timestamp 避免受舊的測試資料影響
    task = f"ServerReflectionTest_{int(time.time())}"
    prompt = "Translate 'Innovation' to Traditional Chinese."

    print(f"--- Calling generate_smart with draft_provider='codex' ---")
    print("This should trigger NAS-side gemini-cli -> gemini-cli reflection.")
    
    for i in range(2):
        print(f"\n[Call {i+1}]")
        # 當 draft_provider="codex" 且未指定 judge_provider 時，會走 Server-side 路由
        result = client.generate_smart(task, prompt, draft_provider="codex")
        print(f"Result: {result}")
        print(f"Last Provider: {client.last_provider}")
        
    print("\n--- Test Finished ---")
    print("Check Llm-Cli-APIServer logs to verify it used /smart/exec.")


if __name__ == "__main__":
    main()

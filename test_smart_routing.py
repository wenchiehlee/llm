"""Test for Smart Routing feature."""
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
    print("=== Smart Routing Test ===\n")
    
    # 初始化客戶端，設定較小的樣本數門檻以便測試
    routing_file = "test_routing.json"
    if os.path.exists(routing_file):
        os.remove(routing_file)
        
    client = LLMClient(
        app_name="SmartTest",
        routing_file=routing_file,
        min_samples=3,    # 只要 3 次樣本就判斷
        threshold=0.6     # 成功率 60% 即可
    )

    task = "SimpleTranslation"
    prompt = "Translate 'Apple' to Traditional Chinese."

    print(f"--- Phase 1: Judging (Expecting judging status) ---")
    for i in range(4):
        print(f"\n[Call {i+1}]")
        result = client.generate_smart(task, prompt)
        print(f"Result: {result}")
        # 查看目前狀態
        stats = client.routing._data.get(task, {})
        print(f"Stats: {stats}")
        time.sleep(1)

    print(f"\n--- Phase 2: Check if promoted ---")
    promoted = client.routing.get_promoted_provider(task)
    print(f"Final Promoted Provider: {promoted}")
    
    if promoted == "mlx":
        print("\n[PASS] Task promoted to MLX successfully.")
    else:
        print("\n[INFO] Task not promoted (maybe low success rate or not enough samples).")

    # Clean up
    if os.path.exists(routing_file):
        os.remove(routing_file)


if __name__ == "__main__":
    main()

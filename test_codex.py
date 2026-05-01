"""Manual test for Codex provider."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

try:
    import dotenv
    dotenv.load_dotenv(override=True)
except ImportError:
    pass

from llm import LLMClient


def check(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {label}" + (f": {detail}" if detail else ""))
    if not passed:
        sys.exit(1)


def main():
    print("=== Codex provider test ===\n")

    # Pre-flight: check environment variables
    url = os.getenv("CODEX_API_URL")
    key = os.getenv("SERVER_API_KEY")

    if not url or not key:
        print("[SKIP] Missing env vars: CODEX_API_URL or SERVER_API_KEY")
        sys.exit(0)

    print(f"Debug: URL={url}")
    print(f"Debug: Key length={len(key)}")
    print(f"Debug: Key starts with={repr(key[0]) if key else 'None'}")
    if "#" in key:
        print("Debug: Key contains '#' character.")
    else:
        # 檢查原始 .env 是否有 # 但讀取出來卻沒有
        pass

    # 1. init
    try:
        client = LLMClient(providers=["codex"])
    except RuntimeError as e:
        check("Codex init", False, str(e))
        return

    check("Codex init", True, f"model={client.last_model} url={url}")

    # 2. plain text
    print("\nTesting generate()...")
    result = client.generate("Reply with exactly: Hello from Codex.")
    check("generate() returns non-empty string", isinstance(result, str) and len(result) > 0, repr(result[:120]))
    check("last_provider is codex", client.last_provider == "codex")

    # 3. JSON mode
    print("\nTesting generate_json()...")
    data = client.generate_json(
        'Return a JSON object with keys "name" (string) and "value" (integer). Example: {"name":"test","value":42}'
    )
    check("generate_json() returns dict", isinstance(data, dict), str(data))
    check('JSON has "name" key', "name" in data)
    check('JSON has "value" key', "value" in data)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()

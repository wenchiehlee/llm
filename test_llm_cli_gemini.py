"""Test for Gemini via Codex provider."""
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
    print("=== Gemini via Codex provider test ===\n")

    url = os.getenv("CODEX_API_URL")
    key = os.getenv("CODEX_API_KEY")

    if not url or not key:
        print("[SKIP] Missing env vars: CODEX_API_URL or CODEX_API_KEY")
        sys.exit(0)

    # 1. init with gemini model
    try:
        # 測試指定 model 為 gemini-2.5-flash，並指定 provider 為 codex
        client = LLMClient(providers=["codex"], model="gemini-2.5-flash")
    except RuntimeError as e:
        check("Codex init", False, str(e))
        return

    check("Codex init", True, f"model={client.last_model} url={url}")

    # 2. plain text
    print("\nTesting generate() via Gemini endpoint...")
    result = client.generate("Reply with exactly: Hello from Gemini via Codex.")
    check("generate() returns non-empty string", isinstance(result, str) and len(result) > 0, repr(result[:120]))
    check("last_provider is codex", client.last_provider == "codex")
    check("last_model is gemini-2.5-flash", client.last_model == "gemini-2.5-flash")

    # 3. JSON mode
    print("\nTesting generate_json() via Gemini endpoint...")
    data = client.generate_json(
        'Return a JSON object with keys "test" (string) and "val" (int). Example: {"test":"ok","val":1}'
    )
    check("generate_json() returns dict", isinstance(data, dict), str(data))
    check('JSON has "test" key', "test" in data)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()

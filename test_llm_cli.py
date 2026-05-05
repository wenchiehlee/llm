"""Manual test for LLM CLI client (codex / gemini / mlx providers)."""
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


def _detect_provider() -> tuple[str, dict]:
    """回傳 (provider_name, extra_env_info)，依序偵測可用的 provider。"""
    codex_url = os.getenv("CODEX_API_URL")
    codex_key = os.getenv("SERVER_API_KEY")
    if codex_url and codex_key:
        return "codex", {"url": codex_url, "key_len": len(codex_key)}

    gemini_key = os.getenv("GEMINI_API_KEY")
    if gemini_key:
        return "gemini", {"key_len": len(gemini_key)}

    mlx_url = os.getenv("MLX_API_URL")
    if mlx_url:
        return "mlx", {"url": mlx_url}

    return "", {}


def main():
    provider, env_info = _detect_provider()

    if not provider:
        print("[SKIP] 未偵測到任何可用的 provider 環境變數（CODEX_API_URL/SERVER_API_KEY、GEMINI_API_KEY、MLX_API_URL）")
        sys.exit(0)

    print(f"=== LLM CLI test（provider: {provider}）===\n")
    for k, v in env_info.items():
        print(f"Debug: {k}={v}")

    # 1. init
    try:
        client = LLMClient(providers=[provider])
    except RuntimeError as e:
        check(f"{provider} init", False, str(e))
        return

    check(f"{provider} init", True, f"model={client.last_model}")

    # 2. plain text
    print("\nTesting generate()...")
    result = client.generate(f"Reply with exactly: Hello from {provider}.")
    check("generate() returns non-empty string", isinstance(result, str) and len(result) > 0, repr(result[:120]))
    check(f"last_provider is {provider}", client.last_provider == provider)

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

"""Manual test for MLX provider (HTTP client to Mac-mini MLX-API-Server)."""
import logging
import os
import sys

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")

try:
    import dotenv
    dotenv.load_dotenv()
except ImportError:
    pass

from llm import LLMClient


def check(label: str, passed: bool, detail: str = "") -> None:
    status = "PASS" if passed else "FAIL"
    print(f"[{status}] {label}" + (f": {detail}" if detail else ""))
    if not passed:
        sys.exit(1)


def main():
    print("=== MLX provider test (HTTP -> Mac-mini) ===\n")

    url = os.getenv("MLX_API_URL")
    key = os.getenv("MLX_SERVER_API_KEY")

    if not url or not key:
        print("[SKIP] Missing env vars: MLX_API_URL or MLX_SERVER_API_KEY")
        sys.exit(0)

    print(f"URL: {url}")

    # 1. init
    try:
        client = LLMClient(providers=["mlx"], app_name="test-mlx")
    except RuntimeError as e:
        check("MLX init", False, str(e))
        return

    check("MLX init", True, f"model={client.last_model}  repo={client.last_model_repo}")

    # 2. plain text
    print("\nTesting generate()...")
    result = client.generate("Reply with exactly: Hello from MLX.")
    check("generate() returns non-empty string", isinstance(result, str) and len(result) > 0, repr(result[:120]))
    check("last_provider is mlx", client.last_provider == "mlx")

    # 3. JSON mode
    print("\nTesting generate_json()...")
    data = client.generate_json(
        'Return a JSON object with keys "name" (string) and "value" (integer). Example: {"name":"test","value":42}'
    )
    check("generate_json() returns dict", isinstance(data, dict), str(data))
    check('JSON has "name" key', "name" in data)
    check('JSON has "value" key', "value" in data)

    # 4. mlx-gemma4 (optional — skipped if still downloading)
    print("\nTesting mlx-gemma4 model (optional)...")
    try:
        gemma_client = LLMClient(providers=["mlx"], app_name="test-mlx-gemma4")
        gemma_client._providers[0].model = "mlx-gemma4"
        gemma_client._providers[0].model_repo = "mlx-community/gemma-4-31b-it-4bit"
        result = gemma_client.generate("Reply with exactly: Hello from Gemma.")
        check("mlx-gemma4 generate()", isinstance(result, str) and len(result) > 0, repr(result[:80]))
    except Exception as e:
        print(f"[SKIP] mlx-gemma4 not ready: {type(e).__name__}")

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()

"""Manual test for MLX provider (Apple Silicon only)."""
import logging
import platform
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
    print("=== MLX provider test ===\n")

    # Pre-flight: Apple Silicon check
    if not (platform.system() == "Darwin" and platform.machine() == "arm64"):
        print(f"[SKIP] Not Apple Silicon ({platform.system()} {platform.machine()}) — mlx-lm is macOS arm64 only.")
        sys.exit(0)

    # Pre-flight: mlx-lm installed?
    try:
        import mlx_lm  # noqa: F401
    except ImportError:
        print("[SKIP] mlx-lm not installed — run: pip install mlx-lm")
        sys.exit(0)

    # 1. init
    try:
        client = LLMClient(providers=["mlx"])
    except RuntimeError as e:
        check("MLX init", False, str(e))
        return

    check("MLX init", True, f"model={client.last_model}  repo={client.last_model_repo}")

    # 2. plain text
    result = client.generate("Reply with exactly: Hello from MLX.")
    check("generate() returns non-empty string", isinstance(result, str) and len(result) > 0, repr(result[:120]))
    check("last_provider is mlx", client.last_provider == "mlx")

    # 3. JSON mode
    data = client.generate_json(
        'Return a JSON object with keys "name" (string) and "value" (integer). Example: {"name":"test","value":42}'
    )
    check("generate_json() returns dict", isinstance(data, dict), str(data))
    check('JSON has "name" key', "name" in data)
    check('JSON has "value" key', "value" in data)

    print("\nAll checks passed.")


if __name__ == "__main__":
    main()

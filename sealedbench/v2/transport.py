"""v2 network retries; rehearsal gateways require explicit dry-upload mode."""
import os
import time

INDEPENDENT = ("https://ar-io.dev", "https://turbo-gateway.com")


def gateways() -> tuple[str, ...]:
    override = os.environ.get("SEALEDBENCH_V2_GATEWAYS")
    if override:
        if os.environ.get("SEALEDBENCH_DRY_UPLOAD") != "1":
            raise ValueError("gateway override requires SEALEDBENCH_DRY_UPLOAD=1")
        return tuple(host.rstrip("/") for host in override.split(","))
    return INDEPENDENT


def retry(label, operation, attempts=6, delay=30):
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except (RuntimeError, OSError, TimeoutError, ValueError) as exc:
            if attempt == attempts:
                raise
            print(f"RETRY {label} attempt={attempt} error={exc}", flush=True)
            time.sleep(delay)

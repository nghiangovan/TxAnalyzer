#!/usr/bin/env python3

import argparse
import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
DEFAULT_CONFIG = ROOT / "config.json"


def resolve_env(value: Any) -> Any:
    if isinstance(value, str):
        match = re.fullmatch(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", value)
        if match:
            return os.environ.get(match.group(1), "")
        return re.sub(r"\$\{([A-Za-z_][A-Za-z0-9_]*)\}", lambda m: os.environ.get(m.group(1), ""), value)
    if isinstance(value, dict):
        return {k: resolve_env(v) for k, v in value.items()}
    if isinstance(value, list):
        return [resolve_env(v) for v in value]
    return value


def load_config(path: Path) -> dict[str, Any]:
    if not path.exists():
        raise FileNotFoundError(f"Config file not found: {path}. Copy config_template.json to config.json first.")
    with path.open("r", encoding="utf-8") as f:
        return resolve_env(json.load(f))


def main() -> int:
    parser = argparse.ArgumentParser(description="Start anvil pinned to a transaction prestate for any configured EVM network.")
    parser.add_argument("--network", required=True, help="Network key from config.json, e.g. eth, bsc, arb, base")
    parser.add_argument("--tx", required=True, help="Transaction hash to pin with --fork-transaction-hash")
    parser.add_argument("--config", default=str(DEFAULT_CONFIG), help="Path to config.json")
    parser.add_argument("--port", type=int, help="Override anvil port")
    parser.add_argument("--cache-path", help="Optional anvil cache path")
    parser.add_argument("--dry-run", action="store_true", help="Print the anvil command without executing it")
    args = parser.parse_args()

    config = load_config(Path(args.config))
    networks = config.get("networks") or {}
    network = networks.get(args.network)
    if not isinstance(network, dict):
        raise ValueError(f"Unsupported network: {args.network}. Supported networks: {list(networks.keys())}")
    if network.get("type") == "solana":
        raise ValueError("Solana does not support Foundry/anvil EVM fork replay")

    rpc_url = network.get("rpc_url_trace") or network.get("rpc_url")
    if not isinstance(rpc_url, str) or not rpc_url:
        raise ValueError(f"Network {args.network} is missing rpc_url_trace/rpc_url or the referenced env var is unset")

    port = args.port or int(network.get("anvil_port") or 8546)
    cmd = [
        "anvil",
        "--fork-url", rpc_url,
        "--fork-transaction-hash", args.tx,
        "--port", str(port),
        "--timeout", "120000",
        "--retries", "20",
        "--fork-retry-backoff", "1000",
        "--no-rate-limit",
    ]
    if args.cache_path:
        cmd.extend(["--cache-path", args.cache_path])

    print(" ".join(cmd))
    if args.dry_run:
        return 0

    return subprocess.call(cmd)


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"error: {exc}", file=sys.stderr)
        raise SystemExit(1)

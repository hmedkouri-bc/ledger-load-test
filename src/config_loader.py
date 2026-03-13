"""YAML + env var configuration loader."""

import os
from pathlib import Path

import yaml

_DEFAULT_CONFIG = {
    "ledger": {
        "host": "localhost",
        "port": 6565,
        "tls": False,
        "rpc_timeout_seconds": 5,
    },
    "test": {
        "user_pool_size": 100,
        "user_uuid_seed": 42,
        "origin": "LOADTEST_FLUTTERWAVE",
        "external_ref_prefix": "LOADTEST:",
    },
    "accounts": {
        "funding": 200500,
        "trading": 200510,
        "fee": 200430,
    },
    "currencies": {
        "primary": "USDT",
    },
    "amounts": {
        "min": 500.0,
        "max": 1000000.0,
    },
}


def _deep_merge(base: dict, override: dict) -> dict:
    result = base.copy()
    for k, v in override.items():
        if k in result and isinstance(result[k], dict) and isinstance(v, dict):
            result[k] = _deep_merge(result[k], v)
        else:
            result[k] = v
    return result


def load_config(path: str | None = None) -> dict:
    """Load config from YAML file, with env var overrides.

    Resolution order: defaults -> YAML file -> env vars.
    """
    config = _DEFAULT_CONFIG.copy()

    # Resolve config file path
    config_path = path or os.environ.get("CONFIG_PATH", "config/local.yaml")
    if Path(config_path).exists():
        with open(config_path) as f:
            file_config = yaml.safe_load(f) or {}
        config = _deep_merge(config, file_config)

    # Env var overrides
    if host := os.environ.get("LEDGER_HOST"):
        config["ledger"]["host"] = host
    if port := os.environ.get("LEDGER_PORT"):
        config["ledger"]["port"] = int(port)
    if tls := os.environ.get("LEDGER_TLS"):
        config["ledger"]["tls"] = tls.lower() in ("true", "1", "yes")

    return config

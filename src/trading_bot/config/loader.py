import os
import yaml
from dotenv import dotenv_values

REQUIRED_KEYS = ("universe", "capital", "data", "backtest", "strategies")


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r") as f:
        cfg = yaml.safe_load(f) or {}
    missing = [k for k in REQUIRED_KEYS if k not in cfg]
    if missing:
        raise ValueError(f"config missing required keys: {missing}")
    return cfg


def load_secrets(path: str = ".env") -> dict:
    values = dotenv_values(path) if os.path.exists(path) else {}
    return {
        "ALPACA_API_KEY": values.get("ALPACA_API_KEY", ""),
        "ALPACA_SECRET_KEY": values.get("ALPACA_SECRET_KEY", ""),
        "ALPACA_PAPER": str(values.get("ALPACA_PAPER", "true")).lower() == "true",
    }

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


def _int(value, default):
    try:
        return int(value)
    except (TypeError, ValueError):
        return default


def load_secrets(path: str = ".env") -> dict:
    values = dotenv_values(path) if os.path.exists(path) else {}
    return {
        "ALPACA_API_KEY": values.get("ALPACA_API_KEY", ""),
        "ALPACA_SECRET_KEY": values.get("ALPACA_SECRET_KEY", ""),
        "ALPACA_PAPER": str(values.get("ALPACA_PAPER", "true")).lower() == "true",
        "SMTP_HOST": values.get("SMTP_HOST", ""),
        "SMTP_PORT": _int(values.get("SMTP_PORT", 587), 587),
        "SMTP_USER": values.get("SMTP_USER", ""),
        "SMTP_PASS": values.get("SMTP_PASS", ""),
        "REPORT_FROM_EMAIL": values.get("REPORT_FROM_EMAIL", ""),
        "REPORT_TO_EMAIL": values.get("REPORT_TO_EMAIL", ""),
    }

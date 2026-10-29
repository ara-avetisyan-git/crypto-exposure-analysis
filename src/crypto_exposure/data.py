"""Input loading and validation."""
from __future__ import annotations

from importlib import resources
from pathlib import Path

import pandas as pd
import yaml

TX_REQUIRED = ["txid", "timestamp", "from_address", "to_address", "amount"]
LABEL_REQUIRED = ["address", "category"]


def default_config_path() -> Path:
    return Path(str(resources.files("crypto_exposure").joinpath("config.yaml")))


def load_config(path: str | Path | None = None) -> dict:
    with open(path or default_config_path(), encoding="utf-8") as fh:
        config = yaml.safe_load(fh)
    for key in ("categories", "analysis", "typologies"):
        if key not in config:
            raise ValueError(f"Config is missing '{key}'")
    unknown = set(config.get("reset_categories", [])) - set(config["categories"])
    if unknown:
        raise ValueError(f"reset_categories not defined in categories: {sorted(unknown)}")
    return config


def prepare_transactions(df: pd.DataFrame) -> pd.DataFrame:
    missing = [c for c in TX_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Transaction file is missing columns: {', '.join(missing)}")
    out = df.copy()
    out["timestamp"] = pd.to_datetime(out["timestamp"], errors="raise")
    out["amount"] = pd.to_numeric(out["amount"], errors="raise")
    if (out["amount"] <= 0).any():
        raise ValueError("amount must be positive")
    for col in ("txid", "from_address", "to_address"):
        out[col] = out[col].astype(str).str.strip()
    per_tx_senders = out.groupby("txid")["from_address"].nunique()
    if (per_tx_senders > 1).any():
        raise ValueError("Each txid must have a single sender; split multi-input transactions beforehand")
    return out.sort_values(["timestamp", "txid"], kind="stable").reset_index(drop=True)


def prepare_labels(df: pd.DataFrame, config: dict) -> dict[str, str]:
    missing = [c for c in LABEL_REQUIRED if c not in df.columns]
    if missing:
        raise ValueError(f"Label file is missing columns: {', '.join(missing)}")
    unknown = set(df["category"]) - set(config["categories"])
    if unknown:
        raise ValueError(f"Labels use categories missing from the config: {sorted(unknown)}")
    if df["address"].duplicated().any():
        raise ValueError("Each address may carry only one label")
    return dict(zip(df["address"].astype(str).str.strip(), df["category"]))


def read_inputs(tx_path: str, labels_path: str, config: dict):
    tx = prepare_transactions(pd.read_csv(tx_path, dtype=str))
    labels = prepare_labels(pd.read_csv(labels_path, dtype=str, keep_default_na=False), config)
    return tx, labels

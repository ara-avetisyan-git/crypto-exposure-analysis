"""Small hand-built scenario with fictional addresses (no real blockchain data)."""
from __future__ import annotations

import pandas as pd

BASE = pd.Timestamp("2026-09-01 08:00")


def build() -> tuple[pd.DataFrame, pd.DataFrame]:
    rows: list[tuple] = []

    def tx(txid: str, hours: float, sender: str, outputs: dict[str, float]):
        for to, amount in outputs.items():
            rows.append((txid, BASE + pd.Timedelta(hours=hours), sender, to, amount, "BTC"))

    # 1. Funds from a sanctioned address are peeled through a chain and cashed out at an exchange
    tx("T001", 0, "ADDR_SANCTIONED_1", {"ADDR_A": 100})
    tx("T002", 2, "ADDR_A", {"ADDR_B": 95, "ADDR_PEEL_1": 5})
    tx("T003", 4, "ADDR_B", {"ADDR_C": 90, "ADDR_PEEL_2": 5})
    tx("T004", 6, "ADDR_C", {"ADDR_D": 85, "ADDR_PEEL_3": 5})
    tx("T005", 8, "ADDR_D", {"ADDR_E": 80, "ADDR_PEEL_4": 5})
    tx("T006", 10, "ADDR_E", {"ADDR_EXCHANGE_1": 80})

    # 2. Mixed funds: 300 of unexplained origin + 100 from a mixer, partly spent onwards
    tx("T007", 24, "ADDR_UNKNOWN_1", {"ADDR_F": 300})
    tx("T008", 25, "ADDR_MIXER_1", {"ADDR_F": 100})
    tx("T009", 30, "ADDR_F", {"ADDR_H": 50})

    # 3. Fan-in to a collector that forwards everything within hours
    for i in range(1, 7):
        tx(f"T01{i - 1}", 48 + (i - 1), f"ADDR_FANIN_{i}", {"ADDR_COLLECTOR": 10})
    tx("T016", 53, "ADDR_COLLECTOR", {"ADDR_G": 60})
    tx("T017", 55, "ADDR_G", {"ADDR_EXCHANGE_1": 60})

    # 4. A victim pays a scam address
    tx("T018", 72, "ADDR_VICTIM_1", {"ADDR_SCAM_1": 5})

    # 5. Ordinary low-risk activity
    tx("T019", 80, "ADDR_CLEAN_1", {"ADDR_CLEAN_2": 20})
    tx("T020", 200, "ADDR_CLEAN_2", {"ADDR_CLEAN_1": 5})

    tx_df = pd.DataFrame(rows, columns=["txid", "timestamp", "from_address", "to_address", "amount", "asset"])
    labels = pd.DataFrame([
        ("ADDR_SANCTIONED_1", "sanctions list (fictional)", "sanctioned"),
        ("ADDR_MIXER_1", "mixing service (fictional)", "mixer"),
        ("ADDR_SCAM_1", "reported scam (fictional)", "scam"),
        ("ADDR_EXCHANGE_1", "regulated exchange (fictional)", "exchange"),
    ], columns=["address", "source", "category"])
    return tx_df, labels

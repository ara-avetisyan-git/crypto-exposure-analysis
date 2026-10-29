"""Proportional ("haircut") taint propagation.

Every address holds a mix of fund origins. When an address sends funds, the sent amount
carries the sender's current mix; funds the data does not explain are "untracked".
Addresses labeled with a risky category are treated as the origin of their own outgoing funds.
"""
from __future__ import annotations

from collections import defaultdict

import pandas as pd

UNTRACKED = "untracked"
EPS = 1e-9


def propagate(tx: pd.DataFrame, labels: dict[str, str], reset_categories: set[str]) -> dict[str, dict[str, float]]:
    """Return, for every address, the cumulative received amount split by fund origin."""
    holdings: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))
    received: dict[str, dict[str, float]] = defaultdict(lambda: defaultdict(float))

    for _, group in tx.groupby("txid", sort=False):
        sender = group["from_address"].iloc[0]
        outputs = list(zip(group["to_address"], group["amount"].astype(float)))
        total = sum(amount for _, amount in outputs)

        category = labels.get(sender)
        if category is not None:
            mix = {UNTRACKED: 1.0} if category in reset_categories else {category: 1.0}
        else:
            held_mix = holdings[sender]
            held = sum(held_mix.values())
            if held >= total - EPS:
                mix = {k: v / held for k, v in held_mix.items() if v > EPS}
                for k, share in mix.items():
                    held_mix[k] -= share * total
            else:
                mix = {k: v / total for k, v in held_mix.items() if v > EPS}
                mix[UNTRACKED] = mix.get(UNTRACKED, 0.0) + (total - held) / total
                held_mix.clear()

        for address, amount in outputs:
            for origin, share in mix.items():
                holdings[address][origin] += amount * share
                received[address][origin] += amount * share

    return {a: dict(m) for a, m in received.items()}


def exposure_score(received_mix: dict[str, float], weights: dict[str, float]) -> float:
    total = sum(received_mix.values())
    if total <= EPS:
        return 0.0
    return 100.0 * sum(amount / total * weights.get(origin, 0.0) for origin, amount in received_mix.items())


def describe_mix(received_mix: dict[str, float], top: int = 3) -> str:
    total = sum(received_mix.values())
    if total <= EPS:
        return ""
    parts = sorted(received_mix.items(), key=lambda kv: -kv[1])[:top]
    return "; ".join(f"{origin}={amount / total:.0%}" for origin, amount in parts)

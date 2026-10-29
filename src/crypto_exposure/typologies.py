"""Behavioural patterns: peeling chains, fan-in / fan-out, rapid forwarding."""
from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass

import pandas as pd


@dataclass(frozen=True)
class PeelingChain:
    chain_id: int
    start_txid: str
    length: int
    addresses: tuple[str, ...]
    peeled_total: float


def _transactions(tx: pd.DataFrame) -> list[dict]:
    rows = []
    for txid, group in tx.groupby("txid", sort=False):
        outputs = sorted(zip(group["to_address"], group["amount"].astype(float)), key=lambda o: -o[1])
        rows.append({"txid": txid, "sender": group["from_address"].iloc[0], "timestamp": group["timestamp"].iloc[0],
                     "outputs": outputs, "total": sum(a for _, a in outputs)})
    return rows


def find_peeling_chains(tx: pd.DataFrame, main_share: float, min_chain: int) -> list[PeelingChain]:
    """A peeling transaction sends most funds to one address and small amounts elsewhere;
    a chain links peeling transactions whose main recipient is the next sender."""
    peel = {t["txid"]: t for t in _transactions(tx)
            if len(t["outputs"]) >= 2 and t["outputs"][0][1] / t["total"] >= main_share}
    by_sender: dict[str, list[str]] = defaultdict(list)
    for txid, t in peel.items():
        by_sender[t["sender"]].append(txid)

    next_of: dict[str, str] = {}
    for txid, t in peel.items():
        main = t["outputs"][0][0]
        later = [c for c in by_sender.get(main, []) if peel[c]["timestamp"] > t["timestamp"]]
        if later:
            next_of[txid] = min(later, key=lambda c: peel[c]["timestamp"])

    chains: list[PeelingChain] = []
    followers = set(next_of.values())
    for start in sorted(peel, key=lambda x: peel[x]["timestamp"]):
        if start in followers:
            continue
        txids = [start]
        while txids[-1] in next_of:
            txids.append(next_of[txids[-1]])
        if len(txids) >= min_chain:
            addresses = [peel[t]["sender"] for t in txids] + [peel[txids[-1]]["outputs"][0][0]]
            peeled = sum(a for t in txids for _, a in peel[t]["outputs"][1:])
            chains.append(PeelingChain(len(chains) + 1, start, len(txids), tuple(addresses), peeled))
    return chains


def find_fans(tx: pd.DataFrame, min_counterparties: int, window_hours: float) -> tuple[set[str], set[str]]:
    window = pd.Timedelta(hours=window_hours)
    fan_in: set[str] = set()
    fan_out: set[str] = set()
    for column, other, target in (("to_address", "from_address", fan_in), ("from_address", "to_address", fan_out)):
        for address, group in tx.groupby(column):
            group = group.sort_values("timestamp")
            times, others = group["timestamp"].tolist(), group[other].tolist()
            for i in range(len(group)):
                j = i
                while j + 1 < len(group) and times[j + 1] - times[i] <= window:
                    j += 1
                if len(set(others[i:j + 1])) >= min_counterparties:
                    target.add(address)
                    break
    return fan_in, fan_out


def find_rapid_forwarders(tx: pd.DataFrame, share: float, window_hours: float, min_amount: float) -> set[str]:
    window = pd.Timedelta(hours=window_hours)
    table = _transactions(tx)
    sent: dict[str, list[tuple[pd.Timestamp, float]]] = defaultdict(list)
    for t in table:
        sent[t["sender"]].append((t["timestamp"], t["total"]))
    flagged: set[str] = set()
    for t in table:
        for address, amount in t["outputs"]:
            if address in flagged or amount < min_amount:
                continue
            out = sum(a for ts, a in sent.get(address, []) if t["timestamp"] < ts <= t["timestamp"] + window)
            if out >= share * amount:
                flagged.add(address)
    return flagged

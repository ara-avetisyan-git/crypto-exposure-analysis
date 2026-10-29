"""Putting it together: one row of findings per address."""
from __future__ import annotations

from dataclasses import dataclass

import pandas as pd

from .graph import build_graph, hops_from, hops_to
from .taint import describe_mix, exposure_score, propagate
from .typologies import PeelingChain, find_fans, find_peeling_chains, find_rapid_forwarders


@dataclass
class AnalysisResult:
    addresses: pd.DataFrame
    chains: list[PeelingChain]
    graph: object
    risky_sources: set[str]
    received: dict


def analyze(tx: pd.DataFrame, labels: dict[str, str], config: dict) -> AnalysisResult:
    weights = config["categories"]
    reset = set(config.get("reset_categories", []))
    params, ty = config["analysis"], config["typologies"]

    risky = {a for a, c in labels.items() if weights[c] > 0}
    services = {a for a, c in labels.items() if c in reset}

    received = propagate(tx, labels, reset)
    graph = build_graph(tx)
    from_risky = hops_from(graph, risky, params["max_hops"])
    to_risky = hops_to(graph, risky, params["max_hops"])

    chains = find_peeling_chains(tx, **ty["peeling_chain"])
    fan_in, fan_out = find_fans(tx, ty["fan"]["min_counterparties"], ty["fan"]["window_hours"])
    forwarders = find_rapid_forwarders(tx, **ty["rapid_forwarding"])
    in_chain = {a for c in chains for a in c.addresses}

    direct: dict[str, set[str]] = {}
    for row in tx.itertuples(index=False):
        if row.from_address in risky:
            direct.setdefault(row.to_address, set()).add(row.from_address)
        if row.to_address in risky:
            direct.setdefault(row.from_address, set()).add(row.to_address)

    sent_total = tx.groupby("from_address")["amount"].sum()
    recv_total = tx.groupby("to_address")["amount"].sum()
    rows = []
    for address in sorted(set(tx["from_address"]) | set(tx["to_address"])):
        mix = received.get(address, {})
        score = exposure_score(mix, weights)
        flags = []
        if address not in services:
            if address in in_chain:
                flags.append("peeling_chain")
            if address in fan_in:
                flags.append("fan_in")
            if address in fan_out:
                flags.append("fan_out")
            if address in forwarders:
                flags.append("rapid_forwarding")
        hf, ht = from_risky.get(address), to_risky.get(address)
        category = labels.get(address)

        if category is not None:
            level = "service" if weights[category] == 0 else ("high" if weights[category] >= 0.7 else "medium")
        elif score >= params["high_score"]:
            level = "high"
        elif (score >= params["medium_score"] or flags
              or (hf is not None and hf <= params["medium_hops"])
              or (ht is not None and ht <= params["medium_hops"])):
            level = "medium"
        else:
            level = "low"

        rows.append({
            "address": address,
            "label": category or "",
            "risk_level": level,
            "exposure_score": round(score, 1),
            "exposure_breakdown": describe_mix(mix),
            "direct_risky_counterparties": len(direct.get(address, ())),
            "hops_from_risky": hf if hf is not None else "",
            "hops_to_risky": ht if ht is not None else "",
            "flags": ";".join(flags),
            "total_received": round(float(recv_total.get(address, 0.0)), 8),
            "total_sent": round(float(sent_total.get(address, 0.0)), 8),
        })
    table = pd.DataFrame(rows)
    order = {"high": 0, "medium": 1, "low": 2, "service": 3}
    table = table.assign(_o=table["risk_level"].map(order)).sort_values(
        ["_o", "exposure_score"], ascending=[True, False]).drop(columns="_o").reset_index(drop=True)
    return AnalysisResult(table, chains, graph, risky, received)

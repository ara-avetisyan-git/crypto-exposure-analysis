"""Transfer graph, hop distances and path tracing."""
from __future__ import annotations

import networkx as nx
import pandas as pd


def build_graph(tx: pd.DataFrame) -> nx.DiGraph:
    graph = nx.DiGraph()
    for row in tx.itertuples(index=False):
        if graph.has_edge(row.from_address, row.to_address):
            edge = graph[row.from_address][row.to_address]
            edge["amount"] += float(row.amount)
            edge["count"] += 1
            edge["last_seen"] = max(edge["last_seen"], row.timestamp)
        else:
            graph.add_edge(row.from_address, row.to_address, amount=float(row.amount), count=1,
                           first_seen=row.timestamp, last_seen=row.timestamp)
    return graph


def hops_from(graph: nx.DiGraph, sources: set[str], cutoff: int) -> dict[str, int]:
    """Shortest number of transfers from any source to each reachable address."""
    present = [s for s in sources if s in graph]
    if not present:
        return {}
    return dict(nx.multi_source_dijkstra_path_length(graph, present, cutoff=cutoff))


def hops_to(graph: nx.DiGraph, targets: set[str], cutoff: int) -> dict[str, int]:
    """Shortest number of transfers from each address to any target."""
    return hops_from(graph.reverse(copy=False), targets, cutoff)


def trace_path(graph: nx.DiGraph, sources: set[str], address: str) -> list[str] | None:
    present = [s for s in sources if s in graph]
    if not present or address not in graph:
        return None
    try:
        _, path = nx.multi_source_dijkstra(graph, present, target=address)
    except nx.NetworkXNoPath:
        return None
    return path

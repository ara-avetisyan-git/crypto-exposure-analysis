"""Command-line interface: sample data, address analysis and single-address tracing."""
from __future__ import annotations

import argparse
from pathlib import Path

from .analysis import analyze
from .data import load_config, read_inputs
from .graph import trace_path
from .sample_data import build


def _cmd_sample(args) -> int:
    out = Path(args.output_dir)
    out.mkdir(parents=True, exist_ok=True)
    tx, labels = build()
    tx.to_csv(out / "transactions_synthetic.csv", index=False)
    labels.to_csv(out / "labels_synthetic.csv", index=False)
    print(f"Wrote {len(tx)} transfers and {len(labels)} labels to {out}/")
    return 0


def _run(args):
    config = load_config(args.config)
    tx, labels = read_inputs(args.transactions, args.labels, config)
    return analyze(tx, labels, config), labels, config


def _cmd_analyze(args) -> int:
    result, _, _ = _run(args)
    result.addresses.to_csv(args.output, index=False)
    counts = result.addresses["risk_level"].value_counts()
    print(f"Analysed {len(result.addresses)} addresses -> {args.output}")
    print("  " + ", ".join(f"{k}={counts.get(k, 0)}" for k in ("high", "medium", "low", "service")))
    for chain in result.chains:
        print(f"  Peeling chain #{chain.chain_id}: {chain.length} transactions, "
              f"{' -> '.join(chain.addresses)}, peeled off {chain.peeled_total:g}")
    return 0


def _cmd_trace(args) -> int:
    result, labels, config = _run(args)
    table = result.addresses.set_index("address")
    if args.address not in table.index:
        print(f"Address {args.address} not found in the transfers")
        return 1
    row = table.loc[args.address]
    print(f"Address:   {args.address}  [{row['risk_level'].upper()}]")
    print(f"Exposure:  {row['exposure_score']}/100  ({row['exposure_breakdown'] or 'no inflows'})")
    print(f"Flags:     {row['flags'] or 'none'}")
    path = trace_path(result.graph, result.risky_sources, args.address)
    if path and len(path) > 1:
        print("Nearest path from a risky address:")
        for a, b in zip(path, path[1:]):
            edge = result.graph[a][b]
            print(f"  {a} -> {b}   {edge['amount']:g} in {edge['count']} transfer(s), {edge['first_seen']:%Y-%m-%d %H:%M}")
    else:
        print("No path from a labeled risky address within the data.")
    return 0


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(prog="crypto-exposure", description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)

    p = sub.add_parser("sample", help="Write the synthetic scenario")
    p.add_argument("--output-dir", default="examples")
    p.set_defaults(func=_cmd_sample)

    for name, func, help_ in (("analyze", _cmd_analyze, "Analyse all addresses"),
                              ("trace", _cmd_trace, "Case view for one address")):
        p = sub.add_parser(name, help=help_)
        p.add_argument("--transactions", required=True)
        p.add_argument("--labels", required=True)
        p.add_argument("--config")
        p.set_defaults(func=func)
        if name == "analyze":
            p.add_argument("--output", required=True)
        else:
            p.add_argument("--address", required=True)
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        return args.func(args)
    except (ValueError, FileNotFoundError) as exc:
        print(f"Error: {exc}")
        return 2

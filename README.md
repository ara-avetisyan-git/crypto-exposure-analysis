# crypto-exposure-analysis

[![CI](https://github.com/ara-avetisyan-git/crypto-exposure-analysis/actions/workflows/ci.yml/badge.svg)](https://github.com/ara-avetisyan-git/crypto-exposure-analysis/actions)

A compact tool for **tracing and assessing cryptocurrency exposure** from transfer data and a list of labeled addresses
(sanctioned, mixer, scam, exchange, ...). It runs on public blockchain exports or, as in this repository, on a small
**fictional scenario**; no commercial analytics service is required.

## What it does

- **Taint propagation (haircut method):** how much of an address's received funds originates from each risky category,
  turned into an exposure score from 0 to 100 using category weights.
- **Hop distance:** how many transfers separate an address from risky addresses, in both directions.
- **Typologies:** peeling chains, fan-in / fan-out, rapid forwarding.
- **Service handling:** custodial services such as exchanges pool funds, so tracing stops there and they are not flagged for
  behaviour that is normal for a service.
- **Case view:** `trace` shows the nearest path from a risky address with amounts and timestamps.

## Install and run

```bash
python -m venv .venv && source .venv/bin/activate     # Windows: .venv\Scripts\activate
pip install -e ".[dev]"
pytest -q

crypto-exposure sample  --output-dir examples
crypto-exposure analyze --transactions examples/transactions_synthetic.csv \
                        --labels examples/labels_synthetic.csv --output addresses.csv
crypto-exposure trace   --transactions examples/transactions_synthetic.csv \
                        --labels examples/labels_synthetic.csv --address ADDR_E
```

Inputs: transfers (`txid, timestamp, from_address, to_address, amount`, one row per output, one sender per txid)
and labels (`address, category, [source]`). Weights and thresholds are in [config.yaml](src/crypto_exposure/config.yaml).
Method and limits: [docs/METHOD.md](docs/METHOD.md).

## Limitations

Account-style simplification of transactions (multi-input transactions must be split first), no clustering heuristics,
single asset per run, illustrative weights. Exposure scores support an investigation; they are not evidence of wrongdoing.
Use only public data and addresses you are entitled to analyse.

## License

MIT. Author: Ara Avetisyan, AML/CFT compliance - [LinkedIn](https://www.linkedin.com/in/ara-avetisyan-1795802a)

import pandas as pd
import pytest

from crypto_exposure.analysis import analyze
from crypto_exposure.cli import main
from crypto_exposure.data import load_config, prepare_labels, prepare_transactions
from crypto_exposure.graph import trace_path
from crypto_exposure.sample_data import build
from crypto_exposure.taint import exposure_score, propagate


@pytest.fixture(scope="module")
def config():
    return load_config()


@pytest.fixture(scope="module")
def result(config):
    tx, labels = build()
    return analyze(prepare_transactions(tx), prepare_labels(labels, config), config)


@pytest.fixture(scope="module")
def table(result):
    return result.addresses.set_index("address")


def test_taint_flows_through_the_whole_chain(table):
    for address in ["ADDR_A", "ADDR_B", "ADDR_C", "ADDR_D", "ADDR_E", "ADDR_PEEL_1", "ADDR_PEEL_4"]:
        assert table.loc[address, "exposure_score"] == 100.0, address
        assert table.loc[address, "risk_level"] == "high"


def test_mixed_funds_are_weighted_proportionally(table):
    # 100 of 400 received came from a mixer (weight 0.7) -> 25% x 0.7 = 17.5
    assert table.loc["ADDR_F", "exposure_score"] == 17.5
    # H received 50 carrying F's mix, so the same proportion
    assert table.loc["ADDR_H", "exposure_score"] == 17.5
    assert table.loc["ADDR_F", "risk_level"] == "medium"


def test_clean_addresses_stay_clean(table):
    for address in ("ADDR_CLEAN_1", "ADDR_CLEAN_2"):
        assert table.loc[address, "exposure_score"] == 0.0
        assert table.loc[address, "risk_level"] == "low"
        assert table.loc[address, "flags"] == ""


def test_peeling_chain_is_found(result, table):
    assert len(result.chains) == 1
    chain = result.chains[0]
    assert chain.length == 4 and chain.addresses[0] == "ADDR_A" and chain.addresses[-1] == "ADDR_E"
    assert chain.peeled_total == 20
    assert "peeling_chain" in table.loc["ADDR_C", "flags"]


def test_fan_in_and_rapid_forwarding(table):
    flags = table.loc["ADDR_COLLECTOR", "flags"]
    assert "fan_in" in flags and "rapid_forwarding" in flags
    assert "rapid_forwarding" in table.loc["ADDR_G", "flags"]


def test_services_are_not_flagged_for_normal_service_behaviour(table):
    assert table.loc["ADDR_EXCHANGE_1", "risk_level"] == "service"
    assert table.loc["ADDR_EXCHANGE_1", "flags"] == ""


def test_hops_and_direct_exposure(table):
    assert table.loc["ADDR_A", "hops_from_risky"] == 1
    assert table.loc["ADDR_E", "hops_from_risky"] == 5
    assert table.loc["ADDR_VICTIM_1", "hops_to_risky"] == 1
    assert table.loc["ADDR_VICTIM_1", "direct_risky_counterparties"] == 1
    assert table.loc["ADDR_VICTIM_1", "risk_level"] == "medium"


def test_trace_path(result):
    path = trace_path(result.graph, result.risky_sources, "ADDR_E")
    assert path == ["ADDR_SANCTIONED_1", "ADDR_A", "ADDR_B", "ADDR_C", "ADDR_D", "ADDR_E"]
    assert trace_path(result.graph, result.risky_sources, "ADDR_CLEAN_1") is None


def test_exchange_pools_funds_and_resets_taint(config):
    tx, labels = build()
    received = propagate(prepare_transactions(tx), prepare_labels(labels, config), {"exchange"})
    # the exchange received sanctioned funds, but anything it sends onwards is untracked
    assert exposure_score(received["ADDR_EXCHANGE_1"], config["categories"]) > 50
    extra = pd.concat([tx, pd.DataFrame([("T900", pd.Timestamp("2026-10-01"), "ADDR_EXCHANGE_1", "ADDR_Z", 10, "BTC")],
                                        columns=tx.columns)])
    received = propagate(prepare_transactions(extra), prepare_labels(labels, config), {"exchange"})
    assert exposure_score(received["ADDR_Z"], config["categories"]) == 0.0


def test_input_validation(config):
    tx, labels = build()
    with pytest.raises(ValueError, match="missing columns"):
        prepare_transactions(tx.drop(columns=["amount"]))
    multi = pd.concat([tx, pd.DataFrame([("T002", tx.timestamp[1], "OTHER", "ADDR_X", 1, "BTC")], columns=tx.columns)])
    with pytest.raises(ValueError, match="single sender"):
        prepare_transactions(multi)
    with pytest.raises(ValueError, match="categories missing"):
        prepare_labels(labels.assign(category="unknown_type"), config)


def test_cli_end_to_end(tmp_path, capsys):
    assert main(["sample", "--output-dir", str(tmp_path)]) == 0
    tx, lb, out = tmp_path / "transactions_synthetic.csv", tmp_path / "labels_synthetic.csv", tmp_path / "out.csv"
    assert main(["analyze", "--transactions", str(tx), "--labels", str(lb), "--output", str(out)]) == 0
    assert "Peeling chain #1" in capsys.readouterr().out
    assert main(["trace", "--transactions", str(tx), "--labels", str(lb), "--address", "ADDR_E"]) == 0
    assert "ADDR_SANCTIONED_1 -> ADDR_A" in capsys.readouterr().out
    assert main(["trace", "--transactions", str(tx), "--labels", str(lb), "--address", "NOPE"]) == 1

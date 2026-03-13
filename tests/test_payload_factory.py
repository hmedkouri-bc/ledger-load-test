"""Tests for payload factory."""

from src.config_loader import load_config
from src.payload_factory import PayloadFactory


def _make_factory() -> PayloadFactory:
    config = load_config("config/local.yaml")
    return PayloadFactory(config)


def test_user_pool_deterministic():
    """Same seed should produce same user pool."""
    f1 = _make_factory()
    f2 = _make_factory()
    assert f1.user_pool == f2.user_pool


def test_user_pool_size():
    f = _make_factory()
    config = load_config("config/local.yaml")
    assert len(f.user_pool) == config["test"]["user_pool_size"]


def test_balance_request_args():
    f = _make_factory()
    args = f.balance_request_args()
    assert "owner_high" in args
    assert "owner_low" in args
    assert args["account"] == 200500
    assert args["max_offset"] == 0
    # sint64 range check
    assert -(1 << 63) <= args["owner_high"] < (1 << 63)
    assert -(1 << 63) <= args["owner_low"] < (1 << 63)


def test_append_request_args():
    f = _make_factory()
    args = f.append_request_args()
    assert args["account"] == 200500
    assert args["origin"] == "LOADTEST_FLUTTERWAVE"
    assert args["external_ref"].startswith("LOADTEST:")
    assert args["leg_currency"] == "USDT"
    assert args["leg_account"] == 200510
    assert -1000000.0 <= args["leg_amount"] <= -500.0
    assert args["leg_string_amount"] == str(args["leg_amount"])
    assert args["leg_ex_currency"] == "USDT"
    assert args["leg_ex_rate"] == 1.0


def test_append_unique_ids():
    """Each append call should generate unique transaction IDs."""
    f = _make_factory()
    ids = set()
    for _ in range(50):
        args = f.append_request_args()
        key = (args["txn_id_high"], args["txn_id_low"])
        assert key not in ids
        ids.add(key)

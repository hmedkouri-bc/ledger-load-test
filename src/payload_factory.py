"""Builds realistic Ledger gRPC request payloads."""

import random
import uuid

from src.uuid_utils import uuid_to_high_low


class PayloadFactory:
    """Generates GetBalanceRequest and AppendTransactionRequest payloads."""

    def __init__(self, config: dict):
        self.config = config
        self.origin = config["test"]["origin"]
        self.ref_prefix = config["test"]["external_ref_prefix"]
        self.funding_account = config["accounts"]["funding"]
        self.trading_account = config["accounts"]["trading"]
        self.currency = config["currencies"]["primary"]
        self.amount_min = config["amounts"]["min"]
        self.amount_max = config["amounts"]["max"]

        # Deterministic user pool to avoid single-account serialization
        seed = config["test"]["user_uuid_seed"]
        pool_size = config["test"]["user_pool_size"]
        rng = random.Random(seed)
        self.user_pool = [
            uuid.UUID(int=rng.getrandbits(128)) for _ in range(pool_size)
        ]

    def random_owner(self) -> uuid.UUID:
        return random.choice(self.user_pool)

    def balance_request_args(self) -> dict:
        """Return kwargs for building a GetBalanceRequest."""
        owner = self.random_owner()
        high, low = uuid_to_high_low(owner)
        return {
            "owner_high": high,
            "owner_low": low,
            "account": self.funding_account,
            "max_offset": 0,
        }

    def append_request_args(self) -> dict:
        """Return kwargs for building an AppendTransactionRequest."""
        owner = self.random_owner()
        owner_high, owner_low = uuid_to_high_low(owner)

        txn_id = uuid.uuid4()
        txn_high, txn_low = uuid_to_high_low(txn_id)

        leg_id = uuid.uuid4()
        leg_high, leg_low = uuid_to_high_low(leg_id)

        amount = round(random.uniform(self.amount_min, self.amount_max), 2)

        return {
            "txn_id_high": txn_high,
            "txn_id_low": txn_low,
            "account": self.funding_account,
            "origin": self.origin,
            "external_ref": f"{self.ref_prefix}{txn_id}",
            "owner_high": owner_high,
            "owner_low": owner_low,
            "leg_id_high": leg_high,
            "leg_id_low": leg_low,
            "leg_currency": self.currency,
            "leg_amount": -amount,
            "leg_string_amount": str(-amount),
            "leg_ex_currency": self.currency,
            "leg_ex_amount": amount,
            "leg_string_ex_amount": str(amount),
            "leg_ex_rate": 1.0,
            "leg_account": self.trading_account,
        }

"""Base Locust User for gRPC load testing with timing and error reporting."""

import time

from grpclib.exceptions import GRPCError
from locust import User, events

from src.async_bridge import run_async, create_on_loop
from src.config_loader import load_config
from src.grpc_client import (
    LedgerBalanceClient,
    LedgerTransactionClient,
    create_channel,
    get_metadata,
)
from src.payload_factory import PayloadFactory


class GrpcUser(User):
    """Base User that manages a grpclib channel and reports RPC timing to Locust."""

    abstract = True

    def __init__(self, environment):
        super().__init__(environment)
        self.config = load_config()
        self.channel = create_on_loop(create_channel, self.config)
        timeout = self.config["ledger"]["rpc_timeout_seconds"]
        metadata = get_metadata(self.config)
        self.txn_client = LedgerTransactionClient(self.channel, timeout, metadata)
        self.bal_client = LedgerBalanceClient(self.channel, timeout, metadata)
        self.factory = PayloadFactory(self.config)

    def on_stop(self):
        if self.channel:
            self.channel.close()

    def _rpc_call(self, request_type: str, name: str, coro_func, *args, **kwargs):
        """Execute an async RPC via the bridge, measure timing, and report to Locust."""
        start = time.perf_counter()
        try:
            result = run_async(coro_func(*args, **kwargs))
            elapsed_ms = (time.perf_counter() - start) * 1000
            events.request.fire(
                request_type=request_type,
                name=name,
                response_time=elapsed_ms,
                response_length=0,
                exception=None,
                context=self.context(),
            )
            return result
        except (GRPCError, Exception) as e:
            elapsed_ms = (time.perf_counter() - start) * 1000
            events.request.fire(
                request_type=request_type,
                name=name,
                response_time=elapsed_ms,
                response_length=0,
                exception=e,
                context=self.context(),
            )

    def grpc_balance_check(self):
        args = self.factory.balance_request_args()
        return self._rpc_call(
            "grpc", "userAccountBalance",
            self.bal_client.user_account_balance, args,
        )

    def grpc_append(self):
        args = self.factory.append_request_args()
        return self._rpc_call(
            "grpc", "append",
            self.txn_client.append, args,
        )

    def grpc_ping_txn(self):
        return self._rpc_call(
            "grpc", "ping/txn",
            self.txn_client.ping, 0, 0,
        )

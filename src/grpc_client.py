"""Thin wrapper around generated Ledger gRPC stubs (grpclib)."""

import ssl

from grpclib.client import Channel

from ledger import ledger_transaction_pb2 as txn_pb2
from ledger import ledger_transaction_grpc as txn_grpc
from ledger import ledger_balance_pb2 as bal_pb2
from ledger import ledger_balance_grpc as bal_grpc


def create_channel(config: dict) -> Channel:
    """Create a grpclib Channel from config."""
    host = config["ledger"]["host"]
    port = int(config["ledger"]["port"])

    ssl_context = None
    if config["ledger"]["tls"]:
        ssl_context = ssl.SSLContext(ssl.PROTOCOL_TLS_CLIENT)
        ssl_context.set_alpn_protocols(["h2"])
        if config["ledger"].get("tls_skip_verify"):
            ssl_context.check_hostname = False
            ssl_context.verify_mode = ssl.CERT_NONE
        else:
            ca_cert_path = config["ledger"].get("tls_ca_cert")
            if ca_cert_path:
                ssl_context.load_verify_locations(ca_cert_path)

    authority = config["ledger"].get("tls_authority")
    if authority and ssl_context:
        # For tunnels: connect to host:port but send authority as :authority
        # and use it as SNI for TLS
        from grpclib.config import Configuration
        grpc_config = Configuration(ssl_target_name_override=authority)
        channel = Channel(host=host, port=port, ssl=ssl_context, config=grpc_config)
        channel._authority = authority
        return channel
    elif authority:
        channel = Channel(host=host, port=port)
        channel._authority = authority
        return channel

    return Channel(host=host, port=port, ssl=ssl_context)


def get_metadata(config: dict) -> dict:
    """Build metadata dict from config."""
    x_origin = config["ledger"].get("x_origin")
    if x_origin:
        return {"x-origin": x_origin}
    return {}


def make_unique_id(high: int, low: int) -> txn_pb2.UniqueID:
    return txn_pb2.UniqueID(high=high, low=low)


class LedgerTransactionClient:
    def __init__(self, channel: Channel, timeout: float = 5.0, metadata: dict = None):
        self.stub = txn_grpc.LedgerTransactionServiceStub(channel)
        self.timeout = timeout
        self.metadata = metadata or {}

    async def ping(self, high: int, low: int) -> txn_pb2.UniqueID:
        return await self.stub.ping(
            make_unique_id(high, low),
            timeout=self.timeout,
            metadata=self.metadata,
        )

    async def append(self, args: dict) -> txn_pb2.AppendTransactionResponse:
        req = txn_pb2.AppendTransactionRequest(
            transaction=[
                txn_pb2.TransactionProto(
                    id=make_unique_id(args["txn_id_high"], args["txn_id_low"]),
                    account=args["account"],
                    origin=args["origin"],
                    external_ref=args["external_ref"],
                    owner=make_unique_id(args["owner_high"], args["owner_low"]),
                    legs=[
                        txn_pb2.TransactionLegProto(
                            id=make_unique_id(args["leg_id_high"], args["leg_id_low"]),
                            currency=args["leg_currency"],
                            amount=args["leg_amount"],
                            string_amount=args["leg_string_amount"],
                            ex_currency=args["leg_ex_currency"],
                            ex_amount=args["leg_ex_amount"],
                            string_ex_amount=args["leg_string_ex_amount"],
                            ex_rate=args["leg_ex_rate"],
                            account=args["leg_account"],
                            owner=make_unique_id(args["owner_high"], args["owner_low"]),
                        )
                    ],
                )
            ]
        )
        return await self.stub.append(req, timeout=self.timeout, metadata=self.metadata)

    async def append_checked(self, args: dict) -> txn_pb2.AppendTransactionResponse:
        req = txn_pb2.AppendTransactionRequest(
            transaction=[
                txn_pb2.TransactionProto(
                    id=make_unique_id(args["txn_id_high"], args["txn_id_low"]),
                    account=args["account"],
                    origin=args["origin"],
                    external_ref=args["external_ref"],
                    owner=make_unique_id(args["owner_high"], args["owner_low"]),
                    legs=[
                        txn_pb2.TransactionLegProto(
                            id=make_unique_id(args["leg_id_high"], args["leg_id_low"]),
                            currency=args["leg_currency"],
                            amount=args["leg_amount"],
                            string_amount=args["leg_string_amount"],
                            ex_currency=args["leg_ex_currency"],
                            ex_amount=args["leg_ex_amount"],
                            string_ex_amount=args["leg_string_ex_amount"],
                            ex_rate=args["leg_ex_rate"],
                            account=args["leg_account"],
                            owner=make_unique_id(args["owner_high"], args["owner_low"]),
                        )
                    ],
                )
            ]
        )
        return await self.stub.appendChecked(req, timeout=self.timeout, metadata=self.metadata)


class LedgerBalanceClient:
    def __init__(self, channel: Channel, timeout: float = 5.0, metadata: dict = None):
        self.stub = bal_grpc.LedgerBalanceServiceStub(channel)
        self.timeout = timeout
        self.metadata = metadata or {}

    async def ping(self, high: int, low: int) -> txn_pb2.UniqueID:
        return await self.stub.ping(
            make_unique_id(high, low),
            timeout=self.timeout,
            metadata=self.metadata,
        )

    async def user_account_balance(self, args: dict) -> bal_pb2.GetBalanceResponse:
        req = bal_pb2.GetBalanceRequest(
            owner=make_unique_id(args["owner_high"], args["owner_low"]),
            account=args["account"],
            max_offset=args["max_offset"],
        )
        return await self.stub.userAccountBalance(
            req, timeout=self.timeout, metadata=self.metadata,
        )

"""Thin wrapper around generated Ledger gRPC stubs."""

import grpc

from ledger import ledger_transaction_pb2 as txn_pb2
from ledger import ledger_transaction_pb2_grpc as txn_grpc
from ledger import ledger_balance_pb2 as bal_pb2
from ledger import ledger_balance_pb2_grpc as bal_grpc


def create_channel(config: dict) -> grpc.Channel:
    """Create a gRPC channel from config, with optional x-origin interceptor."""
    target = f"{config['ledger']['host']}:{config['ledger']['port']}"
    x_origin = config["ledger"].get("x_origin")
    if config["ledger"]["tls"]:
        if config["ledger"].get("tls_skip_verify"):
            # Fetch the server's cert via subprocess to avoid gevent-patched ssl issues.
            import subprocess
            host = config["ledger"]["host"]
            port = int(config["ledger"]["port"])
            result = subprocess.run(
                ["openssl", "s_client", "-connect", f"{host}:{port}",
                 "-servername", host],
                input=b"",
                capture_output=True,
                timeout=10,
            )
            # Extract PEM certificate from openssl output
            output = result.stdout.decode("utf-8", errors="replace")
            begin = output.find("-----BEGIN CERTIFICATE-----")
            end = output.find("-----END CERTIFICATE-----")
            if begin == -1 or end == -1:
                raise RuntimeError(
                    f"Could not fetch server certificate from {host}:{port}. "
                    f"openssl stderr: {result.stderr.decode()}"
                )
            server_cert_pem = output[begin:end + len("-----END CERTIFICATE-----")].encode()

            # Extract CN/SAN for hostname override
            from cryptography import x509 as cx509
            cert = cx509.load_pem_x509_certificate(server_cert_pem)
            try:
                san = cert.extensions.get_extension_for_class(
                    cx509.SubjectAlternativeName
                )
                cert_name = san.value.get_values_for_type(cx509.DNSName)[0]
            except (cx509.ExtensionNotFound, IndexError):
                cn = cert.subject.get_attributes_for_oid(cx509.oid.NameOID.COMMON_NAME)
                cert_name = cn[0].value if cn else host

            creds = grpc.ssl_channel_credentials(root_certificates=server_cert_pem)
            options = [
                ("grpc.ssl_target_name_override", cert_name),
                ("grpc.default_authority", host),
            ]
            channel = grpc.secure_channel(target, creds, options=options)
        else:
            root_certs = None
            ca_cert_path = config["ledger"].get("tls_ca_cert")
            if ca_cert_path:
                with open(ca_cert_path, "rb") as f:
                    root_certs = f.read()
            creds = grpc.ssl_channel_credentials(root_certificates=root_certs)
            channel = grpc.secure_channel(target, creds)
    else:
        channel = grpc.insecure_channel(target)

    if x_origin:
        channel = grpc.intercept_channel(channel, _OriginInterceptor(x_origin))
    return channel


class _ClientCallDetails(
    grpc.ClientCallDetails,
):
    def __init__(self, method, timeout, metadata, credentials, wait_for_ready, compression):
        self.method = method
        self.timeout = timeout
        self.metadata = metadata
        self.credentials = credentials
        self.wait_for_ready = wait_for_ready
        self.compression = compression


class _OriginInterceptor(
    grpc.UnaryUnaryClientInterceptor,
    grpc.UnaryStreamClientInterceptor,
):
    """Injects `x-origin` metadata header, matching the Kotlin client behaviour."""

    def __init__(self, origin: str):
        self._metadata = [("x-origin", origin)]

    def _add_metadata(self, client_call_details):
        metadata = list(client_call_details.metadata or [])
        metadata.extend(self._metadata)
        return _ClientCallDetails(
            client_call_details.method,
            client_call_details.timeout,
            metadata,
            client_call_details.credentials,
            client_call_details.wait_for_ready,
            client_call_details.compression,
        )

    def intercept_unary_unary(self, continuation, client_call_details, request):
        return continuation(self._add_metadata(client_call_details), request)

    def intercept_unary_stream(self, continuation, client_call_details, request):
        return continuation(self._add_metadata(client_call_details), request)


def make_unique_id(high: int, low: int) -> txn_pb2.UniqueID:
    return txn_pb2.UniqueID(high=high, low=low)


class LedgerTransactionClient:
    def __init__(self, channel: grpc.Channel, timeout: float = 5.0):
        self.stub = txn_grpc.LedgerTransactionServiceStub(channel)
        self.timeout = timeout

    def ping(self, high: int, low: int) -> txn_pb2.UniqueID:
        return self.stub.ping(make_unique_id(high, low), timeout=self.timeout)

    def append(self, args: dict) -> txn_pb2.AppendTransactionResponse:
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
        return self.stub.append(req, timeout=self.timeout)

    def append_checked(self, args: dict) -> txn_pb2.AppendTransactionResponse:
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
        return self.stub.appendChecked(req, timeout=self.timeout)


class LedgerBalanceClient:
    def __init__(self, channel: grpc.Channel, timeout: float = 5.0):
        self.stub = bal_grpc.LedgerBalanceServiceStub(channel)
        self.timeout = timeout

    def ping(self, high: int, low: int) -> txn_pb2.UniqueID:
        return self.stub.ping(make_unique_id(high, low), timeout=self.timeout)

    def user_account_balance(self, args: dict) -> bal_pb2.GetBalanceResponse:
        req = bal_pb2.GetBalanceRequest(
            owner=make_unique_id(args["owner_high"], args["owner_low"]),
            account=args["account"],
            max_offset=args["max_offset"],
        )
        return self.stub.userAccountBalance(req, timeout=self.timeout)

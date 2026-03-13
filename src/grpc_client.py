"""Thin wrapper around generated Ledger gRPC stubs."""

import grpc

from ledger import ledger_transaction_pb2 as txn_pb2
from ledger import ledger_transaction_pb2_grpc as txn_grpc
from ledger import ledger_balance_pb2 as bal_pb2
from ledger import ledger_balance_pb2_grpc as bal_grpc


_tls_cache = {}


def _fetch_server_cert(host, port, authority):
    """Fetch server cert, cache it, and set GRPC_DEFAULT_SSL_ROOTS_FILE_PATH.

    This ensures gRPC's C core (BoringSSL) trusts the cert globally,
    including on reconnections and new subchannels.
    """
    cache_key = (host, port, authority)
    if cache_key in _tls_cache:
        return _tls_cache[cache_key]

    import os
    import re
    import subprocess
    import tempfile

    result = subprocess.run(
        ["openssl", "s_client", "-connect", f"{host}:{port}",
         "-servername", authority, "-showcerts"],
        input=b"",
        capture_output=True,
        timeout=10,
    )
    output = result.stdout.decode("utf-8", errors="replace")
    certs = re.findall(
        r"(-----BEGIN CERTIFICATE-----.*?-----END CERTIFICATE-----)",
        output,
        re.DOTALL,
    )
    if not certs:
        raise RuntimeError(
            f"Could not fetch server certificate from {host}:{port}. "
            f"openssl stderr: {result.stderr.decode()}"
        )
    server_cert_pem = "\n".join(certs).encode()

    # Write cert to file and set env var so BoringSSL trusts it globally
    cert_file = tempfile.NamedTemporaryFile(
        prefix="grpc_root_", suffix=".pem", delete=False,
    )
    cert_file.write(server_cert_pem)
    cert_file.close()
    os.environ["GRPC_DEFAULT_SSL_ROOTS_FILE_PATH"] = cert_file.name

    from cryptography import x509 as cx509
    leaf = cx509.load_pem_x509_certificate(certs[0].encode())
    try:
        san = leaf.extensions.get_extension_for_class(
            cx509.SubjectAlternativeName
        )
        cert_name = san.value.get_values_for_type(cx509.DNSName)[0]
    except (cx509.ExtensionNotFound, IndexError):
        cn = leaf.subject.get_attributes_for_oid(cx509.oid.NameOID.COMMON_NAME)
        cert_name = cn[0].value if cn else authority

    _tls_cache[cache_key] = (server_cert_pem, cert_name)
    return server_cert_pem, cert_name


def create_channel(config: dict) -> grpc.Channel:
    """Create a gRPC channel from config, with optional x-origin interceptor."""
    target = f"{config['ledger']['host']}:{config['ledger']['port']}"
    x_origin = config["ledger"].get("x_origin")
    if config["ledger"]["tls"]:
        if config["ledger"].get("tls_skip_verify"):
            host = config["ledger"]["host"]
            port = int(config["ledger"]["port"])
            authority = config["ledger"].get("tls_authority", host)
            server_cert_pem, cert_name = _fetch_server_cert(host, port, authority)

            creds = grpc.ssl_channel_credentials(root_certificates=server_cert_pem)
            options = [
                ("grpc.ssl_target_name_override", cert_name),
                ("grpc.default_authority", authority),
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
        options = []
        authority = config["ledger"].get("tls_authority")
        if authority:
            options.append(("grpc.default_authority", authority))
        channel = grpc.insecure_channel(target, options=options if options else None)

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

#!/usr/bin/env python3
"""Quick gRPC connectivity test against the Ledger health endpoint."""

import sys
import os

sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))
sys.path.insert(0, os.path.join(os.path.dirname(__file__), "..", "generated"))

from src.config_loader import load_config
from src.grpc_client import create_channel

import grpc
from grpc_health.v1 import health_pb2, health_pb2_grpc


def main():
    config_path = sys.argv[1] if len(sys.argv) > 1 else None
    config = load_config(config_path)

    ledger = config["ledger"]
    print(f"Target:          {ledger['host']}:{ledger['port']}")
    print(f"TLS:             {ledger.get('tls', False)}")
    print(f"TLS skip verify: {ledger.get('tls_skip_verify', False)}")
    print(f"x-origin:        {ledger.get('x_origin', '(none)')}")
    print()

    print("Creating channel...")
    channel = create_channel(config)

    # 1. Test gRPC health check (grpc.health.v1.Health/Check)
    print("\n--- grpc.health.v1.Health/Check ---")
    try:
        stub = health_pb2_grpc.HealthStub(channel)
        req = health_pb2.HealthCheckRequest(service="")
        resp = stub.Check(req, timeout=5)
        status_name = health_pb2.HealthCheckResponse.ServingStatus.Name(resp.status)
        print(f"  OK: status={status_name}")
    except grpc.RpcError as e:
        print(f"  FAILED: {e.code().name} — {e.details()}")

    # 2. Test Ledger ping (LedgerTransactionService/ping)
    print("\n--- LedgerTransactionService/ping ---")
    try:
        from src.grpc_client import LedgerTransactionClient
        txn = LedgerTransactionClient(channel, timeout=5)
        resp = txn.ping(0, 1)
        print(f"  OK: high={resp.high}, low={resp.low}")
    except grpc.RpcError as e:
        print(f"  FAILED: {e.code().name} — {e.details()}")

    # 3. Test Ledger balance ping (LedgerBalanceService/ping)
    print("\n--- LedgerBalanceService/ping ---")
    try:
        from src.grpc_client import LedgerBalanceClient
        bal = LedgerBalanceClient(channel, timeout=5)
        resp = bal.ping(0, 1)
        print(f"  OK: high={resp.high}, low={resp.low}")
    except grpc.RpcError as e:
        print(f"  FAILED: {e.code().name} — {e.details()}")

    # 4. Also try the Java CLI for comparison
    print("\n--- Java CLI comparison (snapshot) ---")
    import subprocess
    jar_path = "/tmp/nabu-ledger-cli-1.4.57.jar"
    if os.path.exists(jar_path):
        server = f"{ledger['host']}:{ledger['port']}"
        result = subprocess.run(
            ["java", "-jar", jar_path, "snapshot",
             f"--server={server}", "MERCURY_BALANCE"],
            capture_output=True, text=True, timeout=15,
        )
        print(f"  stdout: {result.stdout[:500] if result.stdout else '(empty)'}")
        print(f"  stderr: {result.stderr[:500] if result.stderr else '(empty)'}")
        print(f"  exit code: {result.returncode}")
    else:
        print("  (jar not found, skipping)")

    channel.close()
    print("\nDone.")


if __name__ == "__main__":
    main()

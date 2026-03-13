"""Test multiple concurrent gRPC TLS connections through the tunnel."""

import sys
import threading
import time

import grpc

sys.path.insert(0, ".")
sys.path.insert(0, "generated")

from src.config_loader import load_config
from src.grpc_client import create_channel


def test_single_connection(i, config, results):
    try:
        channel = create_channel(config)
        # Force the channel to connect
        future = grpc.channel_ready_future(channel)
        future.result(timeout=10)
        results[i] = "OK"
        channel.close()
    except Exception as e:
        results[i] = f"FAIL: {e}"


def main():
    config = load_config()
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 10

    print(f"Testing {n} sequential connections...")
    for i in range(n):
        try:
            channel = create_channel(config)
            future = grpc.channel_ready_future(channel)
            future.result(timeout=10)
            print(f"  Connection {i+1}: OK")
            channel.close()
        except Exception as e:
            print(f"  Connection {i+1}: FAIL - {e}")

    print(f"\nTesting {n} concurrent connections...")
    results = {}
    threads = []
    for i in range(n):
        t = threading.Thread(target=test_single_connection, args=(i, config, results))
        threads.append(t)

    for t in threads:
        t.start()
    for t in threads:
        t.join(timeout=15)

    for i in range(n):
        print(f"  Connection {i+1}: {results.get(i, 'TIMEOUT')}")

    ok = sum(1 for v in results.values() if v == "OK")
    print(f"\nResult: {ok}/{n} connections succeeded")


if __name__ == "__main__":
    main()

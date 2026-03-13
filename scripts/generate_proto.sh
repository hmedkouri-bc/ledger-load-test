#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PYTHON="${PYTHON:-python3}"

# Ensure grpclib protoc plugin is on PATH
PYTHON_BIN_DIR="$(dirname "$PYTHON")"
export PATH="$PYTHON_BIN_DIR:$PATH"

PROTO_DIR="$PROJECT_ROOT/proto/ledger"
OUT_DIR="$PROJECT_ROOT/generated/ledger"

mkdir -p "$OUT_DIR"

# Pass 1: protobuf message classes
$PYTHON -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --pyi_out="$OUT_DIR" \
    "$PROTO_DIR"/ledger_transaction.proto \
    "$PROTO_DIR"/ledger_balance.proto

# Pass 2: grpclib service stubs
$PYTHON -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --grpclib_python_out="$OUT_DIR" \
    "$PROTO_DIR"/ledger_transaction.proto \
    "$PROTO_DIR"/ledger_balance.proto

# Create __init__.py for the generated package
touch "$PROJECT_ROOT/generated/__init__.py"
touch "$OUT_DIR/__init__.py"

# Fix relative imports in generated stubs
for f in "$OUT_DIR"/*.py; do
    sed -i '' 's/^import ledger_transaction_pb2/from . import ledger_transaction_pb2/' "$f" 2>/dev/null || \
    sed -i 's/^import ledger_transaction_pb2/from . import ledger_transaction_pb2/' "$f"

    sed -i '' 's/^import ledger_balance_pb2/from . import ledger_balance_pb2/' "$f" 2>/dev/null || \
    sed -i 's/^import ledger_balance_pb2/from . import ledger_balance_pb2/' "$f"
done

# Remove old grpcio stubs if present
rm -f "$OUT_DIR"/*_pb2_grpc.py

echo "Proto stubs generated in $OUT_DIR"

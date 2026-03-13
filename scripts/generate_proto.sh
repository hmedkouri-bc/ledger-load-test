#!/usr/bin/env bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
PROJECT_ROOT="$(dirname "$SCRIPT_DIR")"

PYTHON="${PYTHON:-python3}"

PROTO_DIR="$PROJECT_ROOT/proto/ledger"
OUT_DIR="$PROJECT_ROOT/generated/ledger"

mkdir -p "$OUT_DIR"

$PYTHON -m grpc_tools.protoc \
    --proto_path="$PROTO_DIR" \
    --python_out="$OUT_DIR" \
    --pyi_out="$OUT_DIR" \
    --grpc_python_out="$OUT_DIR" \
    "$PROTO_DIR"/ledger_transaction.proto \
    "$PROTO_DIR"/ledger_balance.proto

# Create __init__.py for the generated package
touch "$PROJECT_ROOT/generated/__init__.py"
touch "$OUT_DIR/__init__.py"

# Fix relative imports in generated stubs
# grpc_tools generates absolute imports but we need relative imports for package use
for f in "$OUT_DIR"/*.py; do
    sed -i '' 's/^import ledger_transaction_pb2/from . import ledger_transaction_pb2/' "$f" 2>/dev/null || \
    sed -i 's/^import ledger_transaction_pb2/from . import ledger_transaction_pb2/' "$f"

    sed -i '' 's/^import ledger_balance_pb2/from . import ledger_balance_pb2/' "$f" 2>/dev/null || \
    sed -i 's/^import ledger_balance_pb2/from . import ledger_balance_pb2/' "$f"
done

echo "Proto stubs generated in $OUT_DIR"

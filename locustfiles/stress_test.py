"""Scenario 4: Mixed workload at 5x volume (150 RPS) — find breaking point."""

from locust import task, between

from locustfiles.grpc_user import GrpcUser
from src.load_shapes import StressTestShape


class StressTestUser(GrpcUser):
    wait_time = between(0.05, 0.2)

    @task(7)
    def check_balance(self):
        self.grpc_balance_check()

    @task(3)
    def append_transaction(self):
        self.grpc_append()


class StressShape(StressTestShape):
    pass

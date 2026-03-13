"""Scenario 3: 70% balance / 30% append — realistic RFQ simulation."""

from locust import task, between

from locustfiles.grpc_user import GrpcUser
from src.load_shapes import FlutterwaveLoadShape


class MixedWorkloadUser(GrpcUser):
    wait_time = between(0.1, 0.5)

    @task(7)
    def check_balance(self):
        self.grpc_balance_check()

    @task(3)
    def append_transaction(self):
        self.grpc_append()


# Attach shape so `locust -f mixed_workload.py` picks it up
class MixedWorkloadShape(FlutterwaveLoadShape):
    pass

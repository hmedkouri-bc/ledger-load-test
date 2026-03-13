"""Scenario 1: 100% balance check calls — isolate read performance."""

from locust import task, between

from locustfiles.grpc_user import GrpcUser


class BalanceCheckUser(GrpcUser):
    wait_time = between(0.1, 0.5)

    @task
    def check_balance(self):
        self.grpc_balance_check()

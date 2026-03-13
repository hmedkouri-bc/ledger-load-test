"""Scenario 2: 100% append calls — isolate write performance."""

from locust import task, between

from locustfiles.grpc_user import GrpcUser


class AppendTransactionUser(GrpcUser):
    wait_time = between(0.1, 0.5)

    @task
    def append_transaction(self):
        self.grpc_append()

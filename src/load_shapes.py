"""Custom Locust LoadTestShape classes for Flutterwave load profiles."""

from locust import LoadTestShape


class FlutterwaveLoadShape(LoadTestShape):
    """Simulates Flutterwave's traffic pattern: warm-up -> baseline -> peak -> cool-down.

    Timeline (seconds):
      0-60:     ramp 0 -> 6 users (warm-up)
      60-300:   sustain 6 users (baseline)
      300-360:  ramp 6 -> 30 users (peak ramp)
      360-660:  sustain 30 users (peak hold, 5 min)
      660-720:  ramp down 30 -> 6
      720-1020: sustain 6 users (cool-down)
    """

    stages = [
        {"duration": 60, "users": 6, "spawn_rate": 0.1},
        {"duration": 300, "users": 6, "spawn_rate": 1},
        {"duration": 360, "users": 30, "spawn_rate": 0.4},
        {"duration": 660, "users": 30, "spawn_rate": 1},
        {"duration": 720, "users": 6, "spawn_rate": 0.4},
        {"duration": 1020, "users": 6, "spawn_rate": 1},
    ]

    def tick(self):
        run_time = self.get_run_time()
        for stage in self.stages:
            if run_time < stage["duration"]:
                return stage["users"], stage["spawn_rate"]
        return None


class StressTestShape(LoadTestShape):
    """Ramp 0 -> 150 RPS in steps of 10, hold each step for 60s."""

    step_size = 10
    step_duration = 60  # seconds per step
    max_users = 150

    def tick(self):
        run_time = self.get_run_time()
        step = int(run_time // self.step_duration)
        users = min((step + 1) * self.step_size, self.max_users)
        if users > self.max_users:
            return None
        return users, self.step_size


class StabilityLoadShape(LoadTestShape):
    """Sustained 6 RPS with periodic 30 RPS spikes every 30 min.

    Each spike lasts 5 min.
    Total duration: 24h (86400s).
    """

    base_users = 6
    spike_users = 30
    cycle_duration = 1800  # 30 min
    spike_duration = 300  # 5 min
    total_duration = 86400  # 24h

    def tick(self):
        run_time = self.get_run_time()
        if run_time > self.total_duration:
            return None
        position_in_cycle = run_time % self.cycle_duration
        if position_in_cycle >= (self.cycle_duration - self.spike_duration):
            return self.spike_users, 4
        return self.base_users, 1

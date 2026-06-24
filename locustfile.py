from locust import HttpUser, task, between

class CoinGeckoUser(HttpUser):
    wait_time = between(1,3)

    @task(3)
    def list_coins(self):
        self.client.get("/coins/")

    @task(3)
    def get_coins(self):
        self.client.get("/coins/bitcoin")

    @task(1)
    def get_history(self):
        self.client.get(
            "/coins/bitcoin/history?start=2026-01-01T00:00:00&end=2026-12-31T00:00:00"
        )
import time


class RateLimiter:
    """Simple in-memory fixed-window request rate limiter."""

    def __init__(self, window_seconds: int = 60) -> None:
        self.window_seconds = window_seconds
        self._requests: dict[str, tuple[float, int]] = {}

    def allow_request(self, user_id: str, plan: str, limits_config: dict) -> bool:
        """Return whether a user can make another request in the current window."""
        rate_limits = limits_config.get("rate_limits", {})
        plan_limits = rate_limits.get(plan) or rate_limits.get("standard", {})
        requests_per_minute = plan_limits.get("requests_per_minute")

        if requests_per_minute is None:
            return True

        now = time.monotonic()
        window_start, request_count = self._requests.get(user_id, (now, 0))

        if now - window_start >= self.window_seconds:
            window_start = now
            request_count = 0

        if request_count >= int(requests_per_minute):
            self._requests[user_id] = (window_start, request_count)
            return False

        self._requests[user_id] = (window_start, request_count + 1)
        return True
